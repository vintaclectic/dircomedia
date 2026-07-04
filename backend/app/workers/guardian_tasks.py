"""
GUARDIAN tasks — Phase 3 (council decree 2026-07-04).

Two duties, both in service of the Cable Guy Law (an account never rots silently):

1. platform_health_check (every 6h): probe every connection; on a transition to
   DOWN (or a DOWN older than 24h without a reminder) — tell Vinta directly on
   Telegram (falls back to Discord). The machine reports its own wounds.

2. refresh_instagram_token (weekly): Instagram long-lived tokens die at 60 days
   but a still-valid token can be re-exchanged for a fresh 60-day one. Doing it
   weekly means the token in .env is never older than 7 days. Running worker
   processes keep their (still valid) in-memory token; any restart picks up the
   fresh one. The expiry problem ceases to exist.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app

ALERT_REMINDER_HOURS = 24


async def _alert_owner(text: str) -> bool:
    """Tell Vinta directly. Telegram first (personal chat if set), Discord fallback."""
    from app.config import settings
    import httpx

    sent = False
    chat = settings.owner_alert_telegram_chat_id or settings.telegram_channel_id
    if settings.telegram_bot_token and chat:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": chat, "text": text[:4096]},
                )
                sent = r.status_code == 200
        except Exception:
            pass
    if not sent and settings.discord_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{settings.discord_webhook_url}?wait=true",
                    json={"content": text[:2000], "username": "DirCoMedia Guardian"},
                )
                sent = r.status_code in (200, 204)
        except Exception:
            pass
    return sent


@celery_app.task(name="app.workers.guardian_tasks.platform_health_check")
def platform_health_check():
    async def _run():
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models.health import PlatformHealthRecord
        from app.services.distribution.health import check_all

        results = await check_all()
        now = datetime.now(timezone.utc)
        newly_down: list[str] = []
        reminders: list[str] = []

        async with AsyncSessionLocal() as db:
            for platform, h in results.items():
                rec_result = await db.execute(
                    select(PlatformHealthRecord).where(PlatformHealthRecord.platform == platform)
                )
                rec = rec_result.scalar_one_or_none()
                prev_live = rec.live if rec else None
                if not rec:
                    rec = PlatformHealthRecord(platform=platform)
                    db.add(rec)

                rec.configured = bool(h.get("configured"))
                rec.live = h.get("live")
                rec.checked_at = now

                is_down = h.get("configured") and h.get("live") is False
                if is_down:
                    transitioned = prev_live is not False  # was live/unknown, now down
                    last = rec.last_alert_at
                    if last is not None and last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    stale_alert = last is None or (now - last) > timedelta(hours=ALERT_REMINDER_HOURS)
                    if transitioned:
                        newly_down.append(platform)
                        rec.last_alert_at = now
                    elif stale_alert:
                        reminders.append(platform)
                        rec.last_alert_at = now
            await db.commit()

        if newly_down or reminders:
            lines = ["⚠️ DirCoMedia Guardian"]
            if newly_down:
                lines.append("CONNECTION DOWN: " + ", ".join(newly_down))
            if reminders:
                lines.append("still down (24h+): " + ", ".join(reminders))
            lines.append("Fixes: docs/OWNERS_MANUAL.md Part 4 · rail: /approvals")
            await _alert_owner("\n".join(lines))

        return {p: h for p, h in results.items()}

    return asyncio.get_event_loop().run_until_complete(_run())


@celery_app.task(name="app.workers.guardian_tasks.refresh_instagram_token")
def refresh_instagram_token():
    async def _run():
        import httpx
        from app.config import settings

        if not (settings.instagram_app_id and settings.instagram_app_secret and settings.instagram_access_token):
            return {"skipped": "instagram not configured"}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(
                    "https://graph.facebook.com/v21.0/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": settings.instagram_app_id,
                        "client_secret": settings.instagram_app_secret,
                        "fb_exchange_token": settings.instagram_access_token,
                    },
                )
                if r.status_code != 200:
                    await _alert_owner(
                        "⚠️ DirCoMedia Guardian\nInstagram token auto-refresh FAILED "
                        f"(HTTP {r.status_code}). Manual re-exchange needed — "
                        "docs/OWNERS_MANUAL.md Part 4."
                    )
                    return {"error": f"http_{r.status_code}"}
                new_token = r.json().get("access_token")
                if not new_token:
                    return {"error": "no token in response"}

            # Persist to .env (source of truth across restarts) + this process.
            from app.api.v1.settings import _write_env
            _write_env({"INSTAGRAM_ACCESS_TOKEN": new_token})
            settings.instagram_access_token = new_token
            return {"refreshed": True}
        except Exception as e:
            return {"error": str(e)}

    return asyncio.get_event_loop().run_until_complete(_run())
