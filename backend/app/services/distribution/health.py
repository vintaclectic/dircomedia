"""
Shared connection-health probes — Phase 3 (council decree 2026-07-04).

Used by BOTH the /api/v1/distribution/health endpoint (the frontend rail) and
the guardian beat task (alerts through Telegram/Discord). One truth, two eyes.
Per platform: {configured, live} — live=None means no cheap probe exists.
"""
import asyncio

import httpx

from app.config import settings as cfg


async def twitter_health() -> dict:
    configured = all([
        cfg.twitter_api_key, cfg.twitter_api_secret,
        cfg.twitter_access_token, cfg.twitter_access_secret,
    ])
    if not configured:
        return {"configured": False, "live": None}
    try:
        from app.services.distribution.platforms.twitter import TwitterClient
        tw = TwitterClient()
        url = "https://api.twitter.com/2/users/me"
        headers = tw._oauth_headers("GET", url)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers)
            return {"configured": True, "live": r.status_code == 200}
    except Exception:
        return {"configured": True, "live": False}


async def reddit_health() -> dict:
    configured = all([
        cfg.reddit_client_id, cfg.reddit_client_secret,
        cfg.reddit_username, cfg.reddit_password,
    ])
    if not configured:
        return {"configured": False, "live": None}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(cfg.reddit_client_id, cfg.reddit_client_secret),
                data={
                    "grant_type": "password",
                    "username": cfg.reddit_username,
                    "password": cfg.reddit_password,
                },
                headers={"User-Agent": "dircomedia-health/1.0"},
            )
            return {"configured": True, "live": r.status_code == 200 and "access_token" in r.json()}
    except Exception:
        return {"configured": True, "live": False}


async def instagram_health() -> dict:
    if not cfg.instagram_access_token:
        return {"configured": False, "live": None}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://graph.facebook.com/v21.0/me",
                params={"access_token": cfg.instagram_access_token},
            )
            return {"configured": True, "live": r.status_code == 200}
    except Exception:
        return {"configured": True, "live": False}


async def tiktok_health() -> dict:
    configured = bool(cfg.tiktok_client_key and cfg.tiktok_access_token)
    return {"configured": configured, "live": None}  # no cheap probe


async def check_all() -> dict[str, dict]:
    """Probe every platform + storage in parallel. Never raises."""
    from app.services.distribution.platforms.discord import DiscordClient
    from app.services.distribution.platforms.telegram import TelegramClient
    from app.services.distribution.platforms.youtube import YouTubeClient
    from app.services.distribution.platforms.bluesky import BlueskyClient
    from app.services.storage import r2 as r2_storage

    names = [
        "twitter", "reddit", "instagram", "tiktok",
        "discord", "telegram", "youtube", "bluesky", "r2_storage",
    ]
    results = await asyncio.gather(
        twitter_health(),
        reddit_health(),
        instagram_health(),
        tiktok_health(),
        DiscordClient().health(),
        TelegramClient().health(),
        YouTubeClient().health(),
        BlueskyClient().health(),
        r2_storage.health(),
        return_exceptions=True,
    )
    return {
        name: (r if isinstance(r, dict) else {"configured": None, "live": False, "error": str(r)})
        for name, r in zip(names, results)
    }
