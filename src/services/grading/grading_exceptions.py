from services.service_exceptions import ServiceException


class GradingException(ServiceException):
    def __init__(self, message="Grading service error", details=None, status_code=500):
        super().__init__(message=message, details=details, status_code=status_code)


class ReferenceAnswerNotFoundError(GradingException):
    def __init__(self, question_id: str, details=None):
        super().__init__(
            message="Reference answer not found",
            details={"question_id": question_id, **(details or {})},
            status_code=404,
        )


class InvalidReferenceAnswerError(GradingException):
    def __init__(self, message="Reference answer cannot be empty", details=None):
        super().__init__(message=message, details=details, status_code=400)


class InvalidStudentAnswerError(GradingException):
    def __init__(self, message="Student answer cannot be empty", details=None):
        super().__init__(message=message, details=details, status_code=400)


class GradingProcessingError(GradingException):
    def __init__(self, message="Failed to evaluate the student answer", details=None):
        super().__init__(message=message, details=details, status_code=500)
