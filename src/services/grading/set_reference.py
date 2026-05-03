from fastapi import Depends

from core.request_dependencies import get_answer_repo
from models import AnswerModel
from repositories import AnswerRepo
from schemas import RefGradingRequest, RefGradingResponse
from services.grading.grading_exceptions import InvalidReferenceAnswerError


class SetReferenceService:
    def __init__(self, answer_repo: AnswerRepo):
        self.answer_repo = answer_repo

    async def store_reference(self, payload: RefGradingRequest) -> RefGradingResponse:
        if not payload.answer or not payload.answer.strip():
            raise InvalidReferenceAnswerError()

        answer_model = AnswerModel(
            text=payload.answer.strip(),
            word_count=len(payload.answer.split()),
        )
        inserted_id = await self.answer_repo.add_answer(answer_model)
        return RefGradingResponse(question_id=str(inserted_id))


def get_set_reference_service(answer_repo: AnswerRepo = Depends(get_answer_repo)) -> SetReferenceService:
    return SetReferenceService(answer_repo=answer_repo)
