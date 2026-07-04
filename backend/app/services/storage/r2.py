"""
R2 storage — Phase 2 (council decree 2026-07-04).

Uploads media to Cloudflare R2 and returns a public URL. This unblocks
Instagram/TikTok/YouTube posting, which all require publicly reachable media —
the old code emitted file:// placeholders that no platform could fetch.
"""
import asyncio
import mimetypes
import uuid
from pathlib import Path

import boto3

from app.config import settings
from app.core.exceptions import DistributionError


def _client():
    if not (settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise DistributionError("R2 storage is not configured", "r2")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def r2_configured() -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_public_url
    )


async def upload_file(file_path: str, key_prefix: str = "media") -> str:
    """Upload a local file to R2, return its public URL. Runs boto3 in a thread."""
    path = Path(file_path)
    if not path.exists():
        raise DistributionError(f"File not found: {file_path}", "r2")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    key = f"{key_prefix}/{uuid.uuid4().hex[:12]}-{path.name}"

    def _upload():
        _client().upload_file(
            str(path),
            settings.r2_bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    await asyncio.get_event_loop().run_in_executor(None, _upload)
    return f"{settings.r2_public_url.rstrip('/')}/{key}"


async def health() -> dict:
    """head_bucket — cheap liveness probe."""
    if not r2_configured():
        return {"configured": False, "live": None}
    try:
        def _head():
            _client().head_bucket(Bucket=settings.r2_bucket_name)
        await asyncio.get_event_loop().run_in_executor(None, _head)
        return {"configured": True, "live": True}
    except Exception:
        return {"configured": True, "live": False}
