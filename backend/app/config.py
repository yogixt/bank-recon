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

    # AgentMail
    AGENTMAIL_API_KEY: str = ""
    AGENTMAIL_INBOX_ID: str = ""  # e.g. "recon@agentmail.to" or "recon@unomok.com"
    # Email identification patterns
    HDFC_SENDER_PATTERN: str = "hdfcbank"
    HDFC_SUBJECT_PATTERN: str = "Account Statement"
    HDFC_ZIP_PASSWORD: str = ""  # Password for HDFC encrypted zip (e.g. "BIJ8829")
    BRIDGE_SUBJECT_PATTERN: str = "Bridge File"
    LMS_SUBJECT_PATTERN: str = ""
    NOTIFICATION_RECIPIENTS: str = "bijay@unomok.com"
    NOTIFICATION_FROM_NAME: str = "Bank Recon System"
    POLL_INTERVAL_MINUTES: int = 15
    AUTO_RECONCILE_ENABLED: bool = True
    STALE_ALERT_HOUR_IST: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
