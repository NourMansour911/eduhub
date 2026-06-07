from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class FailureInfo(BaseModel):
    message: str = Field(..., description="Technical or user-friendly error message")
    clarification_message: Optional[str] = Field(default=None, description="Predefined question to ask the user if clarification is needed")
    explanation: Optional[str] = Field(default=None, description="Detailed explanation of the failure for the LLM")


class StepOutput(BaseModel):
    step_id: str = Field(default="", description="ID of the step that produced this output")
    tool_name: str = Field(default="", description="Name of the tool that produced this output")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool")
    source: str = Field(..., description="The source of the retrieved context")
    content: Dict[str, Any] = Field(default_factory=dict, description="The retrieved context content (populated on success)")
    failure_info: Optional[FailureInfo] = Field(default=None, description="Details about the failure (populated on failure)")


class PlanStep(BaseModel):
    id: str = Field(..., description="Unique step id (e.g., step_1)")
    tool_name: str = Field(..., description="Name of the tool to execute")
    args: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps this step depends on")


class PlannerOutput(BaseModel):
    status: Literal["plan", "clarification"] = Field(..., description="Whether a plan was generated or clarification is needed")
    steps: Optional[List[PlanStep]] = Field(default=None, description="The list of steps if status is 'plan'")
    clarification_question: Optional[str] = Field(default=None, description="The question if status is 'clarification'")



class ReflectionDecision(BaseModel):
    decision: Literal["success", "replan", "clarification"]
    reason: str
    clarification_question: Optional[str] = None


class RAGSubgraphOutput(BaseModel):
    status: Literal["success", "clarification", "failed"]
    retrieved_context: Optional[str] = None
    run_step_outputs: List[StepOutput] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    error_message: Optional[str] = None


class RAGSubgraphState(BaseModel):
    user_query: str
    student_id: str
    student_courses: str = Field(default="", description="Compact string of student courses")
    previous_attempts: List[StepOutput] = Field(default_factory=list, description="Step outputs of previous attempts in the current run")
    messages_history: List[Any] = Field(default_factory=list, description="Recent messages from the conversation history")
    previous_steps_outputs: List[List[StepOutput]] = Field(default_factory=list, description="Step outputs from previous messages/turns")
    planner_output: Optional[PlannerOutput] = None 
    step_outputs: List[StepOutput] = Field(default_factory=list)
    reflection_decision: Optional[ReflectionDecision] = None
    retriving_results: Optional[RAGSubgraphOutput] = None
    replan_count: int = Field(default=0, description="Tracks how many times replanning occurred")
