class AppException(Exception):
    def __init__(self, message: str = "Something went wrong", status_code: int = 500, error_code: str = "INTERNAL_SERVER_ERROR",details=None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

