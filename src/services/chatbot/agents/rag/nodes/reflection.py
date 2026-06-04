from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from ..states import RAGSubgraphState, ReflectionDecision


class ReflectionNode:
    REFLECTION_PROMPT = """
You are a Reflection node in a RAG system.
Your task is to evaluate the execution history and decide the next move.

Core Responsibility:
1. Examine "Step Outputs" to see what tools were called and what they returned.
2. If tools failed, read their "failure_info" and "explanation".
3. Determine if the gathered information is enough to answer "{user_query}".

Rules for your Decision:
- "success": Everything needed is found.
- "replan": Information is missing, but a DIFFERENT tool or a different search query might find it. 
- "clarification": The query is impossible to satisfy without asking the user (e.g., tool specifically requested missing info via "clarification_message").

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
        planner_output = state.planner_output
        step_outputs = state.step_outputs
        
        planner_serialized = planner_output.model_dump() if planner_output else {}
        step_outputs_serialized = [out.model_dump() for out in step_outputs] if step_outputs else []

        decision: ReflectionDecision = await self.chain.ainvoke({
            "user_query": user_query,
            "planner_output": planner_serialized,
            "execution_state": step_outputs_serialized,
            "format_instructions": self.parser.get_format_instructions()
        })

        return {
            "reflection_decision": decision
        }
