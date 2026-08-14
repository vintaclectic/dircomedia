"""
Broadcast fan-out worker — council decree 2026-07-04, Phase 1.

Takes an approved Broadcast row, posts to every platform on it via the
DistributionScheduler (per-project brand slug preserved), records per-platform
results, and — if configured — reports status back to the brain
(BRAIN_WEBHOOK_URL) so Vintinuum knows what landed.
"""
import asyncio

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, name="app.workers.broadcast_tasks.broadcast_fanout", max_retries=2)
def broadcast_fanout_task(self, broadcast_id: str):
    async def _run():
        import uuid
        from sqlalchemy import select

        from app.config import settings
        from app.database import AsyncSessionLocal
        from app.models.broadcast import Broadcast, BroadcastStatus
        from app.services.distribution.scheduler import DistributionScheduler

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Broadcast).where(Broadcast.id == uuid.UUID(broadcast_id))
            )
            broadcast = result.scalar_one_or_none()
            if not broadcast:
                return {"error": "Broadcast not found"}

            # Hard gate even at the worker: the kill switch stops in-flight work.
            if settings.broadcast_kill_switch:
                broadcast.status = BroadcastStatus.failed
                broadcast.error = "Kill switch engaged at fan-out time."
                await db.commit()
                return {"error": "kill_switch"}

            broadcast.status = BroadcastStatus.posting
            await db.commit()

            text = "\n\n".join(p for p in [broadcast.title, broadcast.body] if p).strip()

            # ── REDDIT ACCOUNT-SAFETY GUARD (Vinta 2026-07-18, "approval-only") ──
            # Reddit bans accounts that auto-blast promos to subs they don't own.
            # Only let Reddit fan out when the target sub is on the owned allowlist
            # (REDDIT_AUTO_SUBREDDITS). Empty allowlist = Reddit is held out of the
            # auto path entirely; it posts only via an explicit owner approval flow.
            platforms = list(broadcast.platforms or [])
            reddit_skipped = False
            if "reddit" in platforms:
                allow = [s.strip().lower() for s in (settings.reddit_auto_subreddits or "").split(",") if s.strip()]
                target = (getattr(broadcast, "reddit_subreddit", None) or "").strip().lower()
                if not allow or (target and target not in allow):
                    platforms = [p for p in platforms if p != "reddit"]
                    reddit_skipped = True

            scheduler = DistributionScheduler()
            results = await scheduler.post(
                platforms=platforms,
                body=text,
                media_url=broadcast.media_url,
                content_type=broadcast.content_type,
                project_slug=broadcast.project_slug,
                # YouTube needs the title UNFLATTENED — `text` merges title and
                # body for feed platforms, but the SEO engine wants the topic
                # on its own to optimise the search phrase against.
                title=broadcast.title,
            )
            if reddit_skipped:
                results["reddit"] = {
                    "error": "held: approval-only (no owned subreddit allowlisted). "
                    "Set REDDIT_AUTO_SUBREDDITS to an owned sub to enable auto-post."
                }

            succeeded = [p for p, r in results.items() if "error" not in r]
            failed = [p for p, r in results.items() if "error" in r]

            broadcast.results = results
            if succeeded and not failed:
                broadcast.status = BroadcastStatus.posted
            elif succeeded:
                broadcast.status = BroadcastStatus.partial
            else:
                broadcast.status = BroadcastStatus.failed
                broadcast.error = "; ".join(f"{p}: {results[p].get('error')}" for p in failed)[:2000]
            await db.commit()

            # Status callback to the brain (best-effort, never blocks the result).
            if settings.brain_webhook_url:
                try:
                    import httpx
                    headers = {}
                    if settings.brain_webhook_token:
                        headers["Authorization"] = f"Bearer {settings.brain_webhook_token}"
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(
                            settings.brain_webhook_url,
                            json={
                                "event": "broadcast.status",
                                "broadcast_id": str(broadcast.id),
                                "project": broadcast.project_slug,
                                "status": broadcast.status.value,
                                "results": results,
                            },
                            headers=headers,
                        )
                except Exception:
                    pass  # webhook failure must never fail the broadcast

            return {"status": broadcast.status.value, "results": results}

    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)
