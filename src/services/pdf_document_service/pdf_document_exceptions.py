from ..service_exceptions import ServiceException


class PdfDocumentException(ServiceException):
    def __init__(
        self,
        message: str = "PDF document service error",
        details=None,
        status_code: int = 500,
        error_code: str = "PDF_DOCUMENT_ERROR",
    ):
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            error_code=error_code,
        )


class InvalidPdfUrlError(PdfDocumentException):
    def __init__(self, details=None):
        super().__init__(
            message="Invalid PDF URL",
            details=details,
            status_code=400,
            error_code="INVALID_PDF_URL",
        )


class AzureDocAnalysisFailedError(PdfDocumentException):
    def __init__(self, details=None):
        super().__init__(
            message="Failed to analyze PDF with Azure Document Intelligence",
            details=details,
            status_code=502,
            error_code="AZURE_DOC_ANALYSIS_FAILED",
        )


class FitzNotInstalledError(PdfDocumentException):
    def __init__(self, details=None):
        super().__init__(
            message="PyMuPDF is not installed",
            details=details,
            status_code=500,
            error_code="FITZ_NOT_INSTALLED",
        )


class FitzPdfParseFailedError(PdfDocumentException):
    def __init__(self, details=None):
        super().__init__(
            message="Failed to parse PDF with Fitz",
            details=details,
            status_code=502,
            error_code="FITZ_PDF_PARSE_FAILED",
        )