"""
Token refresh — the machine keeping its own connections alive (YH9AE4D).

Shared by the manual "Refresh Now" button and the 6-hourly guardian task, so the
button and the schedule can never drift apart in behavior.

THE DOCTRINE (Cable Guy Law): a connection never rots silently. Either we refresh
it ourselves, or we set needs_reconnect and the dashboard turns red with the real
reason. What must never happen is a token quietly expiring and a post failing at
2am with nobody told.
"""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.oauth import flow as oauth_flow
from app.services.oauth import store
from app.services.oauth.providers import get_provider, PROVIDERS, credentials_for

REFRESH_WINDOW_DAYS = 3          # refresh anything expiring within 3 days
REFRESH_WINDOW = REFRESH_WINDOW_DAYS * 86400


async def refresh_one(db: AsyncSession, platform: str) -> dict:
    """Refresh a single platform. Never raises — returns {ok, ...}."""
    if platform not in PROVIDERS:
        return {"ok": False, "platform": platform, "error": f"Unknown platform '{platform}'."}
    p = get_provider(platform)

    row = await store.get_credential(db, platform)
    if not row:
        return {"ok": False, "platform": platform, "error": "Not connected."}

    cid, csec = credentials_for(platform)
    if not (cid and csec):
        msg = f"{p.label} developer app credentials are missing; cannot refresh."
        await store.mark_needs_reconnect(db, platform, msg)
        return {"ok": False, "platform": platform, "error": msg}

    # Instagram's "refresh material" IS the current access token (fb_exchange).
    if platform == "instagram":
        material = await store.get_access_token(db, platform)
    else:
        material = await store.get_refresh_token(db, platform)

    if not material:
        msg = (
            f"{p.label} has no refresh token — this connection cannot renew itself. "
            "Reconnect to mint a new one."
        )
        await store.mark_needs_reconnect(db, platform, msg)
        return {"ok": False, "platform": platform, "error": msg}

    try:
        payload = await oauth_flow.refresh_token(p, refresh=material)
    except Exception as e:
        msg = str(e)[:400]
        await store.mark_needs_reconnect(db, platform, msg)
        return {"ok": False, "platform": platform, "error": msg}

    access = payload["access_token"]
    expires_at = oauth_flow.expires_at_from(payload)
    if platform == "instagram" and expires_at is None:
        expires_at = int(time.time() + 60 * 86400)

    new_refresh = payload.get("refresh_token")
    if platform == "instagram":
        new_refresh = access  # the fresh token is its own next refresh material

    await store.upsert_credential(
        db,
        platform=platform,
        access_token=access,
        refresh_token=new_refresh,
        expires_at=expires_at,
        account_id=row.account_id or "",
        account_name=row.account_name,
        scopes=payload.get("scope") or row.scopes,
    )
    return {
        "ok": True, "platform": platform, "expires_at": expires_at,
        "expires_in_days": round((expires_at - time.time()) / 86400, 2) if expires_at else None,
    }


async def refresh_expiring(db: AsyncSession, window: int = REFRESH_WINDOW) -> dict:
    """Refresh every credential inside the expiry window. Returns a report."""
    now = int(time.time())
    rows = await store.list_credentials(db)
    refreshed, failed, skipped = [], [], []

    for row in rows:
        if row.platform not in PROVIDERS:
            continue
        # Non-expiring credentials have nothing to renew.
        if row.expires_at is None:
            skipped.append(row.platform)
            continue
        if row.expires_at - now > window:
            skipped.append(row.platform)
            continue
        result = await refresh_one(db, row.platform)
        (refreshed if result.get("ok") else failed).append(
            {"platform": row.platform, **{k: v for k, v in result.items() if k != "platform"}}
        )

    return {"refreshed": refreshed, "failed": failed, "skipped": skipped, "checked_at": now}


async def needs_reconnect_platforms(db: AsyncSession) -> list[str]:
    return [r.platform for r in await store.list_credentials(db) if r.needs_reconnect]
