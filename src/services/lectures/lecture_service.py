import json
from pathlib import Path
from typing import Any

from fastapi import Depends
from langchain_openai import ChatOpenAI
from pymongo.errors import DuplicateKeyError
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat,AnalyzeResult
from integrations.llm import LCOpenAI
from integrations.vector_db import VectorDBInterface
from core.request_dependencies import (
    get_lecture_repo,
    get_doc_intelligence_client,
    get_langchain_client,
    get_vdb_client,
)
from core import Settings, get_settings
from models import LectureModel
from repositories import LectureRepo
from schemas import (
    DeleteLectureResponse,
    DeleteLectureByIdRequest,
    DeleteLectureBycourseIdRequest,
    LectureListResponse,
)
from helpers import get_logger

from .lecture_exceptions import (
    LectureConflictError,
    LectureNotFoundError,
    LectureServiceException,
)

from services.vdb_service.vectordb_service import VDBService, get_vdb_service

logger = get_logger(__name__)


class LectureService:
    def __init__(
        self,
        lecture_repo: LectureRepo,
        doc_intelligence_client: DocumentIntelligenceClient,
        summary_llm: ChatOpenAI,
        vdb_client: VectorDBInterface,
        vdb_service: VDBService,
    ):
        self.lecture_repo = lecture_repo
        self.doc_intelligence_client = doc_intelligence_client
        self.summary_llm = summary_llm
        self.vdb_client = vdb_client
        self.vdb_service = vdb_service

    async def prepare_lecture_content(self, pdf_url: str):

        try:
            
            """ poller = self.doc_intelligence_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(url_source=pdf_url),
                output_content_format=DocumentContentFormat.MARKDOWN,
            )
            analyze_result = poller.result() """

            
            # Load from eduhub_demos folder
            
            projects_root = Path(__file__).parents[4]  # Navigate to d:\training\AI\projects
            json_file = projects_root / "demos" /"eduhub_demos"/ "test_jsons" / "data_mining_azure.json"
            
            with open(json_file, "r", encoding="utf-8") as f:
                result_data = json.load(f)

            analyze_result = AnalyzeResult(result_data)  
            
            return analyze_result
        except Exception as exc:
            raise LectureServiceException(
                details={"operation": "prepare_lecture_content", "error": str(exc), "pdf_url": pdf_url}
            ) from exc


    async def add_lecture(self, lecture: LectureModel):
        try:
            return await self.lecture_repo.add_lecture(lecture)
        except DuplicateKeyError as exc:
            raise LectureConflictError(details={"lecture_id": lecture.lecture_id, "error": str(exc)})
        except Exception as exc:
            raise LectureServiceException(details={"operation": "store_lecture", "error": str(exc)}) from exc

    async def get_lecture(self, lecture_id: str) -> LectureModel:
        try:
            lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "get_lecture", "error": str(exc)}) from exc
        if not lecture:
            raise LectureNotFoundError(details={"lecture_id": lecture_id})

        return lecture

    async def get_lecture_content(self, lecture_id: str) -> str:
        try:
            lecture = await self.get_lecture(lecture_id)
            return lecture.content
        except LectureNotFoundError:
            raise
        except Exception as exc:
            raise LectureServiceException(
                details={"operation": "get_lecture_content", "lecture_id": lecture_id, "error": str(exc)}
            ) from exc

    async def get_lectures_by_course(self, course_id: str) -> LectureListResponse:
        try:
            lectures = await self.lecture_repo.get_lectures_by_course(course_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "get_lectures_by_course", "error": str(exc)}) from exc
        return LectureListResponse(items=lectures)

    async def delete_lecture(self, payload: DeleteLectureByIdRequest) -> DeleteLectureResponse:
        try:
            deleted_count = await self.lecture_repo.delete_by_lecture_id(payload.lecture_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "delete_lecture", "error": str(exc)}) from exc
        if deleted_count == 0:
            raise LectureNotFoundError(details={"lecture_id": payload.lecture_id})

        try:
            self.vdb_client.delete_by_filter(
                collection_name="lectures",
                filters=[{"field": "lecture_id", "value": payload.lecture_id, "op": "eq"}],
            )
        except Exception as exc:
            logger.warning(
                "Failed to delete lecture vectors",
                extra={"lecture_id": payload.lecture_id, "error": str(exc)},
            )
        return DeleteLectureResponse( deleted_count=deleted_count)

    async def delete_lectures_by_course(self, payload: DeleteLectureBycourseIdRequest) -> DeleteLectureResponse:
        try:
            deleted_count = await self.lecture_repo.delete_by_course_id(payload.course_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "delete_lectures_by_course", "error": str(exc)}) from exc
        if deleted_count == 0:
            raise LectureNotFoundError(details={"course_id": payload.course_id})

        try:
            self.vdb_client.delete_by_filter(
                collection_name="lectures",
                filters=[{"field": "course_id", "value": payload.course_id, "op": "eq"}],
            )
        except Exception as exc:
            logger.warning(
                "Failed to delete course vectors",
                extra={"course_id": payload.course_id, "error": str(exc)},
            )
        return DeleteLectureResponse(deleted_count=deleted_count)

    


def get_lecture_service(
    lecture_repo: LectureRepo = Depends(get_lecture_repo),
    doc_intelligence_client: DocumentIntelligenceClient = Depends(get_doc_intelligence_client),
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    vdb_client: VectorDBInterface = Depends(get_vdb_client),
    vdb_service: VDBService = Depends(get_vdb_service),
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
        vdb_client=vdb_client,
        vdb_service=vdb_service,
    )