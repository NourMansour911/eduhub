import json
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


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

    @field_validator("args", "depends_on", mode="before")
    @classmethod
    def parse_json_fields(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                pass
        return v


class PlannerOutput(BaseModel):
    status: Literal["plan", "clarification"] = Field(..., description="Whether a plan was generated or clarification is needed")
    steps: Optional[List[PlanStep]] = Field(default=None, description="The list of steps if status is 'plan'")
    clarification_question: Optional[str] = Field(default=None, description="The question if status is 'clarification'")

    @field_validator("steps", mode="before")
    @classmethod
    def parse_steps(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                pass
        return v


class ReflectionDecision(BaseModel):
    decision: Literal["success", "replan", "clarification"] = Field(
        ...,
        description="'success' if the requested type of data was successfully returned (even if dummy/test data); "
                    "'replan' if key entities are missing or tools failed; "
                    "'clarification' if context is too ambiguous to decide."
    )
    reason: str = Field(
        ...,
        description="Explanation of the choice, detailing what key info was found or what is missing if replanning."
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Question to ask the user if decision is 'clarification'."
    )


class RAGSubgraphOutput(BaseModel):
    status: Literal["success", "clarification", "failed"]
    retrieved_context: Optional[str] = None
    run_step_outputs: List[StepOutput] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    error_message: Optional[str] = None


class RAGSubgraphState(BaseModel):
    user_query: str
    student_id: str
    session_id: str = Field(default="", description="ID of the chat session")
    student_courses: str = Field(default="", description="Compact string of student courses")
    past_attempts_tool_outputs: List[StepOutput] = Field(default_factory=list, description="Step outputs of previous attempts in the current run")
    messages_history: List[Any] = Field(default_factory=list, description="Recent messages from the conversation history")
    past_messages_tool_outputs: List[StepOutput] = Field(default_factory=list, description="Step outputs from previous messages/turns")
    planner_output: Optional[PlannerOutput] = None 
    current_attempt_tool_outputs: List[StepOutput] = Field(default_factory=list)
    reflection_decision: Optional[ReflectionDecision] = None
    retriving_results: Optional[RAGSubgraphOutput] = None
    plan_attempts_count: int = Field(default=1, description="Tracks the planning attempt number (1 to 3)")
