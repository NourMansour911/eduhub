"""Lecture storage orchestrator that coordinates multiple services."""
from fastapi import Depends
from langchain_openai import ChatOpenAI

from core.request_dependencies import get_doc_intelligence_client, get_langchain_client
from core import Settings, get_settings
from repositories import LectureRepo
from core.request_dependencies import get_lecture_repo
from models import LectureModel
from schemas import LectureStoreRequest, LectureResponse
from services.lectures.lecture_service import LectureService
from services.summarize.summarize_service import generate_all_summaries
from integrations.llm import LCOpenAI
from helpers import get_logger
from azure.ai.documentintelligence import DocumentIntelligenceClient
from pymongo.errors import DuplicateKeyError
from services.lectures.lecture_exceptions import (
    LectureConflictError,
    LectureServiceException,
)
from utils import serialize_content

logger = get_logger(__name__)


class LectureOrchestrator:
    """
    Orchestrates lecture creation with automatic summary generation.
    Coordinates between LectureService and SummarizeService.
    """
    
    def __init__(
        self,
        lecture_repo: LectureRepo,
        doc_intelligence_client: DocumentIntelligenceClient,
        lc_openai_client: LCOpenAI,
        settings: Settings,
    ):
        self.lecture_repo = lecture_repo
        self.doc_intelligence_client = doc_intelligence_client
        self.lc_openai_client = lc_openai_client
        self.settings = settings
        
        # Initialize LLM for summaries
        self.llm: ChatOpenAI = lc_openai_client.get_langchain_llm(
            model=settings.GENERATION_MODEL_ID,
            temperature=0.1,
            top_p=0.85
        )
        
        # Create lecture service instance
        self.lecture_service = LectureService(
            lecture_repo=lecture_repo,
            doc_intelligence_client=doc_intelligence_client,
            lc_openai_client=lc_openai_client,
            settings=settings,
        )

    async def store_lecture_with_summaries(self, payload: LectureStoreRequest) -> LectureResponse:
        """
        Store lecture and generate all summaries in parallel.
        
        Flow:
        1. Prepare lecture content
        2. Create LectureModel
        3. Generate summaries (0, 1, 2) in parallel
        4. Save to database
        5. Return response
        """
        # Prepare content
        prepared_content = await self.lecture_service.prepare_lecture_content(payload.url)
        
        # Create lecture model
        lecture = LectureModel(
            lecture_id=payload.lecture_id,
            lecture_name=payload.lecture_name,
            subject_id=payload.subject_id,
            subject_name=payload.subject_name,
            content=prepared_content,
            order=payload.order,
        )
        
        # Generate all summaries in parallel
        try:
            summaries = await generate_all_summaries(lecture, self.llm)
            lecture.summaries = summaries
            logger.info(
                f"Generated summaries for lecture {payload.lecture_id}",
                extra={"levels": list(summaries.keys())}
            )
        except Exception as exc:
            # Log warning but don't fail - lecture can be stored without summaries
            logger.warning(
                f"Failed to generate summaries for lecture {payload.lecture_id}, storing without them",
                extra={"error": str(exc), "lecture_id": payload.lecture_id},
            )
        
        # Store lecture with summaries in database
        try:
            inserted_id = await self.lecture_repo.add_lecture(lecture)
        except DuplicateKeyError as exc:
            raise LectureConflictError(details={"lecture_id": lecture.lecture_id, "error": str(exc)})
        except Exception as exc:
            raise LectureServiceException(details={"operation": "store_lecture", "error": str(exc)})
        
        # Return response
        return LectureResponse(
            _id=str(inserted_id),
            lecture_id=lecture.lecture_id,
            lecture_name=lecture.lecture_name,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=serialize_content(lecture.content),
            order=lecture.order,
        )


def get_lecture_orchestrator(
    lecture_repo: LectureRepo = Depends(get_lecture_repo),
    doc_intelligence_client: DocumentIntelligenceClient = Depends(get_doc_intelligence_client),
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    settings: Settings = Depends(get_settings),
) -> LectureOrchestrator:
    """Dependency injection for LectureOrchestrator."""
    return LectureOrchestrator(
        lecture_repo=lecture_repo,
        doc_intelligence_client=doc_intelligence_client,
        lc_openai_client=lc_openai_client,
        settings=settings,
    )
