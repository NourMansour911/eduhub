from enum import Enum
from typing import Any, Dict, List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class QueryRewriteMode(str, Enum):
	SESSION_SUMMARY = "session_summary"
	LECTURE_SEARCH = "lecture_search"
	GENERAL = "general"


class QueryRewriteOutput(BaseModel):
	rewritten_queries: List[str] = Field(default_factory=list)


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
}


QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
	[
		(
			"system",
			"""
You are a query rewriting assistant for retrieval systems.

Rules:
- Keep the meaning close to the original query
- Do not answer the query
- Do not add facts that are not already implied
- Produce search-friendly rewrites only
- Return only valid JSON
{format_instructions}
""",
		),
		(
			"human",
			"""
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
""",
		),
	]
)

PARSER = PydanticOutputParser(pydantic_object=QueryRewriteOutput)


def build_query_rewriting_chain(llm: ChatOpenAI) -> Runnable:
	def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
		query = (inputs.get("query") or "").strip()
		rewrite_mode = str(inputs.get("rewrite_mode") or QueryRewriteMode.GENERAL.value).strip().lower()
		rewrite_count = max(1, int(inputs.get("rewrite_count") or 3))

		return {
			"query": query,
			"rewrite_count": rewrite_count,
			"mode_instruction": MODE_INSTRUCTIONS.get(
				rewrite_mode,
				MODE_INSTRUCTIONS[QueryRewriteMode.GENERAL.value],
			),
			"format_instructions": PARSER.get_format_instructions(),
		}

	return RunnableLambda(prepare_input) | QUERY_REWRITE_PROMPT | llm | PARSER