import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DemoTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class RegisterRequest(BaseModel):
    """Register a new user with email + password."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")


class LoginRequest(BaseModel):
    """Authenticate with email + password."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int
