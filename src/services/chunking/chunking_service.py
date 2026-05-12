from helpers.logger import get_logger
from models.chunk_model import ChunkMetadata
from models.vdb_payload_model import VDBChunkPayload
from .chunking_exceptions import ChunkProcessingError
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
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
                
                for element_id in elements:

                    chunk_text = await self._extract_element_text(
                        prepared_content, element_id, full_content
                    )

                    chunk_text = (chunk_text or "").strip()
                    if not chunk_text:
                        continue

                    metadata = ChunkMetadata(
                        chunk_id=str(uuid4()),
                        lecture_id=lecture_id,
                        lecture_name=lecture_name,
                        subject_id=subject_id,
                        subject_name=subject_name,
                        chunk_index=chunk_count + 1,
                        lecture_order=lecture_order,
                    )

                    chunk_payloads.append(
                        VDBChunkPayload(
                            text=chunk_text,
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
    ) -> str:

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
            return ""
        
        if idx >= len(elements):
            return ""
        
        element = elements[idx]
        spans = self._get(element, "spans", [])
        

        chunk_parts = []
        for span in spans:
            offset = self._get(span, "offset", 0)
            length = self._get(span, "length", 0)
            if 0 <= offset and length > 0:
                extracted_text = full_content[offset:offset + length]
                if extracted_text.strip():
                    chunk_parts.append(extracted_text)
        
        return "".join(chunk_parts)


def get_chunking_service() -> ChunkingService:
    return ChunkingService()


    