from typing import Literal

from pydantic import BaseModel, Field


class LLMHealthResponse(BaseModel):
    status: Literal["ok"]
    provider: Literal["lm-studio"]
    embedding_dimensions: int = Field(gt=0)


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    checks: dict[Literal["database", "qdrant"], Literal["ok"]]
