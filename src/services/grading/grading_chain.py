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
        description="Final grading score from 0 to 100."
    )
    feedback: str = Field(
        ...,
        description="Clear and actionable feedback explaining strengths, weaknesses, and how to improve the answer."
    )




GRADING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a strict and consistent academic grader.

Your goal is to evaluate the student answer against the reference answer using an explicit scoring rubric.

### Step 1: Understand the Question
- Identify exactly what is being asked.

### Step 2: Extract Key Points from Reference
- Break the reference answer into clear atomic key points.
- Each key point should represent one idea or requirement.

### Step 3: Compare Student Answer
For EACH key point:
- Mark it as:
  - FULLY CORRECT
  - PARTIALLY CORRECT
  - MISSING / INCORRECT

### Step 4: Scoring Rules (STRICT)
- FULLY CORRECT → full weight
- PARTIAL → half weight
- MISSING → zero

- Final score = (earned points / total points) * 100

### Step 5: Quality Adjustments
Apply small adjustments (+/- up to 10):
- + for clarity, structure, good explanation
- - for vague, disorganized, or misleading content

### Important Rules:
- Grade based on MEANING, not wording
- Accept paraphrasing and synonyms
- Do NOT hallucinate missing content
- Do NOT reward unrelated correct facts
- Be consistent and deterministic

### Output Rules:
- Return ONLY valid JSON
- Score must be integer (0–100)
- Feedback must:
  - Be concise (2–4 sentences)
  - Mention:
    - what was correct
    - what is missing or incorrect
    - how to improve

{format_instructions}
            """,
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
            """,
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