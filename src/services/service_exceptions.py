from core.app_exceptions import AppException
from helpers import get_logger

logger = get_logger(__name__)


class ServiceException(AppException):
    def __init__(
        self,
        message: str = "Service layer error",
        details=None,
        status_code: int = 500,
        error_code: str = "SERVICE_ERROR",
    ):
        logger.error(
            message,
            extra={
                "status_code": status_code,
                "error_code": error_code,
                "details": details,
            },
        )
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )


class ValidationError(ServiceException):
    def __init__(self, message="Validation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=400,
            error_code="VALIDATION_ERROR",
        )


class NotFoundError(ServiceException):
    def __init__(self, message="Resource not found", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
        )


class ProcessingError(ServiceException):
    def __init__(self, message="Processing error", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=500,
            error_code="PROCESSING_ERROR",
        )


class ExternalServiceError(ServiceException):
    def __init__(self, message="External service error", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
        )