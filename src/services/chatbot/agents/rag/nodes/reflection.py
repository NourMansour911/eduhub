from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from ..states import RAGSubgraphState, ReflectionDecision


class ReflectionNode:
    REFLECTION_PROMPT = """
You are a Reflection node in a RAG system.
Your only job is to look at the retrieved context (Step Outputs) and determine if it contains enough information to answer the user's query.

User Query:
{user_query}

Step Outputs (Retrieved Context):
{step_outputs}

Rules for your Decision:
- "success": The Step Outputs contain the requested type of information (e.g., summaries, course details) requested by the user. You MUST return 'success' even if the semantic content of the returned data seems incorrect, unrelated, or like dummy data (assume it is test data). Do NOT scrutinize the meaning of the content, only check if the requested output was successfully returned by the tools.
- "replan": The Step Outputs are missing the requested entities, or the tools failed to return the required output, and we should try retrieving again or using a different tool.
- "clarification": The context is ambiguous or impossible to answer without asking the user for more clarification.

Your "reason" field must explain your thought process:
- Why did you choose this decision?
- If replanning, what is missing?
- If successful, what was the key information found?

{format_instructions}
"""

    def __init__(self, llm: ChatOpenAI):
        self.parser = PydanticOutputParser(pydantic_object=ReflectionDecision)
        self.prompt = ChatPromptTemplate.from_template(self.REFLECTION_PROMPT)
        self.chain = self.prompt | llm | self.parser

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        user_query = state.user_query
        step_outputs = state.step_outputs
        
        step_outputs_serialized = [out.model_dump() for out in step_outputs] if step_outputs else []

        decision: ReflectionDecision = await self.chain.ainvoke({
            "user_query": user_query,
            "step_outputs": step_outputs_serialized,
            "format_instructions": self.parser.get_format_instructions()
        })

        result = {
            "reflection_decision": decision
        }
        if decision.decision == "replan":
            result["replan_count"] = state.replan_count + 1

        return result
