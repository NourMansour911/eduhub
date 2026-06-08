from models import AnswerModel
from repositories.answer_repo import AnswerRepo
from schemas import RefGradingRequest, RefGradingResponse
from services.grading.grading_exceptions import InvalidReferenceAnswerError


class SetReferenceService:
    def __init__(self, answer_repo: AnswerRepo):
        self.answer_repo = answer_repo

    async def store_reference(self, payload: RefGradingRequest) -> RefGradingResponse:
        if not payload.answer or not payload.answer.strip():
            raise InvalidReferenceAnswerError()
        if not payload.question_text or not payload.question_text.strip():
            raise InvalidReferenceAnswerError()

        answer_model = AnswerModel(
            question=payload.question_text.strip(),
            text=payload.answer.strip(),
            word_count=len(payload.answer.split()),
        )
        inserted_id = await self.answer_repo.add_answer(answer_model)
        return RefGradingResponse(question_id=str(inserted_id))

