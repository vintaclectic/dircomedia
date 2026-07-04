"""
THE PERSISTENCE ENGINE — Phase 3 (council decree 2026-07-04, ARIA's design).

Cable Guy Law: the system never stops following up. Zeppelin Law: campaigns
build, they don't one-off. Dead Law: show up every week, forever, generously.

Each brand config may declare `rituals` — recurring content formats:

    rituals:
      - name: weekly_roundup          # unique per project
        weekday: 0                    # 0=Mon ... 6=Sun (UTC)
        topic: "This week in DirCo: ..."
        platforms: [twitter, discord]

Every day this task finds today's rituals, generates the post in brand voice,
and drops it into the Broadcast queue as APPROVE-FIRST from source
'persistence-engine'. The machine drafts the ritual; Vinta still speaks the
word. Idempotent per (project, ritual, date) — reruns never duplicate.
"""
import asyncio
from datetime import datetime, timezone

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.persistence_tasks.run_persistence_engine")
def run_persistence_engine():
    async def _run():
        from pathlib import Path

        import yaml
        from sqlalchemy import select

        from app.config import settings
        from app.database import AsyncSessionLocal
        from app.models.broadcast import Broadcast, BroadcastStatus
        from app.services.content_engine.generator import ContentGenerator

        now = datetime.now(timezone.utc)
        weekday = now.weekday()  # 0=Mon
        date_str = now.date().isoformat()
        generator = ContentGenerator()

        created, skipped, errors = [], [], []

        config_dir = Path(settings.brand_configs_dir)
        for config_file in sorted(config_dir.glob("*.yaml")):
            slug = config_file.stem
            try:
                data = yaml.safe_load(config_file.read_text()) or {}
            except Exception as e:
                errors.append(f"{slug}: yaml {e}")
                continue

            for ritual in data.get("rituals", []) or []:
                try:
                    if int(ritual.get("weekday", -1)) != weekday:
                        continue
                    name = str(ritual.get("name", "ritual"))
                    idem = f"ritual:{slug}:{name}:{date_str}"

                    async with AsyncSessionLocal() as db:
                        existing = await db.execute(
                            select(Broadcast).where(Broadcast.idempotency_key == idem)
                        )
                        if existing.scalar_one_or_none():
                            skipped.append(idem)
                            continue

                        platforms = ritual.get("platforms") or ["twitter"]
                        gen = await generator.generate_text(
                            project_slug=slug,
                            topic=str(ritual.get("topic", name)),
                            platforms=platforms,
                        )
                        body = (gen.get("body") or "").strip()
                        tags = " ".join(gen.get("hashtags", [])[:5])
                        if tags:
                            body = f"{body}\n\n{tags}"

                        db.add(Broadcast(
                            idempotency_key=idem,
                            project_slug=slug,
                            kind="content",
                            source="persistence-engine",
                            title=gen.get("title") or None,
                            body=body or None,
                            content_type="text",
                            platforms=platforms,
                            mode="approve-first",
                            status=BroadcastStatus.pending_approval,
                        ))
                        await db.commit()
                        created.append(idem)
                except Exception as e:
                    errors.append(f"{slug}/{ritual.get('name')}: {e}")

        return {"created": created, "skipped": skipped, "errors": errors}

    return asyncio.get_event_loop().run_until_complete(_run())
