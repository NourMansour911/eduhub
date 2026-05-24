from services.service_exceptions import ServiceException


class SessionServiceException(ServiceException):
    def __init__(
        self,
        message: str = "Session service error",
        details=None,
        status_code: int = 500,
        error_code: str = "SESSION_SERVICE_ERROR",
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class SessionNotFoundError(SessionServiceException):
    def __init__(self, message: str = "Session not found", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=404,
            error_code="SESSION_NOT_FOUND",
        )


class SessionValidationError(SessionServiceException):
    def __init__(self, message: str = "Session validation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=400,
            error_code="SESSION_VALIDATION_ERROR",
        )


class SessionProcessingError(SessionServiceException):
    def __init__(self, message: str = "Session processing failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=500,
            error_code="SESSION_PROCESSING_ERROR",
        )