from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite+aiosqlite:///./pantauind.db")
    serper_api_key: str = Field(default="")
    secret_key: str = Field(default="dev-secret-change-in-prod")
    frontend_url: str = Field(default="http://localhost:5173")
    evidence_dir: str = Field(default="./evidence")
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/0")
    celery_result_backend: str = Field(default="redis://localhost:6379/0")
    api_key: str = Field(default="")
    webhook_url: str = Field(default="")
    shodan_api_key: str = Field(default="")

    # Email notifications (optional - sent on Critical findings alongside webhook)
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    smtp_to: str = Field(default="")   # comma-separated recipient addresses

    # Slack notifications (optional)
    slack_webhook_url: str = Field(default="")

    # S3/R2 evidence storage (optional - falls back to local disk when not set)
    s3_bucket: str = Field(default="")
    s3_endpoint_url: str = Field(default="")        # Cloudflare R2: https://<account>.r2.cloudflarestorage.com
    s3_access_key_id: str = Field(default="")
    s3_secret_access_key: str = Field(default="")
    s3_public_url: str = Field(default="")          # public base URL for direct object access (optional)
    s3_presign_expiry: int = Field(default=3600)    # presigned URL TTL in seconds

    # Data retention
    evidence_retention_days: int = Field(default=90)   # delete evidence older than N days
    scan_retention_days: int = Field(default=365)       # delete scan records older than N days

    # Subdomain enumeration
    subdomain_max: int = Field(default=30)              # max subdomains to enumerate per root domain
    subdomain_dispatch_scans: bool = Field(default=False)  # dispatch child scans for found subdomains

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
