from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite+aiosqlite:///./pantauind.db")
    google_cse_api_key: str = Field(default="")
    google_cse_id: str = Field(default="")
    secret_key: str = Field(default="dev-secret-change-in-prod")
    frontend_url: str = Field(default="http://localhost:5173")
    evidence_dir: str = Field(default="./evidence")
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/0")
    api_key: str = Field(default="")
    webhook_url: str = Field(default="")
    shodan_api_key: str = Field(default="")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
