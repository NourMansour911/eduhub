from ..service_exceptions import ServiceException


class LectureServiceException(ServiceException):
    def __init__(
        self,
        message: str = "Lecture service error",
        details=None,
        status_code: int = 500,
        error_code: str = "LECTURE_SERVICE_ERROR",
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class LectureValidationError(LectureServiceException):
    def __init__(self, message: str = "Lecture validation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=400,
            error_code="LECTURE_VALIDATION_ERROR",
        )


class LectureNotFoundError(LectureServiceException):
    def __init__(self, message: str = "Lecture not found", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=404,
            error_code="LECTURE_NOT_FOUND",
        )


class LectureConflictError(LectureServiceException):
    def __init__(self, message: str = "Lecture already exists", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=409,
            error_code="LECTURE_CONFLICT",
        )