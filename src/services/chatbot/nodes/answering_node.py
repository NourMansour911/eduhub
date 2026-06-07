from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from helpers import get_logger
from integrations import RedisProvider
from ..states import ChatbotState
from ..utils import format_nested_step_outputs, format_messages_history
from ..chains.summary_chain import build_summary_chain
from ..chains.persona_chain import build_persona_chain
from ..tools.agent_tools import create_update_persona_tool, create_update_summary_tool

logger = get_logger(__name__)


class AnsweringNode:
    SYSTEM_PROMPT = """\
You are Luma, a supportive, encouraging, and clear AI Tutor Chatbot. Your goal is to guide students and answer queries.

IMPORTANT Rules:
1. If the user's query is completely off-topic or unrelated to the educational platform, courses, lectures, academic questions, or academic regulations, you must politely respond stating that you are Luma, an AI Tutor, and you can only assist with academic and course-related queries.
2. If the query is within scope, answer it based on the messages history, student persona, session summary, and retrieved context. Adapt your response to match the student's persona.
3. You have access to tools to update the student's persona profile and update the session summary. Call them when appropriate (e.g. when the student shares preferences or when summarizing the latest turn).

Student Persona:
{user_persona}

Session Summary:
{session_summary}

Retrieved Context:
{retrieved_context}

Previous Turns Step Outputs:
{previous_steps_outputs}

Conversation History (last 4 messages):
{messages_history}
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

        logger.debug(
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
            logger.debug("Persona update tool callback triggered with: %s", new_persona)
            updated_state["user_persona"] = new_persona
            collection = await self.redis_provider.get_collection(user_id=state.student_id, session_id=state.session_id)
            if collection:
                collection.persona = new_persona
                await self.redis_provider.save_collection(collection, session_id=state.session_id)

        async def update_summary_callback(new_summary: str):
            logger.debug("Summary update tool callback triggered with: %s", new_summary)
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

        system_content = self.SYSTEM_PROMPT.format(
            user_persona=state.user_persona or "General friendly student.",
            session_summary=session_summary_str,
            retrieved_context=state.retrieved_context or "No retrieved context.",
            previous_steps_outputs=prev_steps_str,
            messages_history=messages_history_str,
        )

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=state.user_query),
        ]

        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        while response.tool_calls:
            logger.debug("Luma generated tool calls: %s", response.tool_calls)
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                if tool_name in tools_dict:
                    logger.debug("Executing tool: %s with args: %s", tool_name, tool_args)
                    tool_output = await tools_dict[tool_name].ainvoke(tool_args)
                    messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_id))
                else:
                    messages.append(ToolMessage(content=f"Error: Tool '{tool_name}' not found.", tool_call_id=tool_id))

            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

        final_response_text = str(response.content).strip()
        logger.debug("Luma final answer: %s", final_response_text)

        return {
            "response": final_response_text,
            "user_persona": updated_state["user_persona"],
            "session_summary": updated_state["session_summary"],
        }
