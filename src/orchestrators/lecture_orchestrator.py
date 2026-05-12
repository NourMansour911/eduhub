from fastapi import Depends
from models import LectureModel
from schemas import LectureStoreRequest, LectureStoreResponse
from services.lectures.lecture_service import LectureService, get_lecture_service
from services.summarize.summarize_service import get_summarize_service, SummarizeService
from services.chunking.chunking_service import ChunkingService, get_chunking_service
from services.embedding.embedding_service import ChunkEmbeddingService, get_chunk_embedding_service
from services.vdb_service.vectordb_service import VDBService, get_vdb_service
from services.service_exceptions import ProcessingError, ServiceException
from helpers import get_logger
from helpers.utils import serialize_content
import json
from pathlib import Path
logger = get_logger(__name__)


class LectureOrchestrator:

    
    def __init__(
        self,
        lecture_service: LectureService,
        summarize_service: SummarizeService,
        chunking_service: ChunkingService,
        vdb_service: VDBService,
        embedding_service: ChunkEmbeddingService,
    ):
        self.lecture_service = lecture_service
        self.summarize_service = summarize_service
        self.chunking_service = chunking_service
        self.vdb_service = vdb_service
        self.embedding_service = embedding_service

    async def store_lecture_with_summaries(self, payload: LectureStoreRequest) -> LectureStoreResponse:

        prepared_content = await self.lecture_service.prepare_lecture_content(payload.url)
        

        try:
            
            chunk_payloads = await self.chunking_service.process_azure_analyze_result(
                prepared_content=prepared_content,
                lecture_id=payload.lecture_id,
                subject_id=payload.subject_id,
                lecture_name=payload.lecture_name,
                subject_name=payload.subject_name,
                lecture_order=payload.order,
            )

            texts, vectors, ids, metas = [], [], [], []
            if chunk_payloads:
                texts, vectors, ids, metas = await self.embedding_service.embed_chunks(chunk_payloads)
            

            collection_name = "lectures"
            if texts and vectors:
                await self.vdb_service.store_batch(
                    collection_name=collection_name,
                    batch_size=len(texts),
                    texts=texts,
                    vectors=vectors,
                    record_ids=ids,
                    metadatas=metas,
                    use_bm25=True,
                    fields_for_indexing=[
                        {"name": "lecture_name", "type": str},
                        {"name": "subject_name", "type": str},
                        {"name": "lecture_id", "type": str},
                        {"name": "subject_id", "type": str},
                    ]
                )
                logger.info(
                    f"Stored {len(texts)} chunks in VDB",
                    extra={"lecture_id": payload.lecture_id, "collection": collection_name}
                )
        except ServiceException:
            raise
        except Exception as e:
            logger.error(
                "Failed to process and store chunks",
                exc_info=True,
                extra={"lecture_id": payload.lecture_id},
            )
            raise ProcessingError(
                message="Failed to process and store chunks",
                details={
                    "error": str(e),
                    "type": type(e).__name__,
                    "context": {
                        "lecture_id": payload.lecture_id,
                        "subject_id": payload.subject_id,
                    },
                },
            ) from e
        
        
        raw_content = prepared_content.content
        """ summaries = await self.summarize_service.generate_all_summaries(
            lecture_content=raw_content,
            lecture_id=payload.lecture_id,
            subject_id=payload.subject_id,
        ) """
        
        projects_root = Path(__file__).parents[3]  # Navigate to d:\training\AI\projects
        json_file = projects_root / "demos" /"eduhub_demos"/ "test_jsons" / "summaries.json"
            
        with open(json_file, "r", encoding="utf-8") as f:
            summaries = json.load(f)
                
        lecture = LectureModel(
            lecture_id=payload.lecture_id,
            lecture_name=payload.lecture_name,
            subject_id=payload.subject_id,
            subject_name=payload.subject_name,
            summaries=summaries,
            content=raw_content,
            order=payload.order,
        )
        logger.info(
            f"Generated summaries for lecture {payload.lecture_id}",
            extra={"levels": list(summaries.keys())}
        )

        _ = await self.lecture_service.add_lecture(lecture)
        
        return LectureStoreResponse(status="success", lecture_id=lecture.lecture_id)


def get_lecture_orchestrator(
    lecture_service: LectureService = Depends(get_lecture_service),
    summarize_service: SummarizeService = Depends(get_summarize_service),
    chunking_service: ChunkingService = Depends(get_chunking_service),
    vdb_service: VDBService = Depends(get_vdb_service),
    embedding_service: ChunkEmbeddingService = Depends(get_chunk_embedding_service),
) -> LectureOrchestrator:
    return LectureOrchestrator(
        lecture_service=lecture_service,
        summarize_service=summarize_service,
        chunking_service=chunking_service,
        vdb_service=vdb_service,
        embedding_service=embedding_service,
    )
