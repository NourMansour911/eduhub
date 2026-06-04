import asyncio
import re
from typing import Any, Dict, List, Callable
from ..states import RAGSubgraphState, PlanStep, StepOutput, FailureInfo


class ExecutorNode:
    def __init__(self, tool_registry: Dict[str, Callable]):
        self.tool_registry = tool_registry

    def _resolve_arg(self, arg_value: Any, runtime_vars: Dict[str, Any], step_outputs_dict: Dict[str, StepOutput]) -> Any:
        
        if not isinstance(arg_value, str) or not arg_value.startswith("$"):
            return arg_value

        var_name = arg_value[1:]  

        if not var_name.startswith("step_"):
            return runtime_vars.get(var_name, arg_value)

        parts = var_name.split(".", 1)
        if len(parts) == 2:
            step_id, key = parts
            if step_id in step_outputs_dict and key in step_outputs_dict[step_id].content:
                return step_outputs_dict[step_id].content[key]
        
        return arg_value

    async def _execute_step(self, step: PlanStep, step_outputs_dict: Dict[str, StepOutput], runtime_vars: Dict[str, Any]) -> StepOutput:
        if step.tool_name not in self.tool_registry:
            return StepOutput(step_id=step.id, source="Executor", tool_name=step.tool_name, 
                                failure_info=FailureInfo(message=f"Tool '{step.tool_name}' not found."))

        tool_func = self.tool_registry[step.tool_name]
        
        
        resolved_args = {k: self._resolve_arg(v, runtime_vars, step_outputs_dict) for k, v in step.args.items()}
        resolved_args["step_id"] = step.id

        try:
            return await tool_func(**resolved_args)
        except Exception as e:
            return StepOutput(step_id=step.id, source="Executor", tool_name=step.tool_name, 
                                failure_info=FailureInfo(message="Execution Error", explanation=str(e)))

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        planner_output = state.planner_output
        if not planner_output or planner_output.status != "plan" or not planner_output.steps:
            return {}

        step_outputs = list(state.step_outputs)
        step_outputs_dict = {out.step_id: out for out in step_outputs}
        runtime_vars = {"student_id": state.student_id}
        
        executed_ids = set(step_outputs_dict.keys())
        steps_to_run = [s for s in planner_output.steps if s.id not in executed_ids]
        
        while steps_to_run:
            ready_steps = [s for s in steps_to_run if all(dep in executed_ids for dep in s.depends_on)]
            
            if not ready_steps: 
                break

            results: List[StepOutput] = await asyncio.gather(*[
                self._execute_step(step, step_outputs_dict, runtime_vars) for step in ready_steps
            ])
            
            has_error = False
            for result in results:
                step_outputs.append(result)
                step_outputs_dict[result.step_id] = result
                executed_ids.add(result.step_id)
                
                if result.failure_info:
                    has_error = True
            
            if has_error: 
                break  
            
            steps_to_run = [s for s in steps_to_run if s.id not in executed_ids]

        return {
            "step_outputs": step_outputs
        }
