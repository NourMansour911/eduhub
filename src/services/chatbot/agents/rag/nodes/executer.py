import asyncio
import re
from typing import Any, Dict, List, Callable
from ..states import RAGSubgraphState, PlanStep, StepOutput, FailureInfo
from helpers.logger import get_chatbot_logger
from services.chatbot.utils import log_duration

logger = get_chatbot_logger(__name__)


class ExecutorNode:
    def __init__(self, tool_registry: Dict[str, Callable]):
        self.tool_registry = tool_registry

    def _resolve_arg(self, arg_value: Any, runtime_vars: Dict[str, Any], step_outputs_dict: Dict[str, StepOutput]) -> Any:
        if not isinstance(arg_value, str) or not arg_value.startswith("$"):
            return arg_value

        var_name = arg_value[1:]  

        if not var_name.startswith("step_"):
            return runtime_vars.get(var_name, arg_value)

        match = re.match(r'^(step_\d+)(.*)$', var_name)
        if not match:
            return arg_value
        
        step_id, path = match.groups()
        if step_id not in step_outputs_dict:
            return arg_value
        
        current_val = step_outputs_dict[step_id].content
        if not path:
            return current_val
            
        access_pattern = re.compile(r'^(?:\.([a-zA-Z_][a-zA-Z0-9_]*)|\[(\d+)\]|\[[\'"]([^\'\"]+)[\'"]\])')
        
        while path:
            m = access_pattern.match(path)
            if not m:
                return arg_value
            
            key, idx, str_key = m.groups()
            matched_len = m.end()
            path = path[matched_len:]
            
            if key is not None:
                if isinstance(current_val, dict) and key in current_val:
                    current_val = current_val[key]
                else:
                    return arg_value
            elif idx is not None:
                idx_int = int(idx)
                if isinstance(current_val, list) and 0 <= idx_int < len(current_val):
                    current_val = current_val[idx_int]
                else:
                    return arg_value
            elif str_key is not None:
                if isinstance(current_val, dict) and str_key in current_val:
                    current_val = current_val[str_key]
                else:
                    return arg_value
                    
        return current_val

    async def _execute_step(self, step: PlanStep, step_outputs_dict: Dict[str, StepOutput], runtime_vars: Dict[str, Any], session_id: str = "Unknown") -> StepOutput:
        if step.tool_name not in self.tool_registry:
            logger.error(f"[Session: {session_id}] [EXECUTOR NODE] Tool '{step.tool_name}' not found in registry.")
            return StepOutput(step_id=step.id, source="Executor", tool_name=step.tool_name, 
                                 failure_info=FailureInfo(message=f"Tool '{step.tool_name}' not found."))

        tool_func = self.tool_registry[step.tool_name]
        
        resolved_args = {k: self._resolve_arg(v, runtime_vars, step_outputs_dict) for k, v in step.args.items()}
        resolved_args["step_id"] = step.id

        logger.info(f"[Session: {session_id}] [EXECUTOR NODE] RUNNING TOOL: {step.tool_name} ({step.id})")
        logger.debug(f"[Session: {session_id}] Arguments: {resolved_args}")

        try:
            async with log_duration(logger, f"Tool Run: {step.tool_name} ({step.id})", session_id=session_id):
                res = await tool_func(**resolved_args)
            if res.failure_info:
                logger.error(
                    "\n" + f"[Session: {session_id}] [EXECUTOR NODE] TOOL FAILED: {step.tool_name} ({step.id})\n"
                    f"Failure Message: {res.failure_info.message}\n"
                    f"Explanation: {res.failure_info.explanation}\n"
                    + "-"*80
                )
            else:
                logger.info(f"[Session: {session_id}] [EXECUTOR NODE] TOOL SUCCESS: {step.tool_name} ({step.id})")
                logger.debug(f"[Session: {session_id}] Result Content: {res.content}")
            return res
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.error(
                "\n" + f"[Session: {session_id}] [EXECUTOR NODE] TOOL CRASHED: {step.tool_name} ({step.id})\n"
                f"Exception: {str(e)}\n"
                f"Traceback:\n{tb_str}\n"
                + "-"*80
            )
            return StepOutput(step_id=step.id, source="Executor", tool_name=step.tool_name, tool_args=resolved_args,
                                failure_info=FailureInfo(message="Execution Error", explanation=tb_str))

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        planner_output = state.planner_output
        if not planner_output or planner_output.status != "plan" or not planner_output.steps:
            return {}

        step_outputs = list(state.step_outputs)
        step_outputs_dict = {out.step_id: out for out in step_outputs}
        runtime_vars = {"student_id": state.student_id}
        
        executed_ids = set(step_outputs_dict.keys())
        steps_to_run = [s for s in planner_output.steps if s.id not in executed_ids]

        logger.info(
            "\n" + "="*80 + "\n"
            "[EXECUTOR NODE] STARTING EXECUTION\n"
            f"Session ID: {state.session_id}\n"
            f"Steps to execute: {[s.id for s in steps_to_run]}\n"
            + "="*80
        )
        
        while steps_to_run:
            ready_steps = [s for s in steps_to_run if all(dep in executed_ids for dep in s.depends_on)]
            
            if not ready_steps: 
                break

            results: List[StepOutput] = await asyncio.gather(*[
                self._execute_step(step, step_outputs_dict, runtime_vars, session_id=state.session_id) for step in ready_steps
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

        logger.info(
            "\n" + "="*80 + "\n"
            "[EXECUTOR NODE] EXECUTION FINISHED\n"
            f"Session ID: {state.session_id}\n"
            f"Final Step Outputs count: {len(step_outputs)}\n"
            + "="*80
        )

        return {
            "step_outputs": step_outputs
        }
