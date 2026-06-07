from services.service_exceptions import ServiceException


class ChatbotServiceException(ServiceException):
    def __init__(
        self,
        message: str = "Chatbot service error",
        details=None,
        status_code: int = 500,
        error_code: str = "CHATBOT_SERVICE_ERROR",
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class ChatbotValidationError(ChatbotServiceException):
    def __init__(self, message: str = "Chatbot request validation failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=400,
            error_code="CHATBOT_VALIDATION_ERROR",
        )


class ChatbotProcessingError(ChatbotServiceException):
    def __init__(self, message: str = "Chatbot processing failed", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=500,
            error_code="CHATBOT_PROCESSING_ERROR",
        )


class ChatbotExternalError(ChatbotServiceException):
    def __init__(self, message: str = "External dependency failure during chat", details=None):
        super().__init__(
            message=message,
            details=details,
            status_code=502,
            error_code="CHATBOT_EXTERNAL_ERROR",
        )
