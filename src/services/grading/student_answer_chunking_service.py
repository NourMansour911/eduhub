import re
from typing import Any, Dict, List


class StudentAnswerChunkingService:
    _SPACE_PATTERN = re.compile(r"\s+")
    _SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?\u061f])\s+|\n+")

    def chunk_and_extract(self, student_answer: str) -> List[Dict[str, Any]]:
        normalized = self._normalize(student_answer)
        if not normalized:
            return []

        sentences = [
            self._normalize(part)
            for part in self._SENTENCE_SPLIT_PATTERN.split(normalized)
            if self._normalize(part)
        ]
        if not sentences:
            return [{"id": "0", "text": normalized}]

        return [{"id": str(index), "text": text} for index, text in enumerate(sentences)]

    def _normalize(self, text: str) -> str:
        return self._SPACE_PATTERN.sub(" ", text or "").strip()


def get_student_answer_chunking_service() -> StudentAnswerChunkingService:
    return StudentAnswerChunkingService()
