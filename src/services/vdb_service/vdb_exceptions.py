from ..service_exceptions import ServiceException


class VectorDBException(ServiceException):
    def __init__(
        self,
        message="Vector DB service error",
        details=None,
        status_code: int = 500,
        error_code: str = "VECTOR_DB_ERROR",
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class VectorizationError(VectorDBException):
    def __init__(self, message="Vectorization failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=502,
            error_code="VECTORIZATION_FAILED",
        )