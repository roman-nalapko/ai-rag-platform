import uuid

from pydantic import BaseModel, ConfigDict, Field


class DemoTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int
