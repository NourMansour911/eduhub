import re

from helpers.logger import get_logger
from models.chunk_model import ChunkMetadata
from models.vdb_payload_model import VDBChunkPayload
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
        subject_id: str,
        lecture_name: str,
        subject_name: str,
        lecture_order: Optional[int] = None,
    ) -> List[VDBChunkPayload]:

        chunk_payloads: List[VDBChunkPayload] = []
        chunk_count = 0
        

        full_content = self._get(prepared_content, "content", "")
        
        try:

            sections = self._get(prepared_content, "sections", [])
            
            for section in sections:
                
                elements = self._get(section, "elements", [])

                section_parts: List[str] = []
                page_numbers: Set[int] = set()
                for element_id in elements:
                    element_text, element_page = await self._extract_element_text(
                        prepared_content, element_id, full_content
                    )
                    element_text = (element_text or "").strip()
                    if element_text:
                        section_parts.append(element_text)
                    if element_page is not None:
                        page_numbers.add(element_page)

                section_text = "\n".join(section_parts).strip()
                if not section_text:
                    continue

                metadata = ChunkMetadata(
                    chunk_id=str(uuid4()),
                    lecture_id=lecture_id,
                    lecture_name=lecture_name,
                    subject_id=subject_id,
                    subject_name=subject_name,
                    chunk_index=chunk_count + 1,
                    lecture_order=lecture_order,
                    pages_number=sorted(list(page_numbers)),
                )
                
                
                section_text = re.sub(r"<figure>\s*</figure>", "", section_text)
                chunk_payloads.append(
                    VDBChunkPayload(
                        text=section_text,
                        metadata=metadata.model_dump(),
                    )
                )
                chunk_count += 1


            logger.info(
                f"Processed Azure analyze result",
                extra={
                    "lecture_id": lecture_id,
                    "subject_id": subject_id,
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
    ) -> Tuple[str, Optional[int]]:

        if "/paragraphs/" in element_id:
            idx = int(element_id.split("/")[-1])
            elements = self._get(prepared_content, "paragraphs", [])
        elif "/tables/" in element_id:
            idx = int(element_id.split("/")[-1])
            elements = self._get(prepared_content, "tables", [])
        elif "/figures/" in element_id:
            idx = int(element_id.split("/")[-1])
            elements = self._get(prepared_content, "figures", [])
        else:
            return "", None
        
        if idx >= len(elements):
            return "", None
        
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
        
        return "".join(chunk_parts), page_number


def get_chunking_service() -> ChunkingService:
    return ChunkingService()


    