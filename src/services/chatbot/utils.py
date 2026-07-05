import time
import contextlib
import json
from typing import Any, List, AsyncGenerator, Dict, Optional


def extract_llm_call_config(llm: Any) -> Dict[str, Any]:
    if llm is None:
        return {}

    config: Dict[str, Any] = {}
    model_name = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    if model_name is not None:
        config["model"] = model_name

    for attr in ("temperature", "max_tokens", "top_p", "max_retries"):
        value = getattr(llm, attr, None)
        if value is not None:
            config[attr] = value

    model_kwargs = getattr(llm, "model_kwargs", None)
    if isinstance(model_kwargs, dict) and model_kwargs:
        config["model_kwargs"] = model_kwargs

    return config


def extract_llm_metadata(response: Any, llm: Any = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = extract_llm_call_config(llm)

    response_meta = getattr(response, "response_metadata", None) or {}
    for key in ("model_name", "model", "finish_reason", "system_fingerprint"):
        value = response_meta.get(key)
        if value is not None:
            metadata["model" if key == "model_name" else key] = value

    if extra:
        metadata.update(extra)

    return metadata


def build_llm_node_payload(usage: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "usage": usage or {},
        "metadata": metadata or {},
    }

def extract_llm_usage(response: Any) -> Dict[str, Optional[int]]:

    usage_meta = getattr(response, "usage_metadata", None) or {}
    response_meta = getattr(response, "response_metadata", None) or {}
    token_usage_meta = response_meta.get("token_usage") or {}

    prompt_tokens     = usage_meta.get("input_tokens")  if "input_tokens"  in usage_meta else token_usage_meta.get("prompt_tokens")
    completion_tokens = usage_meta.get("output_tokens") if "output_tokens" in usage_meta else token_usage_meta.get("completion_tokens")
    total_tokens      = usage_meta.get("total_tokens")  if "total_tokens"  in usage_meta else token_usage_meta.get("total_tokens")

    return {
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens":      total_tokens,
    }


def merge_llm_usage(usage_dicts: List[Dict[str, Optional[int]]]) -> Dict[str, Optional[int]]:

    total_prompt, total_completion, total_tokens = 0, 0, 0
    for usage in usage_dicts:
        if not usage:
            continue
        total_prompt     += usage.get("prompt_tokens")     or 0
        total_completion += usage.get("completion_tokens") or 0
        total_tokens     += usage.get("total_tokens")      or 0
    return {
        "prompt_tokens":     total_prompt,
        "completion_tokens": total_completion,
        "total_tokens":      total_tokens,
    }


def sum_llm_usage_tree(usage_tree: Any) -> Dict[str, int]:
    total_prompt, total_completion, total_tokens = 0, 0, 0

    if not isinstance(usage_tree, dict):
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_tokens,
        }

    for key, value in usage_tree.items():
        if key == "total":
            continue
        if isinstance(value, dict) and "usage" in value and isinstance(value["usage"], dict):
            usage = value["usage"]
            total_prompt += int(usage.get("prompt_tokens") or 0)
            total_completion += int(usage.get("completion_tokens") or 0)
            total_tokens += int(usage.get("total_tokens") or 0)
        elif isinstance(value, dict) and any(token_key in value for token_key in ("prompt_tokens", "completion_tokens", "total_tokens")):
            total_prompt += int(value.get("prompt_tokens") or 0)
            total_completion += int(value.get("completion_tokens") or 0)
            total_tokens += int(value.get("total_tokens") or 0)
        elif isinstance(value, dict):
            nested_total = sum_llm_usage_tree(value)
            total_prompt += nested_total["prompt_tokens"]
            total_completion += nested_total["completion_tokens"]
            total_tokens += nested_total["total_tokens"]

    return {
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_tokens,
    }


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
        
    items = None
    if "chunks" in content and isinstance(content["chunks"], list):
        items = content["chunks"]
    elif "retrieved_context" in content and isinstance(content["retrieved_context"], list):
        items = content["retrieved_context"]

    if items is not None:
        parts = []
        for i, chunk in enumerate(items, start=1):
            if not isinstance(chunk, dict):
                parts.append(str(chunk))
                continue
            text = chunk.get("text", "")
            meta = chunk.get("metadata", {}) or {}
            if not isinstance(meta, dict):
                meta = {}
            
            meta_clean = {k: v for k, v in meta.items() if k != "chunk_id"}
            meta_str = " | ".join(f"{k}: {v}" for k, v in meta_clean.items()) if meta_clean else ""
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


def clip_message_content(content: str, max_length: int = 500) -> str:

    if not content:
        return ""
    if len(content) <= max_length:
        return content
    return content[:max_length] + " [clipped for brevity]"


def format_chat_history_for_graph(messages: List[Dict[str, str]], limit: int = 6) -> List[Dict[str, str]]:
    last_messages = []
    for msg in messages[-limit:]:
        role = "Human" if msg.get("role") == "user" else "AI"
        content = clip_message_content(msg.get("content", ""))
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
        explanation = (
            failure_info.explanation
            if hasattr(failure_info, "explanation")
            else (failure_info.get("explanation", None) if isinstance(failure_info, dict) else None)
        )
        clarification_msg = (
            failure_info.clarification_message
            if hasattr(failure_info, "clarification_message")
            else (failure_info.get("clarification_message", None) if isinstance(failure_info, dict) else None)
        )
        err_str = f"Tool: {tool_name}\nStatus: FAILED\nError: {msg}"
        if explanation:
            err_str += f"\nExplanation: {explanation}"
        if clarification_msg:
            err_str += f"\nClarification Recommendation: {clarification_msg}"
        return err_str

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
            

    deduped.reverse()
    return deduped
