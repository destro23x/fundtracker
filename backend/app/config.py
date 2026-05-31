from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Any
import json


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fund_tracker"
    secret_key: str = "change-me-in-production"
    # Accepts: "http://localhost:3000"  OR  "url1,url2"  OR  '["url1","url2"]'
    backend_cors_origins: Any = ["http://localhost:3000"]

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    openai_api_key: str = ""

    # S3 / AWS
    aws_endpoint_url: str = "http://localstack:4566"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    aws_region: str = "eu-central-1"
    s3_bucket: str = "fund-tracker-data"
    s3_portfolio_prefix: str = "PortfolioComposition"
    s3_portfolio_loaded_prefix: str = "PortfolioCompositionLoaded"

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
