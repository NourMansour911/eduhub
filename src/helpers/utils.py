
from typing import Any


def serialize_content(content: Any) -> Any:
  
    if hasattr(content, "as_dict"):
        return content.as_dict()
    return content


