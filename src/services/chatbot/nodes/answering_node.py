from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_openai import ChatOpenAI

from helpers.logger import get_chatbot_logger
from integrations.redis_provider import RedisProvider
from ..states import ChatbotState
from ..utils import format_nested_step_outputs, format_messages_history
from ..chains.summary_chain import build_summary_chain
from ..chains.persona_chain import build_persona_chain
from ..tools.agent_tools import create_update_persona_tool, create_update_summary_tool

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
4. Tool Usage: You have access to tools to update the student's persona profile and update the session summary. Call them when appropriate (e.g. when the student shares preferences or when summarizing the latest turn).
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
Student Persona:
{user_persona}

Session Summary:
{session_summary}

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
        self.persona_chain = build_persona_chain(llm_map["persona"])
        self.summary_chain = build_summary_chain(llm_map["summary"])

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

        updated_state = {
            "user_persona": state.user_persona,
            "session_summary": state.session_summary,
        }

        async def update_persona_callback(new_persona: str):
            logger.info("Persona update tool callback triggered with: %s", new_persona)
            updated_state["user_persona"] = new_persona
            collection = await self.redis_provider.get_collection(user_id=state.student_id, session_id=state.session_id)
            if collection:
                collection.persona = new_persona
                await self.redis_provider.save_collection(collection, session_id=state.session_id)

        async def update_summary_callback(new_summary: str):
            logger.info("Summary update tool callback triggered with: %s", new_summary)
            updated_state["session_summary"] = new_summary
            collection = await self.redis_provider.get_collection(user_id=state.student_id, session_id=state.session_id)
            if collection:
                collection.summary = new_summary
                await self.redis_provider.save_collection(collection, session_id=state.session_id)

        summary_tool = create_update_summary_tool(
            summary_chain=self.summary_chain,
            old_summary=session_summary_str,
            callback=update_summary_callback,
        )
        persona_tool = create_update_persona_tool(
            persona_chain=self.persona_chain,
            current_persona=state.user_persona or "General friendly student.",
            messages_history=messages_history_str,
            user_query=state.user_query,
            callback=update_persona_callback,
        )

        tools = [summary_tool, persona_tool]
        tools_dict = {t.name: t for t in tools}
        llm_with_tools = self.llm.bind_tools(tools)

        static_system_content = self.STATIC_SYSTEM_PROMPT
        dynamic_context_content = self.DYNAMIC_CONTEXT_TEMPLATE.format(
            user_persona=state.user_persona or "General friendly student.",
            session_summary=session_summary_str,
            retrieved_context=state.retrieved_context or "No retrieved context.",
            previous_steps_outputs=prev_steps_str,
        )

        messages = [
            SystemMessage(content=static_system_content)
        ]

        # Add message history (last 2 messages, since messages_history has already been limited in chatbot_service)
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

        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        while response.tool_calls:
            logger.info("Luma generated tool calls: %s", response.tool_calls)
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                if tool_name in tools_dict:
                    logger.info("Executing tool: %s with args: %s", tool_name, tool_args)
                    tool_output = await tools_dict[tool_name].ainvoke(tool_args)
                    messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))
                else:
                    messages.append(ToolMessage(content=f"Error: Tool '{tool_name}' not found.", tool_call_id=tool_id))

            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

        final_response_text = str(response.content).strip()
        logger.info("Luma final answer: %s", final_response_text)

        return {
            "response": final_response_text,
            "user_persona": updated_state["user_persona"],
            "session_summary": updated_state["session_summary"],
        }
