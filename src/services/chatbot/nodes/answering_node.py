from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI

from helpers.logger import get_chatbot_logger
from integrations.redis_provider import RedisProvider
from ..states import ChatbotState
from ..utils import format_nested_step_outputs, format_messages_history

logger = get_chatbot_logger(__name__)


class AnsweringNode:
    STATIC_SYSTEM_PROMPT = """
You are Luma, an enthusiastic, warm, and Socratic educational mentor. Your goal is to guide students, facilitate their learning, and answer their academic queries. 

As a Socratic mentor:
- Do not just dump dry facts or short answers. Encourage understanding, use helpful real-world analogies where appropriate, and break down complex concepts step-by-step.
- Conclude your response with a friendly, interactive follow-up question that prompts the student to verify their understanding or expand on the topic.

IMPORTANT Rules:
1. Scope Control: If the user's query is completely off-topic or unrelated to the educational platform, courses, lectures, academic questions, or academic regulations (excluding greetings or sharing learning preferences), you must politely decline.
2. Context Quoting (CRITICAL): When answering a query based on the retrieved context, you MUST first quote the exact relevant snippet(s) of the retrieved text from which you extracted the information. Quote them exactly as they appear in the source context, verbatim, and do not modify or translate them. Under a clear section called "Reference Context:", list these raw verbatim snippets (even if they are in a language different from the student's language, such as Arabic).
3. Student Language: After citing the verbatim reference context, proceed to explain, elaborate, and answer the student's query in their preferred language (e.g. if the student asks in Arabic, answer and explain in Arabic; if they ask in English, answer and explain in English).
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
Student Persona:
{user_persona}

Session Summary:
{session_summary}

Enrolled Courses:
{student_courses}

Retrieved Context (Verbatim Sources):
{retrieved_context}

Previous Turns Step Outputs:
{previous_steps_outputs}
"""

    def __init__(
        self,
        llm_map: Dict[str, ChatOpenAI],
        redis_provider: RedisProvider,
    ):
        self.llm: ChatOpenAI = llm_map["answering"]
        self.redis_provider = redis_provider

    async def __call__(self, state: ChatbotState) -> Dict[str, Any]:
        if state.rag_status == "failed":
            return {
                "response": f"Sorry, I encountered an issue while searching the databases: {state.rag_error_message}. Let me know if you would like me to try again or discuss something else!"
            }
        if state.rag_status == "clarification":
            return {"response": state.rag_clarification_question}

        messages_history_str = format_messages_history(state.messages_history)
        session_summary_str = state.session_summary or "No session summary."
        prev_steps_str = format_nested_step_outputs(state.previous_steps_outputs)

        logger.info(
            "AnsweringNode Luma run. Query: %s | Persona: %s | Summary: %s",
            state.user_query,
            state.user_persona,
            session_summary_str,
        )

        static_system_content = self.STATIC_SYSTEM_PROMPT
        dynamic_context_content = self.DYNAMIC_CONTEXT_TEMPLATE.format(
            user_persona=state.user_persona or "General friendly student.",
            session_summary=session_summary_str,
            student_courses=state.student_courses or "No enrolled courses.",
            retrieved_context=state.retrieved_context or "No retrieved context.",
            previous_steps_outputs=prev_steps_str,
        )

        messages = [
            SystemMessage(content=static_system_content)
        ]

        # Add message history
        for msg in state.messages_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "Human":
                messages.append(HumanMessage(content=content))
            elif role == "AI":
                messages.append(AIMessage(content=content))

        # Add the dynamic retrieved context and session data
        messages.append(SystemMessage(content=dynamic_context_content))
        # Add the current user query
        messages.append(HumanMessage(content=state.user_query))

        response = await self.llm.ainvoke(messages)

        final_response_text = str(response.content).strip()
        logger.info("Luma final answer: %s", final_response_text)

        return {
            "response": final_response_text,
        }
