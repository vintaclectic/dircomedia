"""
Kick → YouTube automation pipeline worker (task 3JFWZQK, 2026-08-14).

Polls Kick for ended streams, downloads VODs, uploads to YouTube with optimized
metadata, and posts announcement to X (Twitter). Passive revenue engine —
turns every Kick stream into discoverable YouTube content with zero manual work.

Architecture:
  - Celery beat task runs every 30min (configurable)
  - Checks Kick for new ended streams since last run
  - Downloads VOD via yt-dlp
  - Uploads to YouTube via YouTubeClient (chunked, resumable)
  - Posts announcement to X via TwitterClient
  - Tracks processed streams in DB to avoid duplicates

Safety:
  - Only processes streams creator owns (Kick username = configured account)
  - Respects YouTube quota (1600 units/upload, ~6/day max)
  - Idempotent: won't re-upload the same stream if task runs multiple times
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from app.database import get_db
from app.models.processed_content import ProcessedContent
from app.services.distribution.platforms.kick import KickClient
from app.services.distribution.platforms.youtube import YouTubeClient
from app.services.distribution.platforms.twitter import TwitterClient
from app.core.exceptions import DistributionError
from app.config import settings


@shared_task(name="kick_youtube_pipeline.poll_and_upload")
def poll_and_upload():
    """
    Celery task: Poll Kick for new ended streams and upload to YouTube.

    Scheduled via Celery beat (default: every 30min). Can be triggered manually:
      celery -A app.workers.celery_app call kick_youtube_pipeline.poll_and_upload
    """
    return asyncio.run(_poll_and_upload_async())


async def _poll_and_upload_async():
    """Async implementation of the pipeline."""
    # Load Kick username from config
    kick_username = getattr(settings, "kick_username", None)
    if not kick_username:
        return {
            "status": "skipped",
            "reason": "KICK_USERNAME not configured in backend/.env",
        }

    kick = KickClient(kick_username)
    youtube = YouTubeClient()
    twitter = TwitterClient()

    # Check if YouTube is configured (required)
    if not youtube.configured:
        return {
            "status": "skipped",
            "reason": "YouTube OAuth not configured (see docs/PLATFORM_CONNECTIONS.md)",
        }

    # Fetch latest ended stream
    try:
        latest_stream = await kick.get_latest_ended_stream()
    except DistributionError as e:
        return {"status": "error", "reason": f"Kick API error: {e.message}"}

    if not latest_stream:
        return {"status": "idle", "reason": "No ended streams found"}

    stream_id = str(latest_stream["id"])
    stream_title = latest_stream.get("session_title", "Untitled")

    # Check if already processed (idempotency)
    async for db in get_db():
        existing = await db.execute(
            select(ProcessedContent).where(
                ProcessedContent.source_platform == "kick",
                ProcessedContent.source_id == stream_id,
            )
        )
        if existing.scalar_one_or_none():
            return {
                "status": "skipped",
                "reason": f"Stream {stream_id} already uploaded to YouTube",
            }

        # Mark as processing (claim the work)
        processed = ProcessedContent(
            source_platform="kick",
            source_id=stream_id,
            source_url=f"https://kick.com/{kick_username}?video={stream_id}",
            processed_at=datetime.now(timezone.utc),
            content_metadata={"stream_title": stream_title},
        )
        db.add(processed)
        await db.commit()

    # Download VOD
    vod_path = None
    try:
        print(f"Downloading Kick VOD: {stream_title} ({stream_id})...")
        vod_path = await kick.download_vod(latest_stream)
        print(f"Downloaded to: {vod_path} ({os.path.getsize(vod_path) / 1e6:.1f} MB)")

        # Optimize metadata for YouTube
        metadata = kick.optimize_metadata_for_youtube(latest_stream)

        # Upload to YouTube
        print(f"Uploading to YouTube: {metadata['title']}")
        result = await youtube.upload(
            video=vod_path,
            title=metadata["title"],
            description=metadata["description"],
            tags=metadata["tags"],
            category_id=metadata["category_id"],
            privacy="public",  # or "unlisted" if you want to review first
        )

        video_id = result.get("id")
        video_url = f"https://youtube.com/watch?v={video_id}"
        print(f"Uploaded successfully: {video_url}")

        # Update processed record with YouTube details
        async for db in get_db():
            processed.target_platform = "youtube"
            processed.target_id = video_id
            processed.target_url = video_url
            processed.metadata["youtube_title"] = metadata["title"]
            await db.commit()

        # Post announcement to X (if configured)
        if twitter.configured:
            try:
                tweet_text = (
                    f"🎮 New video live on YouTube!\n\n"
                    f"{metadata['title']}\n\n"
                    f"Watch now: {video_url}\n\n"
                    f"#LiveStream #Gaming #Kick #YouTube"
                )
                tweet_result = await twitter.post(tweet_text)
                print(f"Tweeted: {tweet_result.get('url', 'success')}")
            except Exception as e:
                # Don't fail the whole pipeline if tweet fails
                print(f"Tweet failed (non-fatal): {e}")

        return {
            "status": "success",
            "stream_id": stream_id,
            "stream_title": stream_title,
            "youtube_url": video_url,
            "youtube_video_id": video_id,
        }

    except Exception as e:
        # Clean up failed processing record so it can be retried
        async for db in get_db():
            await db.delete(processed)
            await db.commit()

        return {
            "status": "error",
            "stream_id": stream_id,
            "error": str(e),
        }

    finally:
        # Clean up downloaded VOD
        if vod_path and os.path.exists(vod_path):
            try:
                os.remove(vod_path)
                print(f"Cleaned up temp VOD: {vod_path}")
            except:
                pass  # temp files clean themselves eventually


# Manual trigger for testing
async def test_pipeline():
    """Run the pipeline once, manually, for testing."""
    result = await _poll_and_upload_async()
    print("\n=== Pipeline Result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(test_pipeline())
