import json
import re
from typing import Any, Dict, List, Literal, Union

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .tools_registry import get_default_tools_registry




from ..states import PlanStep, PlannerOutput
from .tools_registry import get_default_tools_registry


PARSER = PydanticOutputParser(pydantic_object=PlannerOutput)


SYSTEM_PROMPT = """
You are a DAG planner for an agentic tool-using system.

Task: convert the user request into an executable tool DAG or return a clarification question.

Rules:
- NEVER ask for student_id, course_id, lecture_id.
- student_id is always available at runtime as "$student_id".
- ALWAYS prefer constructing a tool chain over asking the user.
- Use ONLY tools from the registry (exact names).
- Tools are black boxes.
- Use depends_on for sequencing.
- Use $step_id.output_key for data passing.

Decision logic (STRICT):
- If ANY tool sequence can move toward solving the request → MUST return a PLAN (status="plan").
- Only return CLARIFICATION (status="clarification") if NO possible tool chain exists to progress.
- You must explicitly select or resolve the correct item using tools or reasoning.

When multiple distinct concepts exist:

You MUST:
1. Extract all atomic concepts explicitly.
2. Create at least one retrieval step per concept.
3. Never combine multiple concepts into a single retrieval query.
4. Each step must target exactly ONE concept.

Tools:
{tools_registry}

Output schema:
{format_instructions}

Output constraints:
- Output ONLY valid JSON
- No explanations
- No extra text
"""




PROMPT = ChatPromptTemplate.from_messages(
	[
		("system", SYSTEM_PROMPT),
		(
			"human",
			"""
User query:
{user_query}
""",
		),
	]
).partial(format_instructions=PARSER.get_format_instructions())


def _prepare_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
	user_query = (inputs.get("user_query") or "").strip()
	if not user_query:
		raise ValueError("user_query is required")

	return {
		"user_query": user_query,
		"tools_registry": json.dumps(get_default_tools_registry(), ensure_ascii=True, indent=2),
	}




def build_planner_chain(llm: ChatOpenAI) -> Runnable:
	return (
		RunnableLambda(_prepare_inputs)
		| PROMPT
		| llm
		| PARSER
	)

