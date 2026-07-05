import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    content_type: str
    created_at: datetime
    processed: bool
    status: Literal["pending", "processing", "indexed", "failed"]
    error_message: str | None


class DocumentUploadResponse(DocumentResponse):
    chunks_count: int
    indexed: bool


class DocumentDetailResponse(DocumentResponse):
    chunks_count: int
