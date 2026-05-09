from fastapi import Depends
from models import LectureModel
from schemas import LectureStoreRequest, LectureStoreResponse
from services.lectures.lecture_service import LectureService, get_lecture_service
from services.summarize.summarize_service import get_summarize_service, SummarizeService
from helpers import get_logger
from helpers.utils import serialize_content

logger = get_logger(__name__)


class LectureOrchestrator:

    
    def __init__(
        self,
        lecture_service: LectureService,
        summarize_service: SummarizeService,
    ):
        self.lecture_service = lecture_service
        self.summarize_service = summarize_service

    async def store_lecture_with_summaries(self, payload: LectureStoreRequest) -> LectureStoreResponse:

        prepared_content = await self.lecture_service.prepare_lecture_content(payload.url)
        
        

        summaries = await self.summarize_service.generate_all_summaries(prepared_content)
        lecture = LectureModel(
            lecture_id=payload.lecture_id,
            lecture_name=payload.lecture_name,
            subject_id=payload.subject_id,
            subject_name=payload.subject_name,
            summaries=summaries,
            content=prepared_content,
            order=payload.order,
        )
        logger.info(
            f"Generated summaries for lecture {payload.lecture_id}",
            extra={"levels": list(summaries.keys())}
        )

        _ = await self.lecture_service.add_lecture(lecture)
        
        return LectureStoreResponse(status="success", lecture_id=lecture.lecture_id)


def get_lecture_orchestrator(
    lecture_service: LectureService = Depends(get_lecture_service),
    summarize_service: SummarizeService = Depends(get_summarize_service),
) -> LectureOrchestrator:
    return LectureOrchestrator(
        lecture_service=lecture_service,
        summarize_service=summarize_service,
    )
