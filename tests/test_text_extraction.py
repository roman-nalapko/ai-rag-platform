"""Unit tests for TextExtractionService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.text_extraction import DocumentExtractionError, TextExtractionService

# ── TXT extraction ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_txt_returns_decoded_content() -> None:
    content = "Hello, RAG platform!"
    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=content.encode("utf-8"))

    service = TextExtractionService()
    result = await service.extract(fake_file, "text/plain")

    assert result == content


@pytest.mark.asyncio
async def test_extract_txt_raises_on_non_utf8() -> None:
    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=b"\xff\xfe invalid latin bytes")

    service = TextExtractionService()
    with pytest.raises(DocumentExtractionError, match="UTF-8"):
        await service.extract(fake_file, "text/plain")


@pytest.mark.asyncio
async def test_extract_unsupported_content_type_raises() -> None:
    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=b"data")

    service = TextExtractionService()
    with pytest.raises(DocumentExtractionError, match="Unsupported"):
        await service.extract(fake_file, "application/octet-stream")


# ── PDF extraction ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_pdf_calls_pypdf() -> None:
    """Verify PDF extraction calls PdfReader and joins page text."""
    page1 = MagicMock()
    page1.extract_text.return_value = "Page one content"
    page2 = MagicMock()
    page2.extract_text.return_value = "Page two content"

    fake_reader = MagicMock()
    fake_reader.pages = [page1, page2]

    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=b"%PDF-1.4 fake")

    service = TextExtractionService()
    with patch("app.services.text_extraction.PdfReader", return_value=fake_reader):
        result = await service.extract(fake_file, "application/pdf")

    assert "Page one content" in result
    assert "Page two content" in result


@pytest.mark.asyncio
async def test_extract_pdf_raises_on_pypdf_error() -> None:
    from pypdf.errors import PyPdfError

    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=b"not a real pdf")

    service = TextExtractionService()
    with patch(
        "app.services.text_extraction.PdfReader", side_effect=PyPdfError("bad pdf")
    ):
        with pytest.raises(DocumentExtractionError, match="PDF"):
            await service.extract(fake_file, "application/pdf")


@pytest.mark.asyncio
async def test_extract_pdf_handles_pages_with_no_text() -> None:
    """Pages that return None from extract_text should be treated as empty strings."""
    page1 = MagicMock()
    page1.extract_text.return_value = None
    page2 = MagicMock()
    page2.extract_text.return_value = "Real content"

    fake_reader = MagicMock()
    fake_reader.pages = [page1, page2]

    fake_file = AsyncMock()
    fake_file.read = AsyncMock(return_value=b"%PDF-fake")

    service = TextExtractionService()
    with patch("app.services.text_extraction.PdfReader", return_value=fake_reader):
        result = await service.extract(fake_file, "application/pdf")

    assert "Real content" in result


# ── extract_path ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_path_raises_on_missing_file() -> None:
    from pathlib import Path

    service = TextExtractionService()
    missing = Path("/nonexistent/path/file.txt")
    with pytest.raises(DocumentExtractionError, match="read"):
        await service.extract_path(missing, "text/plain")
