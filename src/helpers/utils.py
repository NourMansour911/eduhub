from typing import Any, Annotated
from pydantic import AfterValidator


def serialize_content(content: Any) -> Any:
    if hasattr(content, "as_dict"):
        return content.as_dict()
    return content


def unescape_newlines(text: Any) -> Any:
    if not isinstance(text, str):
        return text

    import json
    stripped = text.strip()

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
        if stripped.startswith('"') and stripped.endswith('"'):
            stripped = stripped[1:-1]
    text = stripped.replace('\\"', '"')


    text = text.replace("\\\\r\\\\n", "\n").replace("\\r\\n", "\n")
    text = text.replace("\\\\r", "\n").replace("\\r", "\n")
    text = text.replace("\\\\n", "\n").replace("\\n", "\n")

    return text


CleanMarkdownStr = Annotated[str, AfterValidator(unescape_newlines)]
