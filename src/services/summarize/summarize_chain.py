from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, Runnable
from langchain_openai import ChatOpenAI


SYSTEM_TMPL = """
You are an expert educational assistant specialized in summarizing lecture content.

Your task:
Convert lecture content into a clear, structured, and high-quality summary that helps students understand and revise efficiently.

Strict rules:
- Do NOT add any information not present in the source content
- Do NOT hallucinate or infer external knowledge
- Do NOT repeat sentences verbatim unless necessary for technical accuracy
- Focus only on key concepts and core ideas
- Remove filler, redundancy, and irrelevant details
- Keep structure clear and study-friendly
- Use formal English
- Preserve technical terms as they are
"""


LEVEL_INSTRUCTIONS = {
    0: """
Level: Ultra-Concise Exam Summary

Goal:
Create a fast revision sheet for last-minute exam preparation.

Requirements:
- 3 to 5 bullet points only
- Each bullet = one core idea
- Extremely condensed phrasing
- No explanations, no examples
- Only the most important concepts
- Remove all secondary or supporting details
""",

    1: """
Level: Standard Study Summary

Goal:
Provide a balanced summary for regular study and revision.

Requirements:
- One single paragraph only
- 40–70 words target range
- Capture main ideas and overall meaning
- Include essential concepts only
- No deep explanations or elaboration
- Keep flow natural and readable
""",

    2: """
Level: Detailed Understanding Summary

Goal:
Provide a deep and structured explanation for learning and comprehension.

Requirements:
- 2 to 3 short paragraphs
- Clearly explain main concepts and relationships
- Preserve logical flow of the lecture
- Include key details only if they are important to understanding
- Avoid unnecessary expansion or repetition
- Maintain clarity and educational structure
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

Output rules:
- Return ONLY the final summary
- No titles, no labels, no prefaces
- Clean, structured English text only
"""
        ),
    ]
)


def build_summarize_chain(llm: ChatOpenAI) -> Runnable:

    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        if "lecture_content" not in inputs:
            raise ValueError("lecture_content is required")

        level = int(inputs.get("level", 1))

        level_instruction = LEVEL_INSTRUCTIONS.get(
            level,
            LEVEL_INSTRUCTIONS[1]
        )

        return {
            "lecture_content": inputs["lecture_content"],
            "level_instruction": level_instruction,
        }

    chain = (
        RunnableLambda(prepare_input)
        | PROMPT
        | llm
    )

    return chain