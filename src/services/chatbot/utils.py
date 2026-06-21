import time
import contextlib
from typing import Any, List, AsyncGenerator

@contextlib.asynccontextmanager
async def log_duration(logger: Any, action_name: str, session_id: str = "Unknown") -> AsyncGenerator[None, None]:
    start_time = time.time()
    logger.info(f"[Session: {session_id}] Starting {action_name}")
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"[Session: {session_id}] {action_name} completed in {duration:.2f}s")



def format_step_output(out: Any) -> str:
    if hasattr(out, "tool_name"):
        tool_name = out.tool_name
        content = out.content
        failure_info = out.failure_info
    elif isinstance(out, dict):
        tool_name = out.get("tool_name", "")
        content = out.get("content", {})
        failure_info = out.get("failure_info", None)
    else:
        return str(out)

    if failure_info:
        msg = (
            failure_info.message
            if hasattr(failure_info, "message")
            else (failure_info.get("message", "") if isinstance(failure_info, dict) else str(failure_info))
        )
        return f"Tool: {tool_name}\nError: {msg}"

    return f"Tool: {tool_name}\nContent: {content}"


def format_nested_step_outputs(nested_outputs: List[List[Any]]) -> str:
    if not nested_outputs:
        return "No previous steps outputs."
    formatted = []
    for i, turn_list in enumerate(nested_outputs):
        turn_str = []
        for out in turn_list:
            turn_str.append(format_step_output(out))
        if turn_str:
            formatted.append(f"Turn {i+1}:\n" + "\n".join(turn_str))
    return "\n\n".join(formatted) if formatted else "No previous steps outputs."


def format_messages_history(messages_history: List[Any]) -> str:
    if not messages_history:
        return "No history."
    formatted = []
    for msg in messages_history:
        if isinstance(msg, dict):
            role = msg.get("role", "Human")
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        else:
            formatted.append(str(msg))
    return "\n".join(formatted)
