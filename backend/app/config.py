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

    # Phase 2 platforms (council decree 2026-07-04)
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""

    discord_webhook_url: str = ""
    discord_webhook_overrides: dict = {}   # {"project_slug": "webhook_url"}

    telegram_bot_token: str = ""
    telegram_channel_id: str = ""          # @channelname or -100... chat id

    # Phase 3 platforms + guardians (council decree 2026-07-04)
    bluesky_handle: str = ""               # e.g. dirco.bsky.social
    bluesky_app_password: str = ""         # bsky.app → Settings → App Passwords
    owner_alert_telegram_chat_id: str = "" # personal chat for guardian alerts (falls back to channel)

    # Storage
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "dircomedia"
    r2_public_url: str = ""

    # App
    brand_configs_dir: str = "/app/brand_configs"
    media_upload_dir: str = "/tmp/dircomedia/uploads"

    # Security (Phase 0 — council decree 2026-07-04)
    owner_api_token: str = ""          # required; API fails closed if blank
    cors_origins: str = "http://localhost:3000,http://172.25.39.140:3000"

    # Broadcast Spine (Phase 1)
    broadcast_kill_switch: bool = False        # True = nothing posts, period
    broadcast_daily_cap: int = 10              # max broadcasts fanned out per platform per day
    broadcast_dedupe_hours: int = 24           # identical content blocked within this window
    brain_webhook_url: str = ""                # optional: brain endpoint for status callbacks
    brain_webhook_token: str = ""              # token sent to the brain webhook

    # Model tiering (frugal-max ruling: Opus never for post text)
    content_text_model: str = "claude-sonnet-4-5"
    video_script_model: str = "claude-sonnet-4-5"

    class Config:
        env_file = ".env"
        extra = "ignore"  # allow non-Settings env keys (e.g. OPENROUTER_API_KEY,
                          # HERMES_MODEL) read directly via os.environ elsewhere


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
