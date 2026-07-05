import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_base_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    question: str = Field(min_length=1, max_length=4096)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("Question must not be empty")
        return question


class QASourceResponse(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    filename: str
    chunk_index: int
    score: float
    content: str


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: list[QASourceResponse]
