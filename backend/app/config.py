from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://recon:recon@localhost:5432/bank_recon"
    SYNC_DATABASE_URL: str = "postgresql://recon:recon@localhost:5432/bank_recon"
    REDIS_URL: str = "redis://localhost:6379/0"
    GEMINI_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    UPLOAD_DIR: str = "/tmp/bank-recon-uploads"
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
