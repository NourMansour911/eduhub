from typing import Dict, Any, Optional, Union
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, Runnable
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser


SYSTEM_MSG = """
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
Level: Comprehensive Quick Revision

Purpose:
A high-density, structured summary for rapid review, focusing on core pillars without sacrificing conceptual accuracy.

Requirements:
- Structure: Clear, high-impact bullet points (strictly 4 to 6 bullets).
- Content: Each bullet must be a complete, self-contained analytical sentence capturing a core concept, key definitions, or fundamental relationships.
- Logical Continuity: The sequence of bullets must reflect the core narrative of the lecture, ensuring no conceptual gaps.
- Depth: Omit minor examples and conversational filler, but retain all critical technical terminology and essential formulas/rules.
- Word Count: Aim for 80–130 words to ensure adequate depth for a reliable quick review.

Do NOT:
- Output shallow fragments or isolated keywords.
- Sacrifice the clarity or correctness of a definition for the sake of brevity.
""",

    1: """
Level: Core Concept Summary

Purpose:
A cohesive, single-paragraph summary providing a well-structured overview of the lecture's primary framework.

Requirements:
- Structure: Exactly 1 well-developed, continuous paragraph.
- Content: Synthesize the main arguments, methodologies, and conclusions into a fluid narrative.
- Logical Continuity: Use strong transitional phrasing to show cause-and-effect or sequential relationships between concepts.
- Depth: Include necessary context and primary supporting details that make the concept fully understandable on its own.
- Word Count: Strictly 160–260 words, ensuring it serves as a robust standalone study reference.

Do NOT:
- Use bullet points, subheadings, or lists.
- Abruptly transition between ideas or leave main concepts partially explained.
""",

    2: """
Level: Detailed Learning & Analysis Summary

Purpose:
An exhaustive, multi-paragraph educational reference that mirrors the depth and sequence of the original material.

Requirements:
- Structure: 3 to 5 structured paragraphs, organized logically around major thematic shifts in the lecture.
- Content: Fully map out every significant concept, its underlying mechanism, practical implications, and relevant classifications.
- Logical Continuity: Build a thorough, end-to-end academic narrative that flows naturally from introduction to advanced details.
- Depth: Retain all essential nuances, structural relationships, and technical distinctions while stripping out only true redundancies and non-educational filler.
- Word Count: 350–550 words, serving as a primary substitute for the full lecture text during deep revision.

Do NOT:
- Compress to the point of omitting secondary but important technical nuances.
- Introduce external frameworks, assumptions, or tools not explicitly mentioned in the source text.
"""
}


def build_context_msg_for_level(level: int) -> str:
    level_instruction = LEVEL_INSTRUCTIONS.get(level, LEVEL_INSTRUCTIONS[1]).strip()
    return f"""Lecture content:
{{lecture_content}}

Instructions:
{level_instruction}

Output requirements:
- Return ONLY the final summary
- No titles
- No labels
- No introductions or conclusions
- No markdown formatting except bullets when required
- Ensure the summary feels complete and naturally written"""


CONTEXT_MSG_LEVEL0 = build_context_msg_for_level(0)
CONTEXT_MSG_LEVEL1 = build_context_msg_for_level(1)
CONTEXT_MSG_LEVEL2 = build_context_msg_for_level(2)

CONTEXT_MSG = CONTEXT_MSG_LEVEL1

SUMMARIZE_LEVEL0_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_MSG),
        ("human", CONTEXT_MSG_LEVEL0),
    ]
)

SUMMARIZE_LEVEL1_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_MSG),
        ("human", CONTEXT_MSG_LEVEL1),
    ]
)

SUMMARIZE_LEVEL2_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_MSG),
        ("human", CONTEXT_MSG_LEVEL2),
    ]
)

PROMPTS: Dict[int, ChatPromptTemplate] = {
    0: SUMMARIZE_LEVEL0_PROMPT,
    1: SUMMARIZE_LEVEL1_PROMPT,
    2: SUMMARIZE_LEVEL2_PROMPT,
}

PROMPT = SUMMARIZE_LEVEL1_PROMPT


def build_summarize_chain_for_level(
    llm: ChatOpenAI,
    level: int = 1,
    prompt: Optional[ChatPromptTemplate] = None,
) -> Runnable:
    prompt_to_use = prompt or PROMPTS.get(level, SUMMARIZE_LEVEL1_PROMPT)

    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        lecture_text = inputs.get("lecture_text") or inputs.get("lecture_content")
        if not lecture_text:
            raise ValueError("lecture_text is required")
        return {"lecture_content": lecture_text}

    chain = (
        RunnableLambda(prepare_input)
        | prompt_to_use
        | llm
        | StrOutputParser()
    )

    return chain


def build_summarize_chains(
    llm: ChatOpenAI,
    prompts: Optional[Dict[Any, ChatPromptTemplate]] = None,
) -> Dict[int, Runnable]:
    prompts = prompts or {}
    chains: Dict[int, Runnable] = {}

    for level in [0, 1, 2]:
        p = (
            prompts.get(level)
            or prompts.get(str(level))
            or prompts.get(f"summarize-level{level}")
        )
        chains[level] = build_summarize_chain_for_level(llm, level=level, prompt=p)

    return chains


def build_summarize_chain(
    llm: ChatOpenAI,
    prompt: Optional[ChatPromptTemplate] = None,
) -> Runnable:
    return build_summarize_chain_for_level(llm, level=1, prompt=prompt)