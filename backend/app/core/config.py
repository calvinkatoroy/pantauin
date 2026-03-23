from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite+aiosqlite:///./pantauin.db")
    google_cse_api_key: str = Field(default="")
    google_cse_id: str = Field(default="")
    secret_key: str = Field(default="dev-secret-change-in-prod")
    frontend_url: str = Field(default="http://localhost:5173")
    evidence_dir: str = Field(default="./evidence")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
