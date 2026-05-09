from services.service_exceptions import ServiceException


class SummarizeServiceException(ServiceException):
    def __init__(self, message="Summarize service error", details=None, status_code=500, error_code="SUMMARIZE_SERVICE_ERROR"):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class SummarizeNotFoundError(SummarizeServiceException):
    def __init__(self, message="Lecture not found", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=404,
            error_code="SUMMARIZE_LECTURE_NOT_FOUND",
        )


class SummarizeProcessingError(SummarizeServiceException):
    def __init__(self, message="Summary generation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=500,
            error_code="SUMMARIZE_PROCESSING_ERROR",
        )


class SummarizeValidationError(SummarizeServiceException):
    def __init__(self, message="Summarize validation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=400,
            error_code="SUMMARIZE_VALIDATION_ERROR",
        )
