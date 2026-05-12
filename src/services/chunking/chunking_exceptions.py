from core.app_exceptions import AppException
from ..service_exceptions import ServiceException


class ChunkingServiceException(ServiceException):
    """Base exception for the Chunking microservice."""
    def __init__(self, message="Chunking service error", details=None):
        super().__init__(message=message, details=details)


class ChunkProcessingError(ChunkingServiceException):
    def __init__(self, segment_index: int, message: str = "Error processing chunk"):
        details = {"segment_index": segment_index}
        super().__init__(message=message, details=details)


class EmbeddingError(ChunkingServiceException):
    def __init__(self, segment_index: int, message: str = "Failed to generate embedding"):
        details = {"segment_index": segment_index}
        super().__init__(message=message, details=details)