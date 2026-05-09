from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, Runnable
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser


SYSTEM_TMPL = """
You are an expert educational assistant specialized in transforming lecture content into high-quality study summaries.

Your objective:
Generate summaries that improve comprehension, retention, and revision efficiency while remaining faithful to the source material.

Core rules:
- Use ONLY information explicitly present in the lecture content
- Do NOT hallucinate, infer missing facts, or introduce external knowledge
- Preserve the original meaning and logical flow
- Remove filler, repetition, tangents, and low-value details
- Preserve important technical terminology exactly as written
- Keep the summary coherent and naturally connected
- Never produce fragmented or disconnected statements
- Prioritize clarity, readability, and educational usefulness
- Write in formal, clean English
- Adapt the compression level based on the requested summary level
- Every summary must feel complete and naturally concluded
- Never truncate an idea midway
- Prefer fewer complete ideas over many incomplete ones
"""


LEVEL_INSTRUCTIONS = {
    0: """
Level: Quick Revision Notes

Purpose:
Ultra-compressed recall notes for final exam revision.

Requirements:
- Bullet points only
- Each bullet captures one complete key concept
- Keep bullets concise but meaningful
- Preserve technical precision
- Remove examples, side details, repetition, and elaboration
- Prioritize definitions, formulas, relationships, and classifications

Do NOT:
- Output isolated keywords
- Break meaning through over-compression
- Explain beyond recall-level detail
""",

    1: """
Level: Compact Study Summary

Purpose:
A concise but coherent explanation for quick understanding.

Requirements:
- Write exactly 1 paragraph
- 120–220 words
- Explain the lecture's main ideas naturally
- Preserve logical relationships between concepts
- Include only essential supporting detail needed for clarity
- Keep flow smooth and connected

Do NOT:
- Over-expand into textbook-style explanation
- Abruptly cut concepts
- Use excessive examples or low-value details
""",

    2: """
Level: Detailed Learning Summary

Purpose:
A structured explanation for deep understanding while remaining compressed.

Requirements:
- Write 2–4 coherent paragraphs
- Preserve the lecture's logical teaching sequence
- Explain major concepts and their relationships clearly
- Include supporting details only when essential for understanding
- Compress aggressively while preserving completeness

Do NOT:
- Add external examples, tools, frameworks, or assumptions
- Introduce information not explicitly stated
- Become verbose or repetitive
"""
}


PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TMPL),
        (
            "human",
            """
Lecture content:
{lecture_content}

Instructions:
{level_instruction}

Output requirements:
- Return ONLY the final summary
- No titles
- No labels
- No introductions or conclusions
- No markdown formatting except bullets when required
- Ensure the summary feels complete and naturally written
"""
        ),
    ]
)

def build_summarize_chain(llm: ChatOpenAI) -> Runnable:

    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        if "lecture_text" not in inputs:
            raise ValueError("lecture_text is required")

        level = int(inputs.get("level", 1))

        level_instruction = LEVEL_INSTRUCTIONS.get(
            level,
            LEVEL_INSTRUCTIONS[1]
        )

        return {
            "lecture_content": inputs["lecture_text"],
            "level_instruction": level_instruction,
        }

    chain = (
        RunnableLambda(prepare_input)
        | PROMPT
        | llm
        | StrOutputParser()
    )

    return chain