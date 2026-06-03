import asyncio
import re
from typing import Any, Dict, List, Callable
from src.dtos import RAGContextDTO, FailureInfo
from ..states import ExecutionState, RAGSubgraphState, PlanStep


class ExecutorNode:
    def __init__(self, tool_registry: Dict[str, Callable]):
        self.tool_registry = tool_registry

    async def _execute_step(
        self,
        step: PlanStep,
        execution_state: ExecutionState,
        runtime_vars: Dict[str, Any]
    ) -> RAGContextDTO:
        tool_name = step.tool_name
        if tool_name not in self.tool_registry:
            return RAGContextDTO(
                source="Executor",
                tool_name=tool_name,
                failure_info=FailureInfo(
                    message=f"Tool '{tool_name}' not found.",
                    explanation=f"The planner requested a tool that is not registered: {tool_name}"
                )
            )

        tool_func = self.tool_registry[tool_name]
        
        # Resolve arguments
        resolved_args = {}
        for arg_name, arg_value in step.args.items():
            if isinstance(arg_value, str):
                # Resolve runtime variables
                if arg_value.startswith("$") and not arg_value.startswith("$step_"):
                    var_name = arg_value[1:]
                    resolved_args[arg_name] = runtime_vars.get(var_name)
                    if resolved_args[arg_name] is None:
                        return RAGContextDTO(
                            source="Executor",
                            tool_name=tool_name,
                            failure_info=FailureInfo(
                                message=f"Missing variable: {var_name}",
                                explanation=f"Runtime variable '{var_name}' not found for arg '{arg_name}'."
                            )
                        )
                
                # Resolve step references
                elif arg_value.startswith("$step_"):
                    match = re.match(r"^\$(step_\d+)\.(.+)$", arg_value)
                    if match:
                        prev_step_id = match.group(1)
                        key = match.group(2)
                        
                        prev_output: RAGContextDTO = execution_state.step_outputs.get(prev_step_id)
                        if not prev_output:
                            return RAGContextDTO(
                                source="Executor",
                                tool_name=tool_name,
                                failure_info=FailureInfo(
                                    message=f"Step {prev_step_id} output missing",
                                    explanation=f"Tool depends on {prev_step_id} which hasn't produced output."
                                )
                            )
                        
                        resolved_args[arg_name] = prev_output.content.get(key)
                        if resolved_args[arg_name] is None:
                            return RAGContextDTO(
                                source="Executor",
                                tool_name=tool_name,
                                failure_info=FailureInfo(
                                    message=f"Key {key} not found",
                                    explanation=f"Key '{key}' not found in step '{prev_step_id}' output."
                                )
                            )
                    else:
                        resolved_args[arg_name] = arg_value
                else:
                    resolved_args[arg_name] = arg_value
            else:
                resolved_args[arg_name] = arg_value

        try:
            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(**resolved_args)
            return tool_func(**resolved_args)
        except Exception as e:
            return RAGContextDTO(
                source="Executor",
                tool_name=tool_name,
                failure_info=FailureInfo(
                    message="Tool execution error",
                    explanation=str(e)
                )
            )

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        """
        Executes the DAG of steps defined in the plan.
        """
        planner_output = state.planner_output
        if not planner_output or planner_output.status != "plan" or not planner_output.steps:
            return {}

        plan_steps = planner_output.steps
        execution_state = state.execution_state
        runtime_vars = {
            "student_id": state.student_id
        }

        # Track completed steps
        completed_steps = set(execution_state.step_outputs.keys())
        steps_to_run = [s for s in plan_steps if s.id not in completed_steps]
        
        # We execute in layers (deterministic DAG execution)
        while steps_to_run:
            # Find steps which have all dependencies met
            ready_steps = [
                s for s in steps_to_run 
                if all(dep in completed_steps for dep in s.depends_on)
            ]
            
            if not ready_steps:
                # Check if there's a deadlock or missing dependency output
                if steps_to_run:
                    execution_state.execution_errors.append("Deadlock or missing dependencies in plan.")
                break

            # Execute ready steps in parallel
            tasks = [
                self._execute_step(step, execution_state, runtime_vars)
                for step in ready_steps
            ]
            
            results: List[RAGContextDTO] = await asyncio.gather(*tasks)
            
            has_failure = False
            for step, result in zip(ready_steps, results):
                execution_state.step_outputs[step.id] = result
                
                if result.failure_info:
                    error_msg = result.failure_info.message
                    execution_state.execution_errors.append(
                        f"Step {step.id} ({step.tool_name}) reported failure: {error_msg}"
                    )
                    has_failure = True
                
                completed_steps.add(step.id)
                steps_to_run = [s for s in steps_to_run if s.id != step.id]

            if has_failure:
                break

        # Collect all successful contexts
        contexts = [
            out for out in execution_state.step_outputs.values()
            if not out.failure_info
        ]

        return {
            "execution_state": execution_state,
            "contexts": contexts
        }
