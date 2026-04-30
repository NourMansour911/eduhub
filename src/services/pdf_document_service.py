from urllib.parse import urlparse
from urllib.request import Request, urlopen
import base64

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

from core import AppException, Settings
from helpers import get_logger

logger = get_logger(__name__)


class PdfDocumentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = DocumentIntelligenceClient(
            endpoint=self.settings.AZURE_DOC_ENDPOINT,
            credential=AzureKeyCredential(self.settings.AZURE_DOC_KEY),
        )

    def analyze_pdf_url(self, pdf_url: str) -> dict:
        self._validate_pdf_url(pdf_url)

        try:
            poller = self.client.begin_analyze_document(
                model_id=self.settings.AZURE_DOC_DEPLOYMENT,
                body=AnalyzeDocumentRequest(url_source=pdf_url),
            )
            result = poller.result()

            result_payload = result.as_dict() if hasattr(result, "as_dict") else {}

            azure_output = {
                "model_id": self.settings.AZURE_DOC_DEPLOYMENT,
                "pdf_url": pdf_url,
                "content": getattr(result, "content", None),
                "pages_count": len(getattr(result, "pages", []) or []),
                "result": self._json_safe(result_payload),
            }

            fitz_output = self.analyze_pdf_url_with_fitz(pdf_url=pdf_url)

            return {
                "pdf_url": pdf_url,
                "azure_document_intelligence": azure_output,
                "fitz": fitz_output,
            }
        except AppException:
            raise
        except Exception as exc:
            logger.error("Azure Document Intelligence call failed", exc_info=True)
            raise AppException(
                message="Failed to analyze PDF with Azure Document Intelligence",
                status_code=502,
                error_code="AZURE_DOC_ANALYSIS_FAILED",
                details={"error": str(exc), "pdf_url": pdf_url},
            )

    def analyze_pdf_url_with_fitz(self, pdf_url: str) -> dict:
        self._validate_pdf_url(pdf_url)

        try:
            try:
                import fitz
            except ImportError:
                try:
                    import pymupdf as fitz
                except ImportError as exc:
                    raise AppException(
                        message="PyMuPDF is not installed",
                        status_code=500,
                        error_code="FITZ_NOT_INSTALLED",
                        details={
                            "error": str(exc),
                            "hint": "Install with: pip install PyMuPDF",
                        },
                    )

            request = Request(
                pdf_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                },
            )
            with urlopen(request) as response:
                pdf_bytes = response.read()

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = []
            for page_index in range(doc.page_count):
                page = doc[page_index]
                pages.append(
                    {
                        "page_number": page_index + 1,
                        "text": page.get_text(),
                        "blocks": page.get_text("blocks"),
                        "rawdict": page.get_text("rawdict"),
                    }
                )

            metadata = doc.metadata
            doc.close()

            return {
                "pdf_url": pdf_url,
                "page_count": len(pages),
                "metadata": self._json_safe(metadata),
                "pages": self._json_safe(pages),
            }
        except AppException:
            raise
        except Exception as exc:
            logger.error("Fitz PDF extraction failed", exc_info=True)
            raise AppException(
                message="Failed to parse PDF with Fitz",
                status_code=502,
                error_code="FITZ_PDF_PARSE_FAILED",
                details={"error": str(exc), "pdf_url": pdf_url},
            )

    def compare_azure_and_fitz(self, pdf_url: str) -> dict:
        self._validate_pdf_url(pdf_url)

        try:
            poller = self.client.begin_analyze_document(
                model_id=self.settings.AZURE_DOC_DEPLOYMENT,
                body=AnalyzeDocumentRequest(url_source=pdf_url),
            )
            result = poller.result()
            result_payload = result.as_dict() if hasattr(result, "as_dict") else {}

            azure_output = {
                "model_id": self.settings.AZURE_DOC_DEPLOYMENT,
                "pdf_url": pdf_url,
                "content": getattr(result, "content", None),
                "pages_count": len(getattr(result, "pages", []) or []),
                "result": self._json_safe(result_payload),
            }
        except Exception as exc:
            logger.error("Azure Document Intelligence call failed", exc_info=True)
            raise AppException(
                message="Failed to analyze PDF with Azure Document Intelligence",
                status_code=502,
                error_code="AZURE_DOC_ANALYSIS_FAILED",
                details={"error": str(exc), "pdf_url": pdf_url},
            )

        fitz_output = self.analyze_pdf_url_with_fitz(pdf_url=pdf_url)

        return {
            "pdf_url": pdf_url,
            "azure_document_intelligence": azure_output,
            "fitz": fitz_output,
        }

    def _json_safe(self, value):
        if isinstance(value, bytes):
            return {
                "__type__": "bytes",
                "encoding": "base64",
                "value": base64.b64encode(value).decode("ascii"),
            }
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(v) for v in value]
        return value

    def _validate_pdf_url(self, pdf_url: str) -> None:
        parsed = urlparse(pdf_url)
        if parsed.scheme not in {"http", "https"}:
            raise AppException(
                message="Invalid PDF URL",
                status_code=400,
                error_code="INVALID_PDF_URL",
                details={"pdf_url": pdf_url},
            )
