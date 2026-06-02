from __future__ import annotations

import inspect
import re
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Mapping, Optional, Union

from .planner import Plan

PLACEHOLDER_PATTERN = re.compile(r"\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)")


class ExecuterError(Exception):
    pass


async def execute_plan(
    plan: Plan,
    tool_source: Union[Mapping[str, Callable[..., Any]], Iterable[Any]],
    runtime_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    runtime_context = runtime_context or {}
    results: Dict[str, Dict[str, Any]] = {}
    steps_by_id = {step.id: step for step in plan.steps}
    remaining = list(plan.steps)

    while remaining:
        progress = False
        for step in list(remaining):
            if any(dep not in results for dep in step.depends_on):
                if any(dep not in steps_by_id for dep in step.depends_on):
                    raise ExecuterError(f"Unknown dependency '{step.depends_on}' for step '{step.id}'")
                continue

            resolved_args: Dict[str, Any] = {}
            for arg_name, arg_value in (step.args or {}).items():
                if isinstance(arg_value, str):
                    if arg_value.startswith("$") and "." in arg_value:
                        match = PLACEHOLDER_PATTERN.fullmatch(arg_value)
                        if match:
                            step_id, output_key = match.groups()
                            if step_id in results and output_key in results[step_id]:
                                resolved_args[arg_name] = results[step_id][output_key]
                                continue
                            raise ExecuterError(f"Unknown placeholder: {arg_value}")

                    built: List[str] = []
                    last_end = 0
                    found = False
                    for placeholder in PLACEHOLDER_PATTERN.finditer(arg_value):
                        found = True
                        step_id, output_key = placeholder.groups()
                        if step_id not in results or output_key not in results[step_id]:
                            raise ExecuterError(f"Unknown placeholder: ${step_id}.{output_key}")
                        built.append(arg_value[last_end:placeholder.start()])
                        built.append(str(results[step_id][output_key]))
                        last_end = placeholder.end()
                    if found:
                        built.append(arg_value[last_end:])
                        resolved_args[arg_name] = "".join(built)
                        continue

                    if arg_value in runtime_context:
                        resolved_args[arg_name] = runtime_context[arg_value]
                        continue

                    alt = arg_value.lstrip("$")
                    if alt == "user_id":
                        alt = "student_id"
                    elif alt == "student_id":
                        alt = "user_id"
                    if alt in runtime_context:
                        resolved_args[arg_name] = runtime_context[alt]
                        continue

                    resolved_args[arg_name] = arg_value
                    continue

                if isinstance(arg_value, dict):
                    target = {}
                    stack: List[Dict[str, Any]] = [{"source": arg_value, "target": target}]
                    while stack:
                        frame = stack.pop()
                        source_dict = frame["source"]
                        target_dict = frame["target"]
                        for key, value in source_dict.items():
                            if isinstance(value, dict):
                                child: Dict[str, Any] = {}
                                target_dict[key] = child
                                stack.append({"source": value, "target": child})
                                continue
                            if isinstance(value, list):
                                new_list: List[Any] = []
                                target_dict[key] = new_list
                                for item in value:
                                    if isinstance(item, dict):
                                        child_list_item: Dict[str, Any] = {}
                                        new_list.append(child_list_item)
                                        stack.append({"source": item, "target": child_list_item})
                                        continue
                                    if isinstance(item, str):
                                        if item.startswith("$") and "." in item:
                                            match = PLACEHOLDER_PATTERN.fullmatch(item)
                                            if match:
                                                step_id, output_key = match.groups()
                                                if step_id in results and output_key in results[step_id]:
                                                    new_list.append(results[step_id][output_key])
                                                    continue
                                                raise ExecuterError(f"Unknown placeholder: {item}")
                                        if item in runtime_context:
                                            new_list.append(runtime_context[item])
                                            continue
                                        alt_item = item.lstrip("$")
                                        if alt_item == "user_id":
                                            alt_item = "student_id"
                                        elif alt_item == "student_id":
                                            alt_item = "user_id"
                                        if alt_item in runtime_context:
                                            new_list.append(runtime_context[alt_item])
                                            continue
                                        new_list.append(item)
                                        continue
                                    new_list.append(item)
                                continue
                            if isinstance(value, str):
                                if value.startswith("$") and "." in value:
                                    match = PLACEHOLDER_PATTERN.fullmatch(value)
                                    if match:
                                        step_id, output_key = match.groups()
                                        if step_id in results and output_key in results[step_id]:
                                            target_dict[key] = results[step_id][output_key]
                                            continue
                                        raise ExecuterError(f"Unknown placeholder: {value}")
                                if value in runtime_context:
                                    target_dict[key] = runtime_context[value]
                                    continue
                                alt_value = value.lstrip("$")
                                if alt_value == "user_id":
                                    alt_value = "student_id"
                                elif alt_value == "student_id":
                                    alt_value = "user_id"
                                if alt_value in runtime_context:
                                    target_dict[key] = runtime_context[alt_value]
                                    continue
                                target_dict[key] = value
                                continue
                            target_dict[key] = value
                    resolved_args[arg_name] = target
                    continue

                if isinstance(arg_value, list):
                    resolved_list: List[Any] = []
                    for item in arg_value:
                        if isinstance(item, str):
                            if item.startswith("$") and "." in item:
                                match = PLACEHOLDER_PATTERN.fullmatch(item)
                                if match:
                                    step_id, output_key = match.groups()
                                    if step_id in results and output_key in results[step_id]:
                                        resolved_list.append(results[step_id][output_key])
                                        continue
                                    raise ExecuterError(f"Unknown placeholder: {item}")
                            if item in runtime_context:
                                resolved_list.append(runtime_context[item])
                                continue
                            alt_item = item.lstrip("$")
                            if alt_item == "user_id":
                                alt_item = "student_id"
                            elif alt_item == "student_id":
                                alt_item = "user_id"
                            if alt_item in runtime_context:
                                resolved_list.append(runtime_context[alt_item])
                                continue
                            resolved_list.append(item)
                            continue
                        resolved_list.append(item)
                    resolved_args[arg_name] = resolved_list
                    continue

                resolved_args[arg_name] = arg_value

            tool = None
            if isinstance(tool_source, Mapping):
                if step.tool_name not in tool_source:
                    raise ExecuterError(f"Tool '{step.tool_name}' is not registered")
                tool = tool_source[step.tool_name]
            else:
                for obj in tool_source:
                    if hasattr(obj, step.tool_name):
                        tool = getattr(obj, step.tool_name)
                        break
                if tool is None:
                    raise ExecuterError(f"Tool '{step.tool_name}' is not available in tool sources")

            signature = inspect.signature(tool)
            bound_args: Dict[str, Any] = {}
            for arg_name, arg_value in resolved_args.items():
                if arg_name in signature.parameters:
                    bound_args[arg_name] = arg_value
                    continue
                if arg_name == "student_id" and "user_id" in signature.parameters:
                    bound_args["user_id"] = arg_value
                    continue
                if arg_name == "user_id" and "student_id" in signature.parameters:
                    bound_args["student_id"] = arg_value
                    continue

            if inspect.iscoroutinefunction(tool):
                step_result = await tool(**bound_args)
            else:
                step_result = tool(**bound_args)
                if isinstance(step_result, Awaitable):
                    step_result = await step_result

            if isinstance(step_result, dict):
                results[step.id] = step_result
            else:
                results[step.id] = {"output": step_result}

            remaining.remove(step)
            progress = True

        if not progress:
            raise ExecuterError("Could not make progress executing plan; please verify dependencies")

    return {"plan_outputs": results}
