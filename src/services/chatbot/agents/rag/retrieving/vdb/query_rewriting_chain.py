import json
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator


class QueryRewriteMode(str, Enum):
	SESSION_SUMMARY = "session_summary"
	LECTURE_SEARCH = "lecture_search"
	REGULATIONS_SEARCH = "regulations_search"
	GENERAL = "general"


class QueryRewriteOutput(BaseModel):
	rewritten_queries: List[str] = Field(default_factory=list)

	@field_validator("rewritten_queries", mode="before")
	@classmethod
	def parse_rewritten_queries(cls, v):
		if isinstance(v, str):
			try:
				parsed = json.loads(v)
				if isinstance(parsed, list):
					return parsed
			except json.JSONDecodeError as exc:
				raise ValueError(f"Failed to parse rewritten_queries JSON string: {v}") from exc
			raise ValueError(f"rewritten_queries JSON string did not deserialize to a list: {v}")
		return v


MODE_INSTRUCTIONS = {
	QueryRewriteMode.SESSION_SUMMARY.value: """
You are rewriting a query for retrieving session summary content.
Prefer concise wording that preserves the user's intent, references the main topic, and broadens recall for paraphrased discussion.
Focus on semantic variations, session concepts, and likely summary phrasing.
""",
	QueryRewriteMode.LECTURE_SEARCH.value: """
You are rewriting a query for retrieving lecture content.
Prefer keyword-rich wording that captures course concepts, definitions, formulas, names, and technical terms.
Focus on lecture-style terminology and high-recall search variants.
""",
	QueryRewriteMode.GENERAL.value: """
You are rewriting a query for general retrieval.
Generate a small set of semantically close variants that improve recall without drifting from the original meaning.
""",
	QueryRewriteMode.REGULATIONS_SEARCH.value: """
You are rewriting a query for regulations retrieval.
Prefer keyword-rich wording that captures regulatory terms, concepts, and high-recall search variants.
Focus on academic, legal, and policy phrasing.
""",
}


SYSTEM_MSG = """
You are a query rewriting assistant for retrieval systems.

Rules:
- Keep the meaning close to the original query
- Do not answer the query
- Do not add facts that are not already implied
- Produce search-friendly rewrites only
"""

CONTEXT_MSG = """
Use case:
{mode_instruction}

Original query:
{query}

Target rewrite count:
{rewrite_count}

Output requirements:
- Return exactly the JSON schema requested
- Each rewrite must be a single search query string
- Do not repeat the original query verbatim
- Keep each rewrite short and retrieval-oriented
"""

QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
	[
		("system", SYSTEM_MSG),
		("human", CONTEXT_MSG),
	]
)

def build_query_rewriting_chain(llm: ChatOpenAI) -> Runnable:
	structured_llm = llm.with_structured_output(QueryRewriteOutput, method="function_calling")

	def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
		raw_query = inputs.get("query")
		if not raw_query or not str(raw_query).strip():
			raise ValueError("Field 'query' is required for query rewriting.")
		query = str(raw_query).strip()

		raw_mode = inputs.get("rewrite_mode")
		if raw_mode is None:
			rewrite_mode = QueryRewriteMode.GENERAL.value
		else:
			rewrite_mode = str(raw_mode).strip().lower()
			if rewrite_mode not in MODE_INSTRUCTIONS:
				raise ValueError(
					f"Invalid rewrite_mode '{raw_mode}'. Expected one of {list(MODE_INSTRUCTIONS.keys())}."
				)

		rewrite_count = max(1, int(inputs.get("rewrite_count") or 3))

		return {
			"query": query,
			"rewrite_count": rewrite_count,
			"mode_instruction": MODE_INSTRUCTIONS[rewrite_mode],
		}

	return RunnableLambda(prepare_input) | QUERY_REWRITE_PROMPT | structured_llm