import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_base_id: uuid.UUID
    query: str = Field(min_length=1, max_length=4096)
    limit: int = Field(default=5, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("Query must not be empty")
        return query


class SearchResultResponse(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    filename: str
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultResponse]
