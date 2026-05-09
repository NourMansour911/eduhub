import json
from pathlib import Path
from typing import Any

from fastapi import Depends
from langchain_openai import ChatOpenAI
from pymongo.errors import DuplicateKeyError
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat,AnalyzeResult
from integrations.llm import LCOpenAI
from core.request_dependencies import get_lecture_repo, get_doc_intelligence_client, get_langchain_client
from core import Settings, get_settings
from models import LectureModel
from repositories import LectureRepo
from schemas import (
    DeleteLectureResponse,
    LectureStoreRequest,
    LectureDeleteByIdRequest,
    LectureDeleteBySubjectRequest,
    LectureListResponse,
    LectureResponse,
)
from helpers.utils import serialize_content
from helpers import get_logger

from .lecture_exceptions import (
    LectureConflictError,
    LectureNotFoundError,
    LectureServiceException,
)

logger = get_logger(__name__)


class LectureService:
    def __init__(self, lecture_repo: LectureRepo, doc_intelligence_client: DocumentIntelligenceClient, summary_llm: ChatOpenAI):
        self.lecture_repo = lecture_repo
        self.doc_intelligence_client = doc_intelligence_client
        self.summary_llm = summary_llm

    async def prepare_lecture_content(self, pdf_url: str):

        try:
            """             
            poller = self.doc_intelligence_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(url_source=pdf_url),
                output_content_format=DocumentContentFormat.MARKDOWN,
            )
            analyze_result = poller.result()
            return analyze_result """
            
            # Load from eduhub_demos folder
            
            projects_root = Path(__file__).parents[4]  # Navigate to d:\training\AI\projects
            json_file = projects_root / "demos" /"eduhub_demos" / "data_mining_azure.json"
            
            with open(json_file, "r", encoding="utf-8") as f:
                result_data = json.load(f)

            analyze_result = AnalyzeResult(result_data)  
            
            return analyze_result
        except Exception as exc:
            raise LectureServiceException(
                details={"operation": "prepare_lecture_content", "error": str(exc), "pdf_url": pdf_url}
            )

    async def store_lecture(self, payload: LectureStoreRequest) -> LectureResponse:
        prepared_content = await self.prepare_lecture_content(payload.url)

        lecture = LectureModel(
            lecture_id=payload.lecture_id,
            lecture_name=payload.lecture_name,
            subject_id=payload.subject_id,
            subject_name=payload.subject_name,
            content=prepared_content,
            order=payload.order,
        )
        
        try:
            inserted_id = await self.lecture_repo.add_lecture(lecture)
        except DuplicateKeyError as exc:
            raise LectureConflictError(details={"lecture_id": lecture.lecture_id, "error": str(exc)})
        except Exception as exc:
            raise LectureServiceException(details={"operation": "store_lecture", "error": str(exc)})

        return LectureResponse(
            _id=str(inserted_id),
            lecture_id=lecture.lecture_id,
            lecture_name=lecture.lecture_name,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=serialize_content(lecture.content),
            order=lecture.order,
        )

    async def get_lecture(self, lecture_id: str) -> LectureResponse:
        try:
            lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "get_lecture", "error": str(exc)})
        if not lecture:
            raise LectureNotFoundError(details={"lecture_id": lecture_id})

        return LectureResponse(
            _id=str(lecture.iid) if lecture.iid else None,
            lecture_id=lecture.lecture_id,
            lecture_name=lecture.lecture_name,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=serialize_content(lecture.content),
            order=lecture.order,
        )

    async def get_lectures_by_subject(self, subject_id: str) -> LectureListResponse:
        try:
            lectures = await self.lecture_repo.get_lectures_by_subject(subject_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "get_lectures_by_subject", "error": str(exc)})
        items = [
            LectureResponse(
                _id=str(lecture.iid) if lecture.iid else None,
                lecture_id=lecture.lecture_id,
                lecture_name=lecture.lecture_name,
                subject_id=lecture.subject_id,
                subject_name=lecture.subject_name,
                content=serialize_content(lecture.content),
                order=lecture.order,
            )
            for lecture in lectures
        ]
        return LectureListResponse(items=items)

    async def delete_lecture(self, payload: LectureDeleteByIdRequest) -> DeleteLectureResponse:
        try:
            deleted_count = await self.lecture_repo.delete_by_lecture_id(payload.lecture_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "delete_lecture", "error": str(exc)})
        if deleted_count == 0:
            raise LectureNotFoundError(details={"lecture_id": payload.lecture_id})
        return DeleteLectureResponse(lecture_id=payload.lecture_id, deleted_count=deleted_count)

    async def delete_lectures_by_subject(self, payload: LectureDeleteBySubjectRequest) -> DeleteLectureResponse:
        try:
            deleted_count = await self.lecture_repo.delete_by_subject_id(payload.subject_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "delete_lectures_by_subject", "error": str(exc)})
        if deleted_count == 0:
            raise LectureNotFoundError(details={"subject_id": payload.subject_id})
        return DeleteLectureResponse(subject_id=payload.subject_id, deleted_count=deleted_count)


def get_lecture_service(
    lecture_repo: LectureRepo = Depends(get_lecture_repo),
    doc_intelligence_client: DocumentIntelligenceClient = Depends(get_doc_intelligence_client),
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    settings: Settings = Depends(get_settings),
) -> LectureService:
    

    summary_llm = lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID,
        temperature=0.1,
        top_p=0.85,
    )

    return LectureService(
        lecture_repo=lecture_repo,
        doc_intelligence_client=doc_intelligence_client,
        summary_llm=summary_llm,
    )