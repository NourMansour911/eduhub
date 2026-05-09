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
You are a senior university professor grading student exam answers.

Your grading behavior must simulate real human grading distribution.

CRITICAL PRINCIPLES:

1. You MUST use the full 0–100 scale realistically:
   - Excellent answers are rare (10–20%)
   - Average answers are common (40–60%)
   - Poor answers are also common

2. Do NOT compress scores toward the middle.
   You must clearly separate weak, medium, and strong answers.

3. Grading must be based on concept coverage, not writing style.

---------------------------------------
GRADING METHOD (MANDATORY):

Step 1: Extract key concepts from the reference answer.

Step 2: For each concept, classify student performance:
- Fully correct
- Partially correct
- Missing
- Incorrect

Step 3: Compute score using this strict mapping:

- 100–90 → all key concepts correct
- 80–89 → almost all concepts correct, minor missing detail
- 70–79 → most concepts correct, 1 important missing concept
- 60–69 → mixed correctness, multiple missing concepts
- 50–59 → partial understanding, missing half or more concepts
- 40–49 → weak understanding, few correct ideas
- 30–39 → minimal understanding
- 10–29 → very poor understanding
- 0 → irrelevant or contradiction

Step 4: You MUST ensure score separation:
- If two answers differ in coverage, their scores MUST differ significantly (at least 10–20 points).

Step 5: Decide final score BEFORE writing feedback.

---------------------------------------
CRITICAL RULES:

- Never default to 0.5 / 0.6 / 0.7 style clustering
- Never be "nice grader"
- Be strict and realistic like a human professor
- Fully correct answers must be rare
- Partial answers must not be over-scored

---------------------------------------

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

    )

    return chain