import re
import hashlib

from helpers.logger import get_logger
from dtos.chunk_dto import ChunkMetadata
from dtos.vdb_payload_dto import VDBChunkPayload
from .chunking_exceptions import ChunkProcessingError
from typing import List, Dict, Any, Optional, Union, Set, Tuple
from uuid import uuid4
from azure.ai.documentintelligence.models import AnalyzeResult

logger = get_logger(__name__)


class ChunkingService:

    def __init__(self):
        pass

    def _get(self, obj: Union[AnalyzeResult, Dict[str, Any]], key: str, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    async def process_azure_analyze_result(
        self,
        prepared_content: AnalyzeResult,
        lecture_id: str,
        course_id: str,
        lecture_name: str,
        course_name: str,
        lecture_order: Optional[int] = None,
    ) -> List[VDBChunkPayload]:

        chunk_payloads: List[VDBChunkPayload] = []
        chunk_count = 0
        seen_text_hashes: Set[str] = set()

        def append_chunk_payload_if_new(chunk_text: str, pages_numbers: List[int]) -> None:
            nonlocal chunk_count

            normalized_text = (chunk_text or "").strip()
            if not normalized_text:
                return

            text_hash = hashlib.md5(normalized_text.encode("utf-8")).hexdigest()
            if text_hash in seen_text_hashes:
                return
            seen_text_hashes.add(text_hash)

            metadata = ChunkMetadata(
                chunk_id=str(uuid4()),
                lecture_id=lecture_id,
                lecture_name=lecture_name,
                course_id=course_id,
                course_name=course_name,
                chunk_index=chunk_count + 1,
                lecture_order=lecture_order,
                pages_numbers=pages_numbers,
            )
            chunk_payloads.append(
                VDBChunkPayload(
                    text=normalized_text,
                    metadata=metadata.model_dump(),
                )
            )
            chunk_count += 1
        

        full_content = self._get(prepared_content, "content", "")
        
        try:

            sections = self._get(prepared_content, "sections", [])
            
            for section in sections:
                
                elements = self._get(section, "elements", [])
                used_paras_indices = set()
                section_parts: List[str] = []
                page_numbers: Set[int] = set()
                for element_id in elements:
                    element_text, element_page, returned_idx = await self._extract_element_text(
                        prepared_content, element_id, full_content
                    )
                    if returned_idx is not None:
                        used_paras_indices.add(returned_idx)
                        
                    element_text = (element_text or "").strip()
                    if element_text:
                        section_parts.append(element_text)
                    if element_page is not None:
                        page_numbers.add(element_page)

                section_text = "\n".join(section_parts).strip()
                if not section_text:
                    continue

                section_text = re.sub(r"<figure>\s*</figure>", "", section_text)
                append_chunk_payload_if_new(section_text, sorted(list(page_numbers)))
            
            paragraphs = self._get(prepared_content, "paragraphs", [])
            paragraphs_no = len(paragraphs)
            
            all_indices = set(range(paragraphs_no))
            orphans_indices = all_indices - used_paras_indices

            sorted_indices = sorted(orphans_indices)
            current_parts: List[str] = []
            current_pages: Set[int] = set()
            current_word_count = 0

            for idx in sorted_indices:
                paragraph = paragraphs[idx]
                text = (self._get(paragraph, "text", "") or "").strip()
                if not text or len(text.split()) < 10:
                    continue

                bounding_regions = self._get(paragraph, "bounding_regions", []) or []
                page_number = None
                if bounding_regions:
                    page_number = self._get(bounding_regions[0], "page_number", None)

                paragraph_words = len(text.split())
                page_changed = False
                if current_pages and page_number is not None:
                    last_page = max(current_pages)
                    page_changed = abs(page_number - last_page) > 2
                    
                if current_parts and (page_changed or current_word_count + paragraph_words > 350):
                    chunk_text = "\n".join(current_parts).strip()
                    append_chunk_payload_if_new(chunk_text, sorted(current_pages))

                    current_parts = []
                    current_pages = set()
                    current_word_count = 0

                current_parts.append(text)
                current_word_count += paragraph_words
                if page_number is not None:
                    current_pages.add(page_number)

            if current_parts:
                chunk_text = "\n".join(current_parts).strip()
                append_chunk_payload_if_new(chunk_text, sorted(current_pages))

            logger.info(
                f"Processed Azure analyze result",
                extra={
                    "lecture_id": lecture_id,
                    "course_id": course_id,
                    "sections_count": len(sections),
                    "chunks_count": chunk_count
                }
            )
            
            return chunk_payloads
            
        except Exception as e:
            logger.error("Failed to process Azure analyze result", exc_info=True)
            raise ChunkProcessingError(segment_index=0, message=str(e))

    async def _extract_element_text(
        self,
        prepared_content: AnalyzeResult,
        element_id: str,
        full_content: str
    ) -> Tuple[str, Optional[int], Optional[int]]:
        
        if "/paragraphs/" in element_id:
            idx = int(element_id.split("/")[-1])
            elements = self._get(prepared_content, "paragraphs", [])
            returned_idx = idx
        elif "/tables/" in element_id:
            idx = int(element_id.split("/")[-1])
            elements = self._get(prepared_content, "tables", [])
            returned_idx = None
        elif "/figures/" in element_id:
            idx = int(element_id.split("/")[-1])
            elements = self._get(prepared_content, "figures", [])
            returned_idx = None
        else:
            return "", None, None
        
        if idx >= len(elements):
            return "", None, None
        
        element = elements[idx]
        spans = self._get(element, "spans", [])


        page_number = None
        br = self._get(element, "bounding_regions", None)
        if br:
            page_number = self._get(br[0], "page_number", None)

        chunk_parts = []
        for span in spans:
            offset = self._get(span, "offset", 0)
            length = self._get(span, "length", 0)
            if 0 <= offset and length > 0:
                extracted_text = full_content[offset:offset + length]
                if extracted_text.strip():
                    chunk_parts.append(extracted_text)
        
        return "".join(chunk_parts), page_number,returned_idx


def get_chunking_service() -> ChunkingService:
    return ChunkingService()


    