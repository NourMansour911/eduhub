from ..service_exceptions import ServiceException


class VectorDBException(ServiceException):
    def __init__(self, message="Vector DB service error", details=None):
        super().__init__(message=message, details=details)


class VectorizationError(VectorDBException):
    def __init__(self, message="Vectorization failed", details=None):
        super().__init__(message=message, details=details)