from core.app_exceptions import AppException


class ServiceException(AppException):
    def __init__(self, message="Service layer error", details=None,status_code=500):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code="SERVICE_ERROR",
            details=details
        )


class ValidationError(ServiceException):
    def __init__(self, message="Validation failed", details=None):
        super().__init__(message=message, details=details)


class NotFoundError(ServiceException):
    def __init__(self, message="Resource not found", details=None):
        super().__init__(message=message, details=details,status_code=404)


class ProcessingError(ServiceException):
    def __init__(self, message="Processing error", details=None):
        super().__init__(message=message, details=details)


class ExternalServiceError(ServiceException):
    def __init__(self, message="External service error", details=None):
        super().__init__(message=message, details=details)