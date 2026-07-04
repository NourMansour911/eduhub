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