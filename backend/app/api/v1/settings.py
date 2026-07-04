from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import re

router = APIRouter()

ENV_PATH = Path(__file__).parents[3] / ".env"

# Keys we expose to the frontend — never expose Anthropic or DB keys
ALLOWED_KEYS = {
    "TWITTER_API_KEY",
    "TWITTER_API_SECRET",
    "TWITTER_ACCESS_TOKEN",
    "TWITTER_ACCESS_SECRET",
    "TWITTER_BEARER_TOKEN",
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_ACCESS_TOKEN",
    "INSTAGRAM_APP_ID",
    "INSTAGRAM_APP_SECRET",
    "INSTAGRAM_ACCESS_TOKEN",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USERNAME",
    "REDDIT_PASSWORD",
    "CREATOMATE_API_KEY",
    "RUNWAY_API_KEY",
    "HEYGEN_API_KEY",
}


def _read_env() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    result = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip()
    return result


def _write_env(updates: dict[str, str]) -> None:
    text = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    lines = text.splitlines()
    for key, val in updates.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
        new_line = f"{key}={val}"
        if pattern.search(text):
            # replace existing
            lines = [pattern.sub(new_line, line) if pattern.match(line) else line for line in lines]
        else:
            lines.append(new_line)
    ENV_PATH.write_text("\n".join(lines) + "\n")


class SettingsOut(BaseModel):
    twitter_api_key: str
    twitter_api_secret: str
    twitter_access_token: str
    twitter_access_secret: str
    twitter_bearer_token: str
    tiktok_client_key: str
    tiktok_client_secret: str
    tiktok_access_token: str
    instagram_app_id: str
    instagram_app_secret: str
    instagram_access_token: str
    reddit_client_id: str
    reddit_client_secret: str
    reddit_username: str
    reddit_password: str
    creatomate_api_key: str
    runway_api_key: str
    heygen_api_key: str


class SettingsIn(BaseModel):
    twitter_api_key: str | None = None
    twitter_api_secret: str | None = None
    twitter_access_token: str | None = None
    twitter_access_secret: str | None = None
    twitter_bearer_token: str | None = None
    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_access_token: str | None = None
    instagram_app_id: str | None = None
    instagram_app_secret: str | None = None
    instagram_access_token: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_username: str | None = None
    reddit_password: str | None = None
    creatomate_api_key: str | None = None
    runway_api_key: str | None = None
    heygen_api_key: str | None = None


def _mask(val: str) -> str:
    """Show last 4 chars, mask the rest."""
    if not val or val in ("...", "r8_...", "sk-..."):
        return ""
    if len(val) <= 4:
        return val
    return "•" * (len(val) - 4) + val[-4:]


@router.get("/", response_model=dict)
async def get_settings():
    env = _read_env()
    return {
        "twitter_api_key":        _mask(env.get("TWITTER_API_KEY", "")),
        "twitter_api_secret":     _mask(env.get("TWITTER_API_SECRET", "")),
        "twitter_access_token":   _mask(env.get("TWITTER_ACCESS_TOKEN", "")),
        "twitter_access_secret":  _mask(env.get("TWITTER_ACCESS_SECRET", "")),
        "twitter_bearer_token":   _mask(env.get("TWITTER_BEARER_TOKEN", "")),
        "tiktok_client_key":      _mask(env.get("TIKTOK_CLIENT_KEY", "")),
        "tiktok_client_secret":   _mask(env.get("TIKTOK_CLIENT_SECRET", "")),
        "tiktok_access_token":    _mask(env.get("TIKTOK_ACCESS_TOKEN", "")),
        "instagram_app_id":       _mask(env.get("INSTAGRAM_APP_ID", "")),
        "instagram_app_secret":   _mask(env.get("INSTAGRAM_APP_SECRET", "")),
        "instagram_access_token": _mask(env.get("INSTAGRAM_ACCESS_TOKEN", "")),
        "reddit_client_id":       _mask(env.get("REDDIT_CLIENT_ID", "")),
        "reddit_client_secret":   _mask(env.get("REDDIT_CLIENT_SECRET", "")),
        "reddit_username":        env.get("REDDIT_USERNAME", ""),
        "reddit_password":        _mask(env.get("REDDIT_PASSWORD", "")),
        "creatomate_api_key":     _mask(env.get("CREATOMATE_API_KEY", "")),
        "runway_api_key":         _mask(env.get("RUNWAY_API_KEY", "")),
        "heygen_api_key":         _mask(env.get("HEYGEN_API_KEY", "")),
    }


@router.patch("/")
async def update_settings(body: SettingsIn):
    mapping = {
        "twitter_api_key":        "TWITTER_API_KEY",
        "twitter_api_secret":     "TWITTER_API_SECRET",
        "twitter_access_token":   "TWITTER_ACCESS_TOKEN",
        "twitter_access_secret":  "TWITTER_ACCESS_SECRET",
        "twitter_bearer_token":   "TWITTER_BEARER_TOKEN",
        "tiktok_client_key":      "TIKTOK_CLIENT_KEY",
        "tiktok_client_secret":   "TIKTOK_CLIENT_SECRET",
        "tiktok_access_token":    "TIKTOK_ACCESS_TOKEN",
        "instagram_app_id":       "INSTAGRAM_APP_ID",
        "instagram_app_secret":   "INSTAGRAM_APP_SECRET",
        "instagram_access_token": "INSTAGRAM_ACCESS_TOKEN",
        "reddit_client_id":       "REDDIT_CLIENT_ID",
        "reddit_client_secret":   "REDDIT_CLIENT_SECRET",
        "reddit_username":        "REDDIT_USERNAME",
        "reddit_password":        "REDDIT_PASSWORD",
        "creatomate_api_key":     "CREATOMATE_API_KEY",
        "runway_api_key":         "RUNWAY_API_KEY",
        "heygen_api_key":         "HEYGEN_API_KEY",
    }
    updates = {}
    for field, env_key in mapping.items():
        val = getattr(body, field)
        if val is not None and val != "":
            # Don't overwrite with masked values
            if not all(c == "•" for c in val):
                updates[env_key] = val

    if updates:
        _write_env(updates)

    return {"saved": len(updates), "keys": list(updates.keys())}
