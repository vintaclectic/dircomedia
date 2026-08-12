"""
Shared connection-health probes — Phase 3 (council decree 2026-07-04).

Used by BOTH the /api/v1/distribution/health endpoint (the frontend rail) and
the guardian beat task (alerts through Telegram/Discord). One truth, two eyes.
Per platform: {configured, live} — live=None means no cheap probe exists.
"""
import asyncio
import time

import httpx

from app.config import settings as cfg


# ── credential-vault probes (YH9AE4D, 2026-08-12) ────────────────────────────
# The OAuth wizard stores tokens in `platform_credentials` (encrypted). Those
# take PRECEDENCE over .env for any platform Vinta has connected through the
# wizard: a wizard connection that the health rail couldn't see would report
# "not configured" for an account that posts fine — the exact silent-rot failure
# the Cable Guy Law exists to prevent.

async def vault_health() -> dict[str, dict]:
    """Probe every wizard-connected platform. Returns {} if the vault is empty
    or unreadable — .env probes then carry the whole rail, as before."""
    try:
        from app.database import AsyncSessionLocal
        from app.services.oauth import store
        from app.services.oauth.providers import get_provider, PROVIDERS
        from app.services.oauth import flow as oauth_flow
    except Exception:
        return {}

    out: dict[str, dict] = {}
    try:
        async with AsyncSessionLocal() as db:
            rows = await store.list_credentials(db)
            now = int(time.time())
            for row in rows:
                if row.platform not in PROVIDERS:
                    continue
                p = get_provider(row.platform)
                entry: dict = {
                    "configured": True,
                    "source": "oauth_wizard",
                    "account": row.account_name,
                    "expires_at": row.expires_at,
                    "expires_in_days": (
                        round((row.expires_at - now) / 86400, 2)
                        if row.expires_at else None
                    ),
                    "needs_reconnect": bool(row.needs_reconnect),
                }
                if row.needs_reconnect:
                    entry.update({"live": False, "error": (row.last_error or "reconnect required")[:200]})
                    out[row.platform] = entry
                    continue
                if row.expires_at is not None and row.expires_at <= now:
                    entry.update({"live": False, "error": "access token expired"})
                    out[row.platform] = entry
                    continue

                token = await store.get_access_token(db, row.platform)
                if not token:
                    entry.update({"live": False, "error": "stored credential could not be decrypted"})
                    out[row.platform] = entry
                    continue
                ok, err = await oauth_flow.probe_token(p, token)
                entry["live"] = ok
                if not ok:
                    entry["error"] = (err or "probe failed")[:200]
                out[row.platform] = entry
    except Exception as e:
        return {"_vault_error": {"configured": None, "live": None, "error": str(e)[:200]}}
    return out


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
        params = {"user.fields": "public_metrics"}
        headers = tw._oauth_headers("GET", url, params=params)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, headers=headers, params=params)
            if r.status_code != 200:
                return {
                    "configured": True, "live": False,
                    "error": f"HTTP {r.status_code}: {r.text[:160]}",
                }
            # Report WHICH account posts and how far it reaches — a live rail
            # with an unknown handle is still an unusable rail.
            me = r.json().get("data", {})
            return {
                "configured": True, "live": True,
                "account": me.get("username"),
                "followers": me.get("public_metrics", {}).get("followers_count"),
            }
    except Exception as e:
        return {"configured": True, "live": False, "error": str(e)[:200]}


async def reddit_health() -> dict:
    # A refresh token alone is a complete config (the preferred, passwordless
    # lane) — requiring a password here marked working setups "unconfigured".
    has_app = bool(cfg.reddit_client_id and cfg.reddit_client_secret)
    has_grant = bool(cfg.reddit_refresh_token or (cfg.reddit_username and cfg.reddit_password))
    if not (has_app and has_grant):
        return {"configured": False, "live": None}
    try:
        from app.services.distribution.platforms.reddit import RedditClient
        # Probe through the real client so the health surface and the poster
        # can never disagree about whether Reddit works.
        await RedditClient()._get_access_token()
        return {"configured": True, "live": True}
    except Exception as e:
        return {"configured": True, "live": False, "error": str(e)[:400]}


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
    merged = {
        name: (r if isinstance(r, dict) else {"configured": None, "live": False, "error": str(r)})
        for name, r in zip(names, results)
    }

    # Vault wins where it has an opinion. A platform Vinta connected through the
    # wizard is described by its stored credential, not by whatever stale key
    # happens to sit in .env.
    vault = await vault_health()
    vault.pop("_vault_error", None)
    for platform, entry in vault.items():
        merged[platform] = entry

    # Pinterest exists only in the vault (no .env-era client), so it would be
    # invisible on the rail until connected. Show it as a real, unconnected
    # platform instead of omitting it — an absent row reads as "not supported".
    merged.setdefault("pinterest", {"configured": False, "live": None, "source": "oauth_wizard"})
    return merged
