import json
import re
from typing import Any, Dict, List, Literal, Union

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field




class PlanStep(BaseModel):
	id: str = Field(..., description="Unique step id like step_1")
	tool_name: str = Field(..., description="Tool name from the registry")
	args: Dict[str, Any] = Field(default_factory=dict)
	depends_on: List[str] = Field(default_factory=list)



class Clarification(BaseModel):
    status: Literal[0] = 0
    question: str


class Plan(BaseModel):
    status: Literal[1] = 1
    steps: List[PlanStep]


class PlannerOutput(BaseModel):
    result: Union[Plan, Clarification]



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
- If ANY tool sequence can move toward solving the request → MUST return a PLAN.
- Only return CLARIFICATION if NO possible tool chain exists to progress.
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




def get_default_tools_registry() -> List[Dict[str, Any]]:

	return [
		{
			"name": "ask_in_specific_lecture_by_lecture_id",
			"description": "Search vector DB for chunks in a lecture.",
			"usage": "When to use: query content limited to a specific lecture",
			"args_schema": {
				"lecture_id": "str",
				"query": "str",
			},
		},
		{
			"name": "ask_in_the_whole_course_by_course_id",
			"description": "Search vector DB across a course.",
			"usage": "When to use: search all lectures in a course for relevant chunks.",
			"args_schema": {
				"course_id": "str",
				"query": "str",
			},
		},
		{
			"name": "search_in_sessions_history",
			"description": "Search the user's past sessions.",
			"usage": "When to use: only if the intent that.",
			"args_schema": {
				"student_id": "$student_id",
				"query": "str",
			},
		},
		{
			"name": "ask_in_legal_regulations",
			"description": "Search legal and regulatory lectures.",
			"usage": "When to use: ask regulatory or legal questions that must reference official materials.",
			"args_schema": {
				"query": "str",
			},
		},
		{
			"name": "get_course_id_by_course_name",
			"description": "Resolve a course id from its name.",
			"usage": "When to use: map a user-provided course name (approximately) to its internal id.",
			"output": {
				"course_id": "str",
				"course_name": "str"
			},
			"args_schema": {
				"student_id": "$student_id",
				"course_name": "str",
			},
		},
		{
			"name": "get_lecture_id_by_lecture_name",
			"description": "Resolve a lecture id from its title.",
			"usage": "When to use: map a lecture title (approximately) to its internal id within a course.",
			"output": {
				"lecture_id": "str",
				"lecture_name": "str"
			},
			"args_schema": {
				"course_id": "str",
				"lecture_name": "str",
			},
		},
		{
			"name": "get_course_details_by_course_id",
			"description": "Fetch course metadata by course id.",
			"usage": "When to use: retrieve course details (title, description, instructor) for display or validation.",
			"output": {
				"course_id": "str",
				"title": "str",
				"description": "str",
				"instructor": "str"
			},
			"args_schema": {
				"course_id": "str",
			},
		},
		{
			"name": "get_all_student_courses_ids_and_names",
			"description": "List a student's courses.",
			"usage": "When to use: enumerate available courses for a student.",
			"output": {
				"courses": "list[dict] (course_id, course_name)",
				"total": "int"
			},
			"args_schema": {
				"student_id": "str",
			},
		},
		{
			"name": "get_lecture_whole_content_by_lecture_id",
			"description": "Return the full lecture content by lecture id.",
			"usage": "When to use: obtain the complete lecture text for quoting, analysis, or chunking.",
			"output": {
				"content": "str",
				"lecture_id": "str"
			},
			"args_schema": {
				"lecture_id": "str",
			},
		},
		{
			"name": "get_lecture_summary_by_lecture_id",
			"description": "Return a lecture summary by lecture id.",
			"usage": "When to use: get a concise overview of a lecture when full content is not required.",
			"output": {
				"summary": "str",
				"lecture_id": "str",
				"level": "int (summary level if supported)"
			},
			"args_schema": {
				"lecture_id": "str",
			},
		},
	]


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

