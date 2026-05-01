from fastapi import Depends
from uuid import uuid4

from integrations.integrations_dependencies import get_vdb_client
from integrations.vector_db import VectorDBInterface
from schemas import GradingRequest, GradingResponse, RefGradingRequest, RefGradingResponse
from services import ChunkEmbeddingService, get_chunk_embedding_service
from services.grading import (
	AnswerChunkingService,
	ScoringService,
	StudentAnswerChunkingService,
	get_answer_chunking_service,
	get_scoring_service,
	get_student_answer_chunking_service,
)

class GradingOrchestrator:
	_VDB_COLLECTION_NAME = "answer_references"
	_BATCH_SIZE = 250

	def __init__(
		self,
		chunking_service: AnswerChunkingService,
		student_chunking_service: StudentAnswerChunkingService,
		embedding_service: ChunkEmbeddingService,
		vdb_client: VectorDBInterface,
		scoring_service: ScoringService,
	):
		self.chunking_service = chunking_service
		self.student_chunking_service = student_chunking_service
		self.embedding_service = embedding_service
		self.vdb_client = vdb_client
		self.scoring_service = scoring_service

	async def set_reference_answer(self, payload: RefGradingRequest) -> RefGradingResponse:
		question_id = str(uuid4())
		payloads = await self.chunking_service.build_reference_chunks(
			question_id=question_id,
			answer=payload.answer,
		)
		if not payloads:
			return RefGradingResponse(question_id=question_id)

		texts, vectors, record_ids, metadatas = await self.embedding_service.embed_chunks(
			payloads=payloads,
			id_factory=lambda index: str(uuid4()),
		)

		await self.vdb_client.store_batch(
			collection_name=self._VDB_COLLECTION_NAME,
			batch_size=self._BATCH_SIZE,
			texts=texts,
			vectors=vectors,
			record_ids=record_ids,
			metadatas=metadatas,
			use_bm25=False,
			fields_for_indexing=[{"name": "question_id", "type": str}],
		)
  
		return RefGradingResponse(question_id=question_id)

	async def grade_answer(self, payload: GradingRequest) -> GradingResponse:
		reference_chunks = self.chunking_service.get_reference_chunks(
			question_id=payload.question_id,
			collection_name=self._VDB_COLLECTION_NAME,
			include_vectors=False,
		)

		student_chunks = self.student_chunking_service.chunk_and_extract(
			student_answer=payload.answer,
		)

		if not student_chunks:
			scoring_result = self.scoring_service.calculate_weighted_score(
				reference_chunks=reference_chunks,
				student_chunks=[],
			)
			return GradingResponse(
				final_score=scoring_result["final_score"],
				coverage=scoring_result["coverage"],
				details=scoring_result["details"],
			)

		scoring_result = self.scoring_service.calculate_weighted_score(
			reference_chunks=reference_chunks,
			student_chunks=student_chunks,
		)

		return GradingResponse(
			final_score=scoring_result["final_score"],
			coverage=scoring_result["coverage"],
			details=scoring_result["details"],
		)


def get_grading_orchestrator(
	chunking_service: AnswerChunkingService = Depends(get_answer_chunking_service),
	student_chunking_service: StudentAnswerChunkingService = Depends(get_student_answer_chunking_service),
	embedding_service: ChunkEmbeddingService = Depends(get_chunk_embedding_service),
	vdb_client: VectorDBInterface = Depends(get_vdb_client),
	scoring_service: ScoringService = Depends(get_scoring_service),
) -> GradingOrchestrator:
	return GradingOrchestrator(
		chunking_service=chunking_service,
		student_chunking_service=student_chunking_service,
		embedding_service=embedding_service,
		vdb_client=vdb_client,
		scoring_service=scoring_service,
	)

