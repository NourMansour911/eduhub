import json
from typing import Any, Dict

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

from .tools_registry import get_default_tools_registry
from ..states import PlannerOutput, RAGSubgraphState


class PlannerNode:
    SYSTEM_PROMPT = """
You are a DAG planner. Convert the user request to a tool plan DAG (status="plan") or clarification (status="clarification").

{reflection_feedback}

Execution History (use to adjust strategy & avoid repeated failures):
{history}

Rules:
1. NEVER ask for student_id, course_id, or lecture_id.
2. student_id is "$student_id". Match course names in query to IDs in 'Courses Context' (e.g., "Data Mining(ID: IS422P)" -> course_id="IS422P"). Do not guess/invent IDs; clarify if missing.
3. Pass data between steps using "$step_id.output_key". Use the EXACT "returns" schema defined in the Tools Registry to form your path. For example, if a tool returns {{"lectures": [{{"id": "str"}}]}}, reference the ID as "$step_1.lectures[0].id". NEVER use generic outputs like "$step_1[0]" or "$step_1.output".
4. Prefer planning. Only clarify if no tools can help progress.
5. Use exact tool names and args from the Tools Registry.
6. The "query" field should represent the core concept to retrieve.
7. Adapt based on History: change strategy on failures; use user clarification answers to refine.

Courses Context: {student_courses}

Tools Registry:
{tools_registry}

Output Schema:
{format_instructions}
"""

    def __init__(self, llm: ChatOpenAI):
        self.parser = PydanticOutputParser(pydantic_object=PlannerOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", "User Query: {user_query}"),
        ]).partial(
            format_instructions=self.parser.get_format_instructions(),
            tools_registry=lambda: json.dumps(get_default_tools_registry(), ensure_ascii=True, indent=2)
        )
        
        self.chain = self.prompt | llm | self.parser

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        
        history = list(state.history)
        step_outputs = list(state.step_outputs)
        
        if step_outputs:
            history.extend(step_outputs)
            step_outputs = []

        history_serialized = [h.model_dump() for h in history]
        
        reflection_feedback = ""
        if state.reflection_decision and state.reflection_decision.decision == "replan":
            reflection_feedback = f"\n[CRITICAL FEEDBACK FROM PREVIOUS ATTEMPT]:\nThe previous plan failed or was insufficient. Reason: {state.reflection_decision.reason}\nYou MUST adjust your plan based on this feedback.\n"

        planner_output = await self.chain.ainvoke({
            "user_query": state.user_query,
            "history": history_serialized,
            "reflection_feedback": reflection_feedback,
            "student_courses": state.student_courses
        })
        
        return {
            "planner_output": planner_output,
        }

