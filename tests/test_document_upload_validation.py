import httpx
import pytest

from app.core.config import settings

VALID_UUID = "11111111-1111-4111-8111-111111111111"


@pytest.mark.asyncio
async def test_document_upload_rejects_unsupported_file_type(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/documents/upload",
        data={"knowledge_base_id": VALID_UUID},
        files={
            "file": (
                "document.md",
                b"# Markdown is not supported",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 415
    assert response.json() == {
        "detail": "Only PDF (application/pdf) and TXT (text/plain) files are supported"
    }


@pytest.mark.asyncio
async def test_document_upload_rejects_oversized_file_before_database_access(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "UPLOAD_MAX_BYTES", 1)

    response = await api_client.post(
        "/documents/upload",
        data={"knowledge_base_id": VALID_UUID},
        files={
            "file": (
                "document.txt",
                b"too large",
                "text/plain",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Uploaded file exceeds the 1 byte limit"
    }
