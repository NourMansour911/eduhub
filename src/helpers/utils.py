from typing import Any, Annotated
from pydantic import AfterValidator


def serialize_content(content: Any) -> Any:
    if hasattr(content, "as_dict"):
        return content.as_dict()
    return content


def unescape_newlines(text: Any) -> Any:
    """
    Cleans LLM output text by:
    1. Unwrapping double-serialized JSON strings (e.g. '"text"' -> 'text')
    2. Replacing literal \\n / \\r\\n escape sequences with real newlines
    This must be applied at the source (right after LLM output) before any storage.
    """
    if not isinstance(text, str):
        return text

    import json
    stripped = text.strip()

    # Try to safely decode JSON-wrapped strings (handles double-serialization)
    # e.g. '"hello\\nworld"' -> 'hello\nworld'
    try:
        while (
            (stripped.startswith('"') and stripped.endswith('"'))
            or (stripped.startswith('[') and stripped.endswith(']'))
            or (stripped.startswith('{') and stripped.endswith('}'))
        ):
            decoded = json.loads(stripped)
            if isinstance(decoded, str):
                stripped = decoded.strip()
            else:
                break
    except Exception:
        # Fallback: if json.loads fails (e.g. raw newlines inside a quoted string),
        # manually strip the outer quotes.
        if stripped.startswith('"') and stripped.endswith('"'):
            stripped = stripped[1:-1]

    # Unescape escaped double quotes left over from JSON encoding
    text = stripped.replace('\\"', '"')

    # Unescape escaped newlines (literal \n / \r\n sequences -> real newlines)
    text = text.replace("\\\\r\\\\n", "\n").replace("\\r\\n", "\n")
    text = text.replace("\\\\r", "\n").replace("\\r", "\n")
    text = text.replace("\\\\n", "\n").replace("\\n", "\n")

    return text


CleanMarkdownStr = Annotated[str, AfterValidator(unescape_newlines)]
