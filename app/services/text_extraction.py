import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PyPdfError


class DocumentExtractionError(ValueError):
    """Raised when text cannot be extracted from an uploaded document."""


class TextExtractionService:
    async def extract(self, file: UploadFile, content_type: str) -> str:
        data = await file.read()

        if content_type == "text/plain":
            return self._extract_txt(data)
        if content_type == "application/pdf":
            return await asyncio.to_thread(self._extract_pdf, data)

        raise DocumentExtractionError(f"Unsupported content type: {content_type}")

    async def extract_path(self, path: Path, content_type: str) -> str:
        try:
            data = await asyncio.to_thread(path.read_bytes)
        except OSError as error:
            raise DocumentExtractionError(
                "Stored document could not be read"
            ) from error

        if content_type == "text/plain":
            return self._extract_txt(data)
        if content_type == "application/pdf":
            return await asyncio.to_thread(self._extract_pdf, data)

        raise DocumentExtractionError(f"Unsupported content type: {content_type}")

    @staticmethod
    def _extract_txt(data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DocumentExtractionError(
                "TXT documents must contain valid UTF-8 text"
            ) from error

    @staticmethod
    def _extract_pdf(data: bytes) -> str:
        try:
            reader = PdfReader(BytesIO(data), strict=False)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except (PyPdfError, OSError, ValueError) as error:
            raise DocumentExtractionError(
                "Text could not be extracted from the PDF document"
            ) from error
