from core.app_exceptions import AppException


class LLMException(AppException):
    def __init__(
        self,
        message: str = "LLM layer error",
        status_code: int = 500,
        error_code: str = "LLM_ERROR",
        details: dict = None,
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details,
        )



class LLMInitializationException(LLMException):
    def __init__(self, provider: str, init_error: str):
        super().__init__(
            message=f"{provider} initialization failed",
            error_code="LLM_INIT_ERROR",
            details={"provider": provider, "error": init_error},
        )


# Model Errors
class LLMModelNotSetException(LLMException):
    def __init__(self, operation: str, model_type: str, provider: str):
        super().__init__(
            message=f"{model_type} model not set for {operation}",
            error_code="LLM_MODEL_NOT_SET",
            details={
                "operation": operation,
                "model_type": model_type,
                "provider": provider,
            },
        )


# API / Provider Errors
class LLMAPINotAvailableException(LLMException):
    def __init__(self, provider: str, api_endpoint: str, network_error: str):
        super().__init__(
            message=f"{provider} API not available",
            error_code="LLM_API_DOWN",
            details={
                "provider": provider,
                "endpoint": api_endpoint,
                "error": network_error,
            },
        )


class LLMRateLimitException(LLMException):
    def __init__(self, model_id: str, retry_after: int = None):
        super().__init__(
            message="Rate limit exceeded",
            error_code="LLM_RATE_LIMIT",
            status_code=429,
            details={
                "model_id": model_id,
                "retry_after": retry_after,
            },
        )


# Response Errors
class LLMInvalidResponseException(LLMException):
    def __init__(self, model_id: str, response_data: str, validation_error: str):
        super().__init__(
            message="Invalid response from LLM",
            error_code="LLM_INVALID_RESPONSE",
            details={
                "model_id": model_id,
                "error": validation_error,
                "response": response_data,
            },
        )


# Embedding Errors
class LLMEmbeddingException(LLMException):
    def __init__(self, model_id: str, text_sample: str, embedding_error: str):
        super().__init__(
            message="Embedding generation failed",
            error_code="LLM_EMBEDDING_ERROR",
            details={
                "model_id": model_id,
                "text_sample": text_sample,
                "error": embedding_error,
            },
        )