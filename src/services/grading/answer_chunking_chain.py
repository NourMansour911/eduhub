from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List


from pydantic import BaseModel, Field
from typing import List
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate


class AnswerChunk(BaseModel):
    text: str = Field(
        ...,
        description="Atomic meaningful unit from the student's answer. Must be self-contained and evaluable."
    )
    weight: float = Field(
        ...,
        ge=0,
        le=1,
        description="Importance weight of this chunk relative to the full answer."
    )


class AnswerChunkingOutput(BaseModel):
    chunks: List[AnswerChunk] = Field(
        ...,
        description="List of meaningful answer chunks."
    )


chunking_parser = PydanticOutputParser(pydantic_object=AnswerChunkingOutput)


REF_CHUNKING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert educational rubric designer.

Your task is to convert a model (reference) answer into a precise grading rubric by decomposing it into atomic grading units (chunks).

Your output will be used in an automated grading system, so accuracy, clarity, and evaluability are critical.

========================
CORE OBJECTIVE
========================
Extract grading criteria — not explanations.

Each chunk must represent ONE independently assessable marking point that can be checked in a student's answer.

========================
1) CHUNKING RULES
========================
- Each chunk MUST evaluate exactly ONE atomic grading criterion.
- Each chunk represents a single marking point in a rubric.
- Do NOT merge multiple grading criteria into one chunk.
- If a sentence contains multiple distinct ideas → SPLIT them.
- If multiple sentences express the same idea → MERGE them.
- Do NOT split based on sentence boundaries alone — split based on meaning.

========================
2) GRADING-ORIENTED WORDING
========================
- Each chunk MUST be written as a grading criterion, not as an explanation.
- It should be directly usable to assign marks.
- Use concise, objective phrasing.

Good example:
"Defines overfitting as learning noise and failing to generalize"

Bad example:
"Overfitting is when a model learns noise and doesn't generalize"

========================
3) OBSERVABILITY RULE
========================
- Each chunk MUST correspond to something explicitly observable in a student's answer.
- Avoid abstract, implicit, or unverifiable concepts.
- The grader should be able to clearly mark the chunk as:
  correct / incorrect / partially correct

========================
4) GRANULARITY RULES
========================
- Split only when there are distinct grading points.
- Prefer rubric-level decomposition, not linguistic splitting.
- Avoid over-fragmentation into trivial details.
- Each chunk must carry meaningful grading value.

========================
5) WEIGHTING RULES
========================
- Weights represent grading importance (mark distribution).
- The sum of all weights MUST equal exactly 1.0.
- Reflect realistic exam marking logic (not text length).

Weighting guidance:
- Core definition or main concept → 0.30 to 0.40
- Key supporting ideas (causes, mechanisms) → medium weights
- Secondary details (examples, techniques, mitigations) → lower weights

- Do NOT assign high weights to minor or secondary details.
- Ensure weights are balanced and meaningful.

========================
6) REDUNDANCY CONSTRAINT
========================
- No two chunks should evaluate the same underlying concept.
- If overlap exists → MERGE into one chunk.

========================
7) CHUNK COUNT CONTROL
========================
- Target 4–8 chunks for most answers.
- Do NOT exceed 10 chunks unless absolutely necessary.
- Prefer fewer high-quality chunks over many weak ones.

========================
8) STABILITY RULES
========================
- If the answer represents a single concept → return ONE chunk with weight = 1.0
- Do NOT force artificial splitting.

========================
9) EDGE CASE HANDLING
========================
- If the answer is a list → convert each meaningful item into a chunk (if distinct)
- If the answer is shallow → produce fewer, broader chunks

========================
10) OUTPUT RULES
========================
- Return ONLY valid JSON.
- No explanations, no markdown, no extra text.
- Ensure weights sum exactly to 1.0 (fix floating errors if needed).


{format_instructions}
            """,
        ),
        ("human", "{answer}"),
    ]
)

def build_answer_chunking_chain(llm: ChatOpenAI) -> Runnable:
    def prepare_input(inputs: dict):
        return {
            "answer": inputs["answer"],
            "format_instructions": chunking_parser.get_format_instructions(),
        }


    chain = (
        RunnableLambda(prepare_input)
        | REF_CHUNKING_PROMPT
        | llm
        | chunking_parser
        | RunnableLambda(lambda x: x.chunks)
    )
    
    return chain
