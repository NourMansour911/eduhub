import re
from typing import Any, Dict, List

import spacy
from sklearn.feature_extraction.text import TfidfVectorizer


class StudentAnswerChunkingService:
    _NUMBER_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
    _MAX_KEYWORDS_PER_CHUNK = 8

    def __init__(self):
        self._nlp = self._build_nlp_pipeline()

    def chunk_and_extract(self, student_answer: str) -> List[Dict[str, Any]]:
        chunks = self._sentence_based_chunks(student_answer=student_answer)
        if not chunks:
            return []

        keywords_map = self._extract_keywords(chunks)

        processed: List[Dict[str, Any]] = []
        for index, chunk_text in enumerate(chunks):
            doc = self._nlp(chunk_text)
            entities = [
                {
                    "text": ent.text,
                    "label": ent.label_,
                }
                for ent in doc.ents
            ]
            processed.append(
                {
                    "id": str(index),
                    "text": chunk_text,
                    "keywords": keywords_map[index],
                    "numbers": self.extract_numbers(chunk_text),
                    "entities": entities,
                }
            )

        return processed

    def extract_numbers(self, text: str) -> List[str]:
        if not text:
            return []
        return [match.group(0) for match in self._NUMBER_PATTERN.finditer(text)]

    def _sentence_based_chunks(self, student_answer: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", student_answer or "").strip()
        if not normalized:
            return []

        doc = self._nlp(normalized)
        chunks = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        if chunks:
            return chunks

        return [normalized]

    def _extract_keywords(self, chunks: List[str]) -> Dict[int, List[str]]:
        if not chunks:
            return {}

        try:
            vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_]+\b",
            )
            matrix = vectorizer.fit_transform(chunks)
        except ValueError:
            return {index: [] for index in range(len(chunks))}

        feature_names = vectorizer.get_feature_names_out()
        keywords_map: Dict[int, List[str]] = {}

        for row_index in range(matrix.shape[0]):
            row = matrix.getrow(row_index)
            if row.nnz == 0:
                keywords_map[row_index] = []
                continue

            scored_terms = sorted(
                (
                    (feature_names[column_index], value)
                    for column_index, value in zip(row.indices, row.data)
                    if value > 0
                ),
                key=lambda item: (-item[1], item[0]),
            )
            keywords_map[row_index] = [
                term for term, _ in scored_terms[: self._MAX_KEYWORDS_PER_CHUNK]
            ]

        return keywords_map

    def _build_nlp_pipeline(self):
        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            nlp = spacy.blank("en")

        if "sentencizer" not in nlp.pipe_names:
            nlp.add_pipe("sentencizer")

        return nlp


def get_student_answer_chunking_service() -> StudentAnswerChunkingService:
    return StudentAnswerChunkingService()
