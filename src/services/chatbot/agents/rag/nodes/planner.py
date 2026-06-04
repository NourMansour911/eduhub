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
You are a DAG planner for an agentic tool-using system.

Your task is to convert the user request into an executable tool DAG or return a clarification question.

Execution History:
{history}
(This contains previous attempts, successful results, and failures. Use this to avoid repeating failed actions or to build upon previous findings).

Rules:
- NEVER ask for student_id, course_id, lecture_id.
- student_id is always available at runtime as "$student_id".
- ALWAYS prefer constructing a tool chain over asking the user.
- If the History contains a clarification answer from the user, use it to refine the plan.
- Use ONLY tools from the registry (exact names).
- Use $step_id.output_key for data passing between steps in the CURRENT plan.
- If previous attempts (History) failed, change your strategy (different tool, different query).

Decision logic (STRICT):
- If ANY tool sequence can move toward solving the request → MUST return a PLAN (status="plan").
- Only return CLARIFICATION (status="clarification") if NO possible tool chain exists to progress.

Tools Registry:
{tools_registry}

Output schema:
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

        planner_output = await self.chain.ainvoke({
            "user_query": state.user_query,
            "history": history_serialized
        })
        
        return {
            "planner_output": planner_output,
            "history": history,
            "step_outputs": step_outputs
        }

