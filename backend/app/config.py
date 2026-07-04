from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://dirco:dirco@localhost:5432/dircomedia"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # AI / Content
    anthropic_api_key: str = ""
    replicate_api_token: str = ""
    openai_api_key: str = ""

    # Video Pipeline
    creatomate_api_key: str = ""
    runway_api_key: str = ""
    kling_api_key: str = ""
    heygen_api_key: str = ""

    # Social Platforms
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""
    twitter_bearer_token: str = ""

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_access_token: str = ""

    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_access_token: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""

    # Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "dircomedia"
    r2_public_url: str = ""

    # App
    brand_configs_dir: str = "/app/brand_configs"
    media_upload_dir: str = "/tmp/dircomedia/uploads"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
