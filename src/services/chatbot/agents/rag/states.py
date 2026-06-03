from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from src.dtos import RAGContextDTO


class PlanStep(BaseModel):
    id: str = Field(..., description="Unique step id (e.g., step_1)")
    tool_name: str = Field(..., description="Name of the tool to execute")
    args: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps this step depends on")


class PlannerOutput(BaseModel):
    status: Literal["plan", "clarification"] = Field(..., description="Whether a plan was generated or clarification is needed")
    steps: Optional[List[PlanStep]] = Field(default=None, description="The list of steps if status is 'plan'")
    clarification_question: Optional[str] = Field(default=None, description="The question if status is 'clarification'")


class ExecutionState(BaseModel):
    step_outputs: Dict[str, Any] = Field(default_factory=dict)
    execution_errors: List[str] = Field(default_factory=list)


class ReflectionDecision(BaseModel):
    decision: Literal["success", "replan", "clarification"]
    reason: str
    clarification_question: Optional[str] = None


class RAGSubgraphOutput(BaseModel):
    status: Literal["success", "clarification"]
    contexts: List[RAGContextDTO] = Field(default_factory=list)
    clarification_question: Optional[str] = None


class RAGSubgraphState(BaseModel):
    user_query: str
    student_id: str
    planner_output: Optional[PlannerOutput] = None 
    execution_state: ExecutionState = Field(default_factory=ExecutionState)
    contexts: List[RAGContextDTO] = Field(default_factory=list)
    reflection_decision: Optional[ReflectionDecision] = None
    