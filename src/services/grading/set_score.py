from fastapi import Depends
from langchain_openai import ChatOpenAI
from typing import List, Dict, Any, Optional
from langchain_core.runnables import Runnable, RunnableConfig
from bson.errors import InvalidId

from core.request_dependencies import get_answer_repo
from repositories import AnswerRepo
from schemas import GradingRequest, GradingResponse, BatchGradingRequest, BatchGradingResponse
from services.grading.grading_exceptions import (
    InvalidStudentAnswerError,
    ReferenceAnswerNotFoundError,
    GradingProcessingError,
)
from services.grading.grading_chain import build_requery_chain, GradingOutput
from models import AnswerModel
from integrations.llm import LCOpenAI
from core import Settings, get_langchain_client, get_settings

class SetScoreService:
    def __init__(self, answer_repo: AnswerRepo, settings: Settings, lc_openai_client: LCOpenAI) -> None:
        self.answer_repo: AnswerRepo = answer_repo
        self.llm: ChatOpenAI = lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, top_p=0.1,temperature=0.0)


    async def batch_grade(self, payload: BatchGradingRequest) -> BatchGradingResponse:

        results: List[GradingResponse] = []
        
        try:

            references: Dict[str, AnswerModel] = {}
            for item in payload.items:
                reference_answer: Optional[AnswerModel] = await self.answer_repo.get_answer(item.question_id)
                if reference_answer is None:
                    raise ReferenceAnswerNotFoundError(question_id=item.question_id)
                references[item.question_id] = reference_answer
            

            inputs: List[Dict[str, Any]] = []
            configs: List[RunnableConfig] = []
            
            for item in payload.items:
                ref: AnswerModel = references[item.question_id]
                inputs.append({
                    "question": ref.question,
                    "reference_answer": ref.text.strip(),
                    "student_answer": item.answer.strip(),
                })
                

                config: RunnableConfig = RunnableConfig(
                    run_name=f"grade_batch_run",
                    metadata={
                        "question_id": item.question_id,
                        "batch_type": "essay_grading",
                    },
                    tags=["batch_grading", "essay"],
                )
                configs.append(config)
            

            grading_chain: Runnable = build_requery_chain(self.llm)
            grading_outputs: List[GradingOutput] = await grading_chain.abatch(inputs, config=configs)
            
 
            for item, output in zip(payload.items, grading_outputs):
                ref: AnswerModel = references[item.question_id]
                total_score: float = output.score / 100.0
                if total_score < payload.threshold:
                    total_score = 0.0
                
                results.append(GradingResponse(
                    question_id=item.question_id,
                    score=total_score,
                    feedback=output.feedback,
                    reference_answer=ref.text.strip(),
                    student_answer=item.answer.strip(),
                ))
        
        except Exception as e:
            raise GradingProcessingError(
                message="Batch grading processing failed",
                details={"error": str(e)}
            )
        
        return BatchGradingResponse(results=results)


def get_set_score_service(
    answer_repo: AnswerRepo = Depends(get_answer_repo),
    settings: Settings = Depends(get_settings),
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
) -> SetScoreService:
    return SetScoreService(answer_repo=answer_repo, settings=settings, lc_openai_client=lc_openai_client)