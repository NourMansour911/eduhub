import asyncio
import re
from typing import List

from fastapi import Depends
from flask import config

from core import Settings, get_settings
from helpers import get_logger
from integrations.llm import LCOpenAI
from integrations.integrations_dependencies import get_langchain_client
from models.answer_chunk_model import AnsChunkMetadata
from models.vdb_payload_model import VDBChunkPayload
from services.grading.answer_chunking_chain import build_answer_chunking_chain, AnswerChunk

logger = get_logger(__name__)





class AnswerChunkingService:
    _MAX_RETRIES = 3
    _RETRY_DELAY_SECONDS = 1

    def __init__(self, settings: Settings, langchain_client: LCOpenAI):
        self.settings = settings
        self.llm = langchain_client.get_langchain_llm(
            model=self.settings.GENERATION_MODEL_ID,
            temperature=0,
        )
        self.chunking_chain = build_answer_chunking_chain(self.llm)

    async def build_reference_chunks(
        self,
        question_id: str,
        answer: str,
    ) -> List[VDBChunkPayload]:
        try:
            raw_items = await self._chunk_with_chain(answer=answer,question_id=question_id)
        except Exception:
            logger.warning("Chunking failed, using fallback", exc_info=True)
            raw_items = []

        if not raw_items:
            raw_items = self._fallback_simple_chunks(answer=answer)

        normalized_answer_chunks = self._normalize_items(raw_items)
        
        
        payloads = []
        for index, item in enumerate(normalized_answer_chunks):
            text = item.text.strip()
            weight = item.weight
            metadata = AnsChunkMetadata(
                question_id=question_id,
                weight=weight,
                chunk_order=index + 1,
                word_count=self._word_count(text),
            )
            
            payloads.append(
                VDBChunkPayload(text=text, metadata=metadata.model_dump())
            )

        return payloads

    
    async def _chunk_with_chain(self,question_id: str ,answer: str) -> List[AnswerChunk]:
        last_error = None

        for attempt in range(self._MAX_RETRIES):
            try:
                
                response: List[AnswerChunk] = await self.chunking_chain.ainvoke(
                    {"answer": answer},
                    config={
                "run_name": "reference_answer_chunking_run",
                "tags": ["reference", "chunking", "grading"],
                "metadata": {
                    "question_id": question_id,
                },
            }

                )

                
                if response and isinstance(response, list):
                    return response

            except Exception as e:
                last_error = e
                logger.warning(
                    "Chunking chain failed",
                    extra={
                        "attempt": attempt + 1,
                        "max_attempts": self._MAX_RETRIES,
                        "error": str(e),
                    },
                    exc_info=True,
                )

            
            if attempt < self._MAX_RETRIES - 1:
                await asyncio.sleep(self._RETRY_DELAY_SECONDS)

        raise Exception(
            f"Chunking failed after {self._MAX_RETRIES} attempts"
        ) from last_error

        

    def _fallback_simple_chunks(self, answer: str) -> List[AnswerChunk]:
        text = re.sub(r"\s+", " ", answer or "").strip()
        if not text:
            return []

        max_words = 25
        min_words = 5

        sentences = [
            part.strip()
            for part in re.split(r"(?<=[.!?\u061f])\s+", text)
            if part.strip()
        ]
        if not sentences:
            sentences = [text]

        segments: List[str] = []
        for sentence in sentences:
            words = sentence.split()
            if len(words) <= max_words:
                segments.append(sentence)
            else:
                for start in range(0, len(words), max_words):
                    segments.append(" ".join(words[start : start + max_words]))

        chunks: List[str] = []
        current_words: List[str] = []
        for segment in segments:
            seg_words = segment.split()
            if not current_words:
                current_words = seg_words
                continue

            if len(current_words) + len(seg_words) <= max_words:
                current_words += seg_words
                continue

            if len(current_words) < min_words:
                current_words += seg_words
                chunks.append(" ".join(current_words))
                current_words = []
                continue

            chunks.append(" ".join(current_words))
            current_words = seg_words

        if current_words:
            if chunks and len(current_words) < min_words:
                chunks[-1] = f"{chunks[-1]} {' '.join(current_words)}"
            else:
                chunks.append(" ".join(current_words))

        return [AnswerChunk(text=chunk, weight=0.0) for chunk in chunks]


    def _normalize_items(
        self,
        items: List[AnswerChunk],
    ) -> List[AnswerChunk]:
        if not items:
            return []

        n = len(items)
        def_weight = 1.0 / n


        weights = [
            max(0.0, float(item.weight)) if item.weight and item.weight > 0 else def_weight
            for item in items
        ]

        total = sum(weights)

        if total <= 0:
            normalized = [def_weight for _ in items]
        else:
            normalized = [w / total for w in weights]

        diff = 1.0 - sum(normalized)
        normalized[-1] = max(0.0, normalized[-1] + diff)


        return [
            AnswerChunk(
                text=item.text,
                weight=normalized[i]
            )
            for i, item in enumerate(items)
        ]

    def _word_count(self, text: str) -> int:
        return len([word for word in text.split() if word])


def get_answer_chunking_service(
    settings: Settings = Depends(get_settings),
    langchain_client: LCOpenAI = Depends(get_langchain_client),
) -> AnswerChunkingService:
    return AnswerChunkingService(
        settings=settings,
        langchain_client=langchain_client,
    )
