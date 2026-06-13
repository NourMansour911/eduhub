import json
from typing import Any, Dict

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .tools_registry import get_default_tools_registry
from ..states import PlannerOutput, RAGSubgraphState
from helpers.logger import get_logger
from services.chatbot.utils import format_step_output, format_nested_step_outputs, format_messages_history

logger = get_logger(__name__)


class PlannerNode:
    STATIC_SYSTEM_PROMPT = """
You are a DAG planner. Convert the user request to a tool plan DAG (status="plan") or clarification (status="clarification").

Rules:
1. NEVER ask for student_id, course_id, or lecture_id.
2. The student_id is implicitly "$student_id".
3. Match course names in the user query to IDs listed in the 'Enrolled Courses' context (e.g., "Data Mining(ID: IS422P)" -> course_id="IS422P"). Do not guess or invent IDs; clarify if missing or ambiguous.
4. Pass data between steps using "$step_id.output_key". Use the EXACT "returns" schema defined in the Tools Registry to form your path. For example, if a tool returns {{"lectures": [{{"id": "str"}}]}}, reference the ID as "$step_1.lectures[0].id". NEVER use generic outputs like "$step_1[0]" or "$step_1.output".
5. Use exact tool names and arguments from the Tools Registry.
6. The "query" argument in search tools should represent the core concept to retrieve.
7. Adapt based on History: change strategy on failures; use user clarification answers to refine.
8. The student is ONLY allowed to ask questions related to their enrolled courses. If the user's query asks about topics, lectures, or courses outside of 'Enrolled Courses', you MUST output status='clarification' and politely clarify that you can only assist with their enrolled courses.
9. If the user query is a simple greeting (e.g., "hello", "hi"), a polite thank-you, or general chit-chat that does not require retrieving external database/course information, you MUST output status="plan" with an empty steps list (steps=[]). Do not trigger any tools or ask for clarification for simple greetings.

Tools Registry:
{tools_registry}

Output Schema:
{format_instructions}
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
Enrolled Courses: {student_courses}

Execution History of the current message (use to adjust strategy & avoid repeated failures):
{previous_attempts}

Recent Conversation Chat History:
{messages_history}

Steps Outputs of Previous Messages:
{previous_steps_outputs}

{reflection_feedback}

Current User Query: {user_query}
"""

    def __init__(self, llm: ChatOpenAI):
        self.parser = PydanticOutputParser(pydantic_object=PlannerOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.STATIC_SYSTEM_PROMPT),
            ("human", self.DYNAMIC_CONTEXT_TEMPLATE),
        ]).partial(
            format_instructions=self.parser.get_format_instructions(),
            tools_registry=lambda: json.dumps(get_default_tools_registry(), ensure_ascii=True, indent=2)
        )
        
        self.chain = self.prompt | llm | self.parser

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        previous_attempts = list(state.previous_attempts)
        step_outputs = list(state.step_outputs)
        
        if step_outputs:
            previous_attempts.extend(step_outputs)
            step_outputs = []

        # Formats
        previous_attempts_formatted = "\n\n".join([format_step_output(h) for h in previous_attempts]) if previous_attempts else "No previous attempts."
        previous_steps_outputs_formatted = format_nested_step_outputs(state.previous_steps_outputs)
        messages_history_formatted = format_messages_history(state.messages_history)
        
        reflection_feedback = ""
        if state.reflection_decision and state.reflection_decision.decision == "replan":
            reflection_feedback = f"\n[CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT]:\nThe previous plan failed or was insufficient. Reason: {state.reflection_decision.reason}\nYou MUST adjust your plan based on this feedback.\n"

        logger.info(
            "PlannerNode invoked. Query: %s | Previous Attempts: %s | Previous Steps: %s",
            state.user_query,
            previous_attempts_formatted,
            previous_steps_outputs_formatted,
        )

        planner_output = await self.chain.ainvoke({
            "user_query": state.user_query,
            "previous_attempts": previous_attempts_formatted,
            "messages_history": messages_history_formatted,
            "previous_steps_outputs": previous_steps_outputs_formatted,
            "reflection_feedback": reflection_feedback,
            "student_courses": state.student_courses
        })

        logger.info("PlannerNode output status: %s", planner_output.status)
        
        return {
            "planner_output": planner_output,
        }

