from difflib import SequenceMatcher

from fastapi import Depends

from core.request_dependencies import get_answer_repo
from repositories import AnswerRepo
from schemas import GradingRequest, GradingResponse
from services.grading.grading_exceptions import (
    InvalidStudentAnswerError,
    ReferenceAnswerNotFoundError,
)


class SetScoreService:
    def __init__(self, answer_repo: AnswerRepo):
        self.answer_repo = answer_repo

    async def set_score(self, payload: GradingRequest) -> GradingResponse:
        if not payload.answer or not payload.answer.strip():
            raise InvalidStudentAnswerError()

        reference_answer = await self.answer_repo.get_answer(payload.question_id)
        if reference_answer is None:
            raise ReferenceAnswerNotFoundError(question_id=payload.question_id)

        normalized_reference = reference_answer.text.strip()
        normalized_student = payload.answer.strip()
        score = SequenceMatcher(
            None,
            normalized_reference.lower(),
            normalized_student.lower(),
        ).ratio()

        feedback = "Exact match" if score == 1 else "Automatic similarity-based score"

        return GradingResponse(
            score=score,
            feedback=feedback,
            reference_answer=normalized_reference,
            student_answer=normalized_student,
        )


def get_set_score_service(answer_repo: AnswerRepo = Depends(get_answer_repo)) -> SetScoreService:
    return SetScoreService(answer_repo=answer_repo)