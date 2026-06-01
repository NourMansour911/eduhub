import json
import re
from typing import Any, Dict, List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field




class PlanStep(BaseModel):
	id: str = Field(..., description="Unique step id like step_1")
	tool_name: str = Field(..., description="Tool name from the registry")
	args: Dict[str, Any] = Field(default_factory=dict)
	reason: str = Field(..., description="Reason for choosing this step")
	depends_on: List[str] = Field(default_factory=list)


class Plan(BaseModel):
	steps: List[PlanStep] = Field(default_factory=list)
	goal: str = Field(..., description="The original user query or goal that this plan addresses")



PARSER = PydanticOutputParser(pydantic_object=Plan)


SYSTEM_PROMPT = """
You are the Planner. Your role is to output ONLY a valid JSON execution DAG for the user query.

Rules:
- Do NOT answer the user.
- Do NOT execute tools.
- Treat all tools as black boxes.
- Use ONLY tool names defined below (exact match).
- Produce a DAG as a JSON object with a top-level `steps` array.

Each step object must include these keys:
- `id`: unique step id (e.g. "step_1").
- `tool_name`: tool name exactly as listed in the registry.
- `args`: object with the arguments to pass to the tool.
- `output`: object describing the expected output schema or example keys and their types (used by downstream steps).
- `depends_on`: array of step ids this step depends on (may be empty).

If a step needs data from a previous step, reference it in `args` using the syntax `$<step_id>.<output_key>` (for example `$step_1.course_id`).

Available tools (name + description + usage + args schema + output (optional)):
{tools_registry}



Output MUST be valid JSON only — no surrounding text, commentary, or explanations.

The JSON must strictly follow this schema guidance:
{format_instructions}
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
			"usage": "When to use: query content limited to a specific lecture (provide lecture_id and query).",
			"args_schema": {
				"lecture_id": "str",
				"query": "str",
			},
		},
		{
			"name": "ask_in_the_whole_course_by_course_id",
			"description": "Search vector DB across a course.",
			"usage": "When to use: search all lectures in a course for relevant chunks (provide course_id and query).",
			"args_schema": {
				"course_id": "str",
				"query": "str",
			},
		},
		{
			"name": "search_in_sessions_history",
			"description": "Search the user's past sessions.",
			"usage": "When to use: retrieve prior interactions or context for the same user (provide user_id and query).",
			"args_schema": {
				"user_id": "str",
				"query": "str",
			},
		},
		{
			"name": "ask_in_legal_regulations",
			"description": "Search legal and regulatory lectures (REG01).",
			"usage": "When to use: ask regulatory or legal questions that must reference official materials.",
			"args_schema": {
				"query": "str",
			},
		},
		{
			"name": "get_course_id_by_course_name",
			"description": "Resolve a course id from its name.",
			"usage": "When to use: map a user-provided course name (approximately) to its internal id (provide student_id and course_name).",
			"output": {
				"course_id": "str",
				"course_name": "str"
			},
			"args_schema": {
				"student_id": "str",
				"course_name": "str",
			},
		},
		{
			"name": "get_lecture_id_by_lecture_name",
			"description": "Resolve a lecture id from its title.",
			"usage": "When to use: map a lecture title (approximately) to its internal id within a course (provide course_id and lecture_name).",
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
			"usage": "When to use: retrieve course details (title, description, instructor) for display or validation (provide course_id).",
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
			"usage": "When to use: enumerate available courses for a student (provide student_id).",
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
			"usage": "When to use: obtain the complete lecture text for quoting, analysis, or chunking (provide lecture_id).",
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
			"usage": "When to use: get a concise overview of a lecture when full content is not required (provide lecture_id).",
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
		| RunnableLambda(lambda x: x.steps)
	)


__all__ = ["build_planner_chain", "get_default_tools_registry"]
