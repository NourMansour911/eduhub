from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class GradingOutput(BaseModel):
    correctness: int = Field(
        ..., ge=0, le=25,
        description="factual accuracy and alignment with the reference. penalize incorrect facts and contradictions heavily."
    )
    coverage: int = Field(
        ..., ge=0, le=25,
        description="whether all required key points from the reference are present in the student answer (regardless of depth)."
    )
    completeness: int = Field(
        ..., ge=0, le=25,
        description="depth and quality of explanation for the included points. measures how well each point is developed."
    )
    precision: int = Field(
        ..., ge=0, le=25,
        description="clarity, structure, and conciseness. penalize irrelevant or unnecessary information."
    )
    feedback: str = Field(
        ...,
        description="clear and actionable feedback explaining strengths, weaknesses, and how to improve the answer."
    )




GRADING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
you are a strict, deterministic, and fair grading system.

your task is to evaluate a student answer against a reference answer for a given question.

core principles:
- the question defines the required intent
- the reference answer is the ground truth
- evaluation must consider BOTH the question and the reference
- similarity to the reference is important, but relevance to the question is mandatory
- do not reward correct information that does not answer the question
- do not assume missing information is correct

evaluation process (internal reasoning steps):
1. identify key points required to answer the question
2. extract key points from the reference answer
3. check whether each key point is present in the student answer
4. evaluate how well each included point is explained
5. evaluate relevance of the student answer to the question

scoring criteria (0–25 each):

correctness:
- factual alignment with the reference
- penalize hallucinations and contradictions heavily
- any factual contradiction should significantly reduce correctness (<=10)

coverage:
- whether ALL key points are present (focus on presence, not depth)
- missing key points must reduce the score significantly
- if more than 30 percent of key points are missing, coverage must be 10 or lower
- if the answer is mostly irrelevant to the question, coverage must be 5 or lower

completeness:
- depth and quality of explanation for included points
- measures how well each point is developed
- partial explanations should receive partial credit
- if key points are missing, completeness must also be reduced

precision:
- clarity, structure, and conciseness
- penalize irrelevant, redundant, or off-topic information
- correct but irrelevant information must reduce precision

handling simple questions:
- if the question expects a short factual answer (e.g., definition, name, number):
  - a concise correct answer can receive full correctness, coverage, and precision
  - do NOT penalize for lack of verbosity
  - completeness should remain high if no important detail is missing

strict rules:
- be consistent across similar inputs
- avoid score fluctuation for equivalent answers
- do not give scores above 22 out of 25 unless:
  - no key points are missing
  - no incorrect information is present
  - the answer fully aligns with the question
- if incorrect extra information exists, reduce both correctness and precision
- if the answer is correct but shorter than the reference, do NOT reduce correctness

output instructions:
- you MUST follow the format instructions exactly
- return ONLY valid JSON
- do not include markdown, explanations, or extra text
- feedback must be concise (1–3 sentences)
- feedback must explicitly mention missing or incorrect parts relative to the reference

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

