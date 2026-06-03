from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from src.dtos import RAGContextDTO
from ..states import RAGSubgraphState, ReflectionDecision, RAGSubgraphOutput, ExecutionState
from .planner import PlannerOutput


REFLECTION_PROMPT = """
You are a Reflection node in a RAG system.
Your task is to evaluate if the retrieved contexts are sufficient to answer the user query, or if a replan or clarification is needed.

User Query: {user_query}
Planner Output: {planner_output}
Execution State (Errors/Outputs): {execution_state}
Retrieved Contexts: {contexts}

Decision Logic:
1. "success": If the retrieved contexts are sufficient to answer the query and there are no critical execution errors.
2. "replan": If the current plan failed OR the retrieved contexts are insufficient but more tools could be used.
3. "clarification": If the retrieved contexts are insufficient and you need more information from the user to proceed.

STRICT RULE FOR CLARIFICATION:
If any tool has failed (failure_info is present) and provided a "clarification_message", you SHOULD prefer using that message for your "clarification_question" as it is a predefined instruction for the user to help the tools succeed.

Output ONLY valid JSON matching the schema.
"""

REFLECTION_PARSER = PydanticOutputParser(pydantic_object=ReflectionDecision)


def build_reflection_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_template(REFLECTION_PROMPT)
    return prompt | llm | REFLECTION_PARSER


async def reflection_node(state: RAGSubgraphState, reflection_chain) -> Dict[str, Any]:
    user_query = state.user_query
    planner_output = state.planner_output
    execution_state = state.execution_state
    contexts = state.contexts

    contexts_serialized = [c.model_dump() for c in contexts]
    planner_serialized = planner_output.model_dump() if planner_output else {}
    exec_state_serialized = execution_state.model_dump() if execution_state else {}

    decision: ReflectionDecision = await reflection_chain.ainvoke({
        "user_query": user_query,
        "planner_output": planner_serialized,
        "execution_state": exec_state_serialized,
        "contexts": contexts_serialized
    })

    return {
        "reflection_decision": decision
    }
