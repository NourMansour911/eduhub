from services.service_exceptions import ServiceException


class EmbeddingServiceException(ServiceException):
    def __init__(
        self,
        message: str = "Embedding service error",
        details=None,
        status_code: int = 500,
        error_code: str = "EMBEDDING_SERVICE_ERROR",
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class EmptyChunkTextError(EmbeddingServiceException):
    def __init__(self, details=None):
        super().__init__(
            message="Chunk text is empty",
            details=details,
            status_code=400,
            error_code="EMPTY_CHUNK_TEXT",
        )


class EmbeddingGenerationError(EmbeddingServiceException):
    def __init__(self, details=None):
        super().__init__(
            message="Embedding generation failed",
            details=details,
            status_code=502,
            error_code="EMBEDDING_GENERATION_FAILED",
        )
