from pathlib import Path

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

    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_API_KEY: str = "lm-studio"
    LM_STUDIO_CHAT_MODEL: str
    LM_STUDIO_EMBEDDING_MODEL: str
    LM_STUDIO_TIMEOUT_SECONDS: float = Field(default=300.0, gt=0)
    LM_STUDIO_MAX_TOKENS: int = Field(default=64, ge=1, le=4096)


settings = Settings()
