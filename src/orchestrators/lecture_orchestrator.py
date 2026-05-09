from fastapi import Depends
from repositories import LectureRepo
from core.request_dependencies import get_lecture_repo
from models import LectureModel
from schemas import LectureStoreRequest, LectureResponse
from services.lectures.lecture_service import LectureService, get_lecture_service
from services.summarize.summarize_service import get_summarize_service, SummarizeService
from helpers import get_logger
from pymongo.errors import DuplicateKeyError
from services.lectures.lecture_exceptions import (
    LectureConflictError,
    LectureServiceException,
)
from helpers.utils import serialize_content

logger = get_logger(__name__)


class LectureOrchestrator:

    
    def __init__(
        self,
        lecture_repo: LectureRepo,
        lecture_service: LectureService,
        summarize_service: SummarizeService,
    ):
        self.lecture_repo = lecture_repo
        self.lecture_service = lecture_service
        self.summarize_service = summarize_service

    async def store_lecture_with_summaries(self, payload: LectureStoreRequest) -> LectureResponse:

        prepared_content = await self.lecture_service.prepare_lecture_content(payload.url)
        

        lecture = LectureModel(
            lecture_id=payload.lecture_id,
            lecture_name=payload.lecture_name,
            subject_id=payload.subject_id,
            subject_name=payload.subject_name,
            content=prepared_content,
            order=payload.order,
        )
        

        try:
            summaries = await self.summarize_service.generate_all_summaries(lecture)
            lecture.summaries = summaries
            logger.info(
                f"Generated summaries for lecture {payload.lecture_id}",
                extra={"levels": list(summaries.keys())}
            )
        except Exception as exc:
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
    lecture_service: LectureService = Depends(get_lecture_service),
    summarize_service: SummarizeService = Depends(get_summarize_service),
) -> LectureOrchestrator:
    return LectureOrchestrator(
        lecture_repo=lecture_repo,
        lecture_service=lecture_service,
        summarize_service=summarize_service,
    )
