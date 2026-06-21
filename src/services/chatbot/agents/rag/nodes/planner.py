import json
from typing import Any, Dict

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from ..states import RAGSubgraphState, PlannerOutput
from .tools_registry import get_default_tools_registry
from helpers.logger import get_chatbot_logger
from services.chatbot.utils import format_step_output, format_nested_step_outputs, log_duration

logger = get_chatbot_logger(__name__)


class PlannerNode:
    STATIC_SYSTEM_PROMPT = """
You are a DAG planner. Convert the user request to a tool plan DAG or clarification.

Rules:
1. Student ID is implicitly "$student_id"; never ask for it.
2. Match course names in the query to IDs in 'Enrolled Courses' (e.g., "Data Mining" -> course_id="IS422P"). Do not guess; clarify if ambiguous.
3. Pass data between steps using "$step_id.output_key" (matching the exact returns schema in Tools Registry, e.g. "$step_1.lectures[0].id").
4. Only assist with topics/courses in 'Enrolled Courses'. If user asks outside of these, output status="clarification" with a polite response.
5. Simple greetings/chit-chat require no tools; output status="plan" with steps=[].
6. Adjust plan based on execution history/failures.

Tools Registry:
{tools_registry}

Output Schema:
{format_instructions}
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
Enrolled Courses: {student_courses}

Execution History of the current message (use to adjust strategy & avoid repeated failures):
{previous_attempts}

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
        
        reflection_feedback = ""
        if state.reflection_decision and state.reflection_decision.decision == "replan":
            reflection_feedback = f"\n[CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT]:\nThe previous plan failed or was insufficient. Reason: {state.reflection_decision.reason}\nYou MUST adjust your plan based on this feedback.\n"

        logger.info(
            "\n" + "="*80 + "\n"
            "[PLANNER NODE] STARTING EVALUATION\n"
            f"Session ID: {state.session_id}\n"
            f"User Query: {state.user_query}\n"
            f"Enrolled Courses: {state.student_courses}\n"
            f"Previous Attempts: {previous_attempts_formatted}\n"
            f"Previous Messages Step Outputs: {previous_steps_outputs_formatted}\n"
            f"Reflection Feedback: {reflection_feedback.strip() if reflection_feedback else 'None'}\n"
            + "="*80
        )

        async with log_duration(logger, "Planner Node Chain Call", session_id=state.session_id):
            planner_output = await self.chain.ainvoke({
                "user_query": state.user_query,
                "previous_attempts": previous_attempts_formatted,
                "previous_steps_outputs": previous_steps_outputs_formatted,
                "reflection_feedback": reflection_feedback,
                "student_courses": state.student_courses
            })

        steps_logged = []
        if planner_output.steps:
            for step in planner_output.steps:
                steps_logged.append(f"  - ID: {step.id} | Tool: {step.tool_name} | Args: {step.args} | Depends: {step.depends_on}")
        steps_str = "\n".join(steps_logged) if steps_logged else "  (None)"

        logger.info(
            "\n" + "-"*80 + "\n"
            "[PLANNER NODE] DECISION GENERATED\n"
            f"Status: {planner_output.status.upper()}\n"
            f"Steps:\n{steps_str}\n"
            f"Clarification Question: {planner_output.clarification_question or 'None'}\n"
            + "-"*80
        )
        
        return {
            "planner_output": planner_output,
        }

