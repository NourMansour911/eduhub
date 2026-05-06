import logging
from typing import Dict, Any, List

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, Runnable
from langchain_core.output_parsers import PydanticOutputParser


from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

class GradingOutput(BaseModel):
    score: int = Field(
        ..., ge=0, le=100,
        description="Final grading score from 0 to 100 (multiples of 10 preferred)."
    )
    feedback: str = Field(
        ...,
        description="Short feedback (1–2 sentences, max 25 words) mentioning the main missing or incorrect points only."
    )


GRADING_PROMPT = ChatPromptTemplate.from_messages(
[
(
"system",
"""
You are a strict grader.

Evaluate ONLY how much the student answer matches the reference answer in meaning.

Rules:
- Do NOT add information
- Do NOT assume missing parts are correct
- Accept correct paraphrasing
- Penalize only missing or incorrect ideas

Scoring:

1) Hard gates (apply FIRST):
- If answer is irrelevant or contradicts the reference → score = 0
- If most key ideas are missing → score ≤ 30

2) Otherwise:
- Start from 100
- Subtract:
  - major missing/incorrect idea → -40
  - minor missing detail → -15

3) Clamp between 0 and 100
4) Prefer multiples of 10

Critical:
- Determine the score FIRST
- Be conservative: if unsure, choose the LOWER score
- Do NOT change score after writing feedback

Feedback rules:
- 1–2 short sentences (max 25 words)
- Mention only the main missing or incorrect parts

Output rules:
- Return ONLY valid JSON
{format_instructions}
"""
),
(
"human",
"""
QUESTION:
{question}

REFERENCE ANSWER:
{reference_answer}

STUDENT ANSWER:
{student_answer}
"""
),
]
)

parser = PydanticOutputParser(pydantic_object=GradingOutput)

def build_requery_chain(llm: ChatOpenAI) -> Runnable:

    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "question": inputs["question"],
            "reference_answer": inputs["reference_answer"],
            "student_answer": inputs["student_answer"],
            "format_instructions": parser.get_format_instructions()
        }

    chain = (
        RunnableLambda(prepare_input)
        | GRADING_PROMPT
        | llm
        | parser
        | RunnableLambda(lambda x: x)
    )

    return chain