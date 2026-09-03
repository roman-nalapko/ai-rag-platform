from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Local AI RAG Platform"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    QDRANT_URL: str
    UPLOAD_STORAGE_PATH: Path = Path("storage/uploads")
    UPLOAD_MAX_BYTES: int = Field(default=10 * 1024 * 1024, gt=0)

    # ── LLM Provider ───────────────────────────────────────────────────────
    # Set LLM_PROVIDER=openai to use the OpenAI API instead of LM Studio.
    # This enables cloud deployment without a local GPU.
    LLM_PROVIDER: Literal["lm_studio", "openai"] = "lm_studio"

    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_API_KEY: str = "lm-studio"
    LM_STUDIO_CHAT_MODEL: str = ""
    LM_STUDIO_EMBEDDING_MODEL: str = ""
    LM_STUDIO_TIMEOUT_SECONDS: float = Field(default=300.0, gt=0)
    LM_STUDIO_MAX_TOKENS: int = Field(default=64, ge=1, le=4096)

    # OpenAI settings (used when LLM_PROVIDER=openai)
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    RERANKING_ENABLED: bool = False
    RERANKING_CANDIDATE_MULTIPLIER: int = Field(default=3, ge=1, le=10)

    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1)
    DEMO_MODE_ENABLED: bool = True

    DOCUMENT_WORKER_ENABLED: bool = True
    DOCUMENT_WORKER_POLL_SECONDS: float = Field(default=2.0, gt=0)
    DOCUMENT_WORKER_STALE_AFTER_SECONDS: float = Field(default=900.0, gt=0)

    @property
    def llm_base_url(self) -> str:
        """Resolved LLM base URL depending on the active provider."""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_BASE_URL
        return self.LM_STUDIO_BASE_URL

    @property
    def llm_api_key(self) -> str:
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_API_KEY
        return self.LM_STUDIO_API_KEY

    @property
    def llm_chat_model(self) -> str:
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_CHAT_MODEL
        return self.LM_STUDIO_CHAT_MODEL

    @property
    def llm_embedding_model(self) -> str:
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_EMBEDDING_MODEL
        return self.LM_STUDIO_EMBEDDING_MODEL


settings = Settings()  # type: ignore[call-arg]  # Values are loaded from the environment.
