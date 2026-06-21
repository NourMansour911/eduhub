import time
import contextlib
import json
from typing import Any, List, AsyncGenerator, Dict

@contextlib.asynccontextmanager
async def log_duration(logger: Any, action_name: str, session_id: str = "Unknown") -> AsyncGenerator[None, None]:
    start_time = time.time()
    logger.info(f"[Session: {session_id}] Starting {action_name}")
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"[Session: {session_id}] {action_name} completed in {duration:.2f}s")


def extract_clean_content_text(content: Any) -> str:
    if not content:
        return ""
    if not isinstance(content, dict):
        return str(content)
        
    if "chunks" in content and isinstance(content["chunks"], list):
        parts = []
        for i, chunk in enumerate(content["chunks"], start=1):
            if not isinstance(chunk, dict):
                parts.append(str(chunk))
                continue
            text = chunk.get("text", "")
            meta = {k: v for k, v in chunk.items() if k != "text"}
            meta_str = ", ".join(f"{k}: {v}" for k, v in meta.items()) if meta else ""
            header = f"[Chunk {i}]" + (f" ({meta_str})" if meta_str else "")
            parts.append(f"{header}\n{text}")
        return "\n\n".join(parts)
        
    for key in ("summary", "text", "content"):
        if key in content:
            return str(content[key])
            
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)


def clean_payload_for_planning(content: Any) -> Any:
    if isinstance(content, dict):
        cleaned = {}
        for k, v in content.items():
            if k == "chunks" and isinstance(v, list):
                cleaned_chunks = []
                for chunk in v:
                    if isinstance(chunk, dict):
                        c_copy = chunk.copy()
                        if "text" in c_copy:
                            text_len = len(str(c_copy["text"]))
                            c_copy["text"] = f"<Text content: {text_len} characters>"
                        cleaned_chunks.append(c_copy)
                    else:
                        cleaned_chunks.append(chunk)
                cleaned[k] = cleaned_chunks
            elif k in ("summary", "text", "content") and isinstance(v, str):
                cleaned[k] = f"<{k.capitalize()} content: {len(v)} characters>"
            else:
                cleaned[k] = clean_payload_for_planning(v)
        return cleaned
    elif isinstance(content, list):
        return [clean_payload_for_planning(item) for item in content]
    else:
        return content


def format_student_courses(courses: List[Dict[str, Any]]) -> str:
    courses_str = ", ".join([f"{c.get('name', 'Unknown')}(ID:{c.get('course_id', 'Unknown')})" for c in courses])
    if not courses_str:
        courses_str = "No enrolled courses"
    return courses_str


def format_chat_history_for_graph(messages: List[Dict[str, str]], limit: int = 6) -> List[Dict[str, str]]:
    last_messages = []
    for msg in messages[-limit:]:
        role = "Human" if msg.get("role") == "user" else "AI"
        content = msg.get("content", "")
        last_messages.append({"role": role, "content": content})
    return last_messages


def format_step_output(out: Any, for_planning: bool = False) -> str:
    if hasattr(out, "tool_name"):
        tool_name = out.tool_name
        content = out.content
        failure_info = out.failure_info
    elif isinstance(out, dict):
        tool_name = out.get("tool_name", "")
        content = out.get("content", {})
        failure_info = out.get("failure_info", None)
    else:
        content_str = str(out)
        return f"Status: SUCCESS\nContent: {content_str}"

    if failure_info:
        msg = (
            failure_info.message
            if hasattr(failure_info, "message")
            else (failure_info.get("message", "") if isinstance(failure_info, dict) else str(failure_info))
        )
        return f"Tool: {tool_name}\nStatus: FAILED\nError: {msg}"

    if for_planning:
        content = clean_payload_for_planning(content)

    return f"Tool: {tool_name}\nStatus: SUCCESS\nContent: {content}"


def format_nested_step_outputs(nested_outputs: List[Any], for_planning: bool = False) -> str:
    if not nested_outputs:
        return "No previous steps outputs."
    formatted = []
    for out in nested_outputs:
        formatted.append(format_step_output(out, for_planning=for_planning))
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


def deduplicate_tool_outputs(outputs: List[Any]) -> List[Any]:

    if not outputs:
        return []
        
    seen_keys = set()
    deduped = []
    
    for out in reversed(outputs):
        if not out:
            continue
            
        if isinstance(out, dict):
            t_name = out.get("tool_name", "")
            t_args = out.get("tool_args", {})
        else:
            t_name = getattr(out, "tool_name", "")
            t_args = getattr(out, "tool_args", {})
            
        try:
            t_args_str = json.dumps(t_args, sort_keys=True)
        except Exception:
            t_args_str = str(t_args)
            
        key = (t_name, t_args_str)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(out)
            
    # Reverse back to restore original chronological order
    deduped.reverse()
    return deduped
