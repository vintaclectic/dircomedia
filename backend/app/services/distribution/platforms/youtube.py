"""
YouTube client — Phase 2 (council decree 2026-07-04), hardened for real
uploads under task TA3SQSM (2026-08-14).

YouTube Data API v3 via raw httpx (no google client lib — matches every other
platform client here, zero new deps):
  - OAuth refresh-token flow (offline access, owner-only)
  - Resumable video upload (videos.insert, uploadType=resumable)
  - CHUNKED transfer: a video is streamed to disk then pushed in slices, so a
    2GB upload costs ~8MB of RAM instead of 2GB. The previous implementation
    did `media.content` (whole file into memory) — that OOMs the worker on any
    real video and was the single biggest thing standing between this client
    and a genuine publish.
  - Resume-on-interrupt: a dropped connection asks YouTube how many bytes it
    actually received and continues from there, rather than restarting a
    multi-gigabyte upload from zero.
  - Local file paths AND remote URLs both accepted.
  - Thumbnails via thumbnails.set (the single highest-leverage CTR lever on
    the platform).

Quota reality: video upload costs 1,600 units of the 10,000/day default —
~6 uploads/day ceiling. Fine for owner cadence. Community posts have NO
public API (extension-assisted or manual). See docs/PLATFORM_CONNECTIONS.md §5.
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

import httpx

from app.config import settings
from app.core.exceptions import DistributionError

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMBNAIL_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"

# Google requires resumable chunks to be a multiple of 256KB. 8MB balances
# request overhead against how much work a dropped chunk costs us.
CHUNK_SIZE = 8 * 1024 * 1024
MAX_RESUME_ATTEMPTS = 5

VALID_PRIVACY = {"public", "unlisted", "private"}

# YouTube category IDs. 20=Gaming (DirCo's home turf), 28=Science & Technology,
# 27=Education, 24=Entertainment, 22=People & Blogs.
DEFAULT_CATEGORY = "20"


class YouTubeClient:
    def __init__(self):
        self.client_id = settings.youtube_client_id
        self.client_secret = settings.youtube_client_secret
        self.refresh_token = settings.youtube_refresh_token

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if not self.configured:
            raise DistributionError(
                "YouTube OAuth not configured — set YOUTUBE_CLIENT_ID, "
                "YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN in backend/.env "
                "(see docs/PLATFORM_CONNECTIONS.md §5)",
                "youtube",
            )
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code >= 400:
            detail = response.text[:300]
            # invalid_grant is the 7-day Testing-mode refresh-token expiry, by
            # far the most common real failure. Name it so Vinta knows the fix
            # rather than staring at an opaque 400.
            if "invalid_grant" in detail:
                raise DistributionError(
                    "YouTube refresh token is expired or revoked. If the OAuth "
                    "consent screen is in Testing mode, tokens die every 7 days "
                    "— publish the app or re-run the consent flow "
                    "(scripts/youtube_auth.py).",
                    "youtube",
                )
            raise DistributionError(f"YouTube token refresh failed: {detail}", "youtube")
        return response.json()["access_token"]

    # ── media acquisition ────────────────────────────────────────────────────
    async def _materialize(self, client: httpx.AsyncClient, video: str) -> tuple[str, bool]:
        """Return (local_path, is_temp). Streams remote URLs to disk in chunks.

        Streaming to a temp file rather than holding bytes in RAM is what makes
        large uploads survivable, and it also gives us an exact content length,
        which the resumable protocol requires up front.
        """
        if not video:
            raise DistributionError("YouTube requires a video file or URL", "youtube")

        if not video.startswith(("http://", "https://")):
            if not os.path.isfile(video):
                raise DistributionError(f"Video file not found: {video}", "youtube")
            return video, False

        fd, tmp_path = tempfile.mkstemp(suffix=".mp4", prefix="dirco_yt_")
        try:
            with os.fdopen(fd, "wb") as fh:
                async with client.stream("GET", video, follow_redirects=True) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                        fh.write(chunk)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return tmp_path, True

    # ── resumable upload ─────────────────────────────────────────────────────
    async def _upload_bytes(
        self, client: httpx.AsyncClient, session_uri: str, path: str, total: int
    ) -> dict:
        """Push the file in chunks, resuming from YouTube's byte count on error."""
        offset = 0
        attempts = 0
        with open(path, "rb") as fh:
            while offset < total:
                fh.seek(offset)
                chunk = fh.read(CHUNK_SIZE)
                end = offset + len(chunk) - 1
                try:
                    resp = await client.put(
                        session_uri,
                        headers={
                            "Content-Length": str(len(chunk)),
                            "Content-Range": f"bytes {offset}-{end}/{total}",
                        },
                        content=chunk,
                    )
                except httpx.HTTPError as exc:
                    attempts += 1
                    if attempts > MAX_RESUME_ATTEMPTS:
                        raise DistributionError(
                            f"YouTube upload failed after {MAX_RESUME_ATTEMPTS} resume attempts: {exc}",
                            "youtube",
                        ) from exc
                    offset = await self._resume_offset(client, session_uri, total, offset)
                    continue

                # 200/201 = the whole upload is committed; body is the video.
                if resp.status_code in (200, 201):
                    return resp.json()
                # 308 = "Resume Incomplete" — the happy path between chunks.
                if resp.status_code == 308:
                    rng = resp.headers.get("Range")
                    offset = int(rng.split("-")[1]) + 1 if rng else offset + len(chunk)
                    attempts = 0
                    continue
                # 5xx is transient per Google's guidance — re-query and retry.
                if resp.status_code >= 500:
                    attempts += 1
                    if attempts > MAX_RESUME_ATTEMPTS:
                        raise DistributionError(
                            f"YouTube upload failed (HTTP {resp.status_code}) after retries",
                            "youtube",
                        )
                    offset = await self._resume_offset(client, session_uri, total, offset)
                    continue
                raise DistributionError(
                    f"YouTube upload rejected (HTTP {resp.status_code}): {resp.text[:300]}",
                    "youtube",
                )
        raise DistributionError("YouTube upload ended without a final response", "youtube")

    async def _resume_offset(
        self, client: httpx.AsyncClient, session_uri: str, total: int, current: int
    ) -> int:
        """Ask YouTube how many bytes it actually holds, so we resume exactly."""
        try:
            probe = await client.put(
                session_uri,
                headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"},
            )
            if probe.status_code == 308:
                rng = probe.headers.get("Range")
                if rng and "-" in rng:
                    return int(rng.split("-")[1]) + 1
                return 0
        except httpx.HTTPError:
            pass
        return current

    async def upload_video(
        self,
        video_url: str,
        title: str,
        description: str = "",
        tags: Optional[list[str]] = None,
        privacy: str = "public",
        category_id: str = DEFAULT_CATEGORY,
        thumbnail_url: Optional[str] = None,
        made_for_kids: bool = False,
    ) -> dict:
        """Upload a video (local path or URL) to YouTube. Returns id + url."""
        if privacy not in VALID_PRIVACY:
            raise DistributionError(
                f"Invalid privacy '{privacy}' (expected one of {sorted(VALID_PRIVACY)})",
                "youtube",
            )

        temp_path: Optional[str] = None
        async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=30.0)) as client:
            token = await self._access_token(client)
            client.headers["Authorization"] = f"Bearer {token}"

            path, is_temp = await self._materialize(client, video_url)
            if is_temp:
                temp_path = path
            try:
                total = os.path.getsize(path)
                if total == 0:
                    raise DistributionError("Video file is empty", "youtube")

                # 1. Initiate the resumable session.
                init = await client.post(
                    f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
                    headers={
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/*",
                        "X-Upload-Content-Length": str(total),
                    },
                    json={
                        "snippet": {
                            "title": (title or "DirCo update")[:100],
                            "description": (description or "")[:5000],
                            "tags": (tags or [])[:30],
                            "categoryId": category_id,
                        },
                        "status": {
                            "privacyStatus": privacy,
                            "selfDeclaredMadeForKids": made_for_kids,
                        },
                    },
                )
                if init.status_code >= 400:
                    raise DistributionError(
                        f"YouTube rejected the upload session: {init.text[:300]}", "youtube"
                    )
                session_uri = init.headers.get("Location")
                if not session_uri:
                    raise DistributionError(
                        "YouTube did not return an upload session", "youtube"
                    )

                # 2. Stream the bytes.
                data = await self._upload_bytes(client, session_uri, path, total)
                video_id = data.get("id")
                if not video_id:
                    raise DistributionError(
                        f"YouTube upload returned no video id: {str(data)[:200]}", "youtube"
                    )

                # 3. Thumbnail — best-effort. A published video with a default
                #    thumbnail beats a failed publish over a cosmetic asset.
                thumb_status = None
                if thumbnail_url:
                    try:
                        thumb_status = await self._set_thumbnail(client, video_id, thumbnail_url)
                    except Exception as exc:  # noqa: BLE001
                        thumb_status = f"failed: {str(exc)[:120]}"

                return {
                    "id": video_id,
                    "url": f"https://youtu.be/{video_id}",
                    "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
                    "privacy": privacy,
                    "bytes": total,
                    "thumbnail": thumb_status,
                    "status": "posted",
                }
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

    async def _set_thumbnail(
        self, client: httpx.AsyncClient, video_id: str, thumbnail: str
    ) -> str:
        """Set a custom thumbnail (requires a verified channel)."""
        if thumbnail.startswith(("http://", "https://")):
            resp = await client.get(thumbnail, follow_redirects=True)
            resp.raise_for_status()
            blob = resp.content
            ctype = resp.headers.get("Content-Type", "image/jpeg")
        else:
            if not os.path.isfile(thumbnail):
                return "failed: file not found"
            with open(thumbnail, "rb") as fh:
                blob = fh.read()
            ctype = "image/png" if thumbnail.lower().endswith(".png") else "image/jpeg"

        if len(blob) > 2 * 1024 * 1024:
            return "skipped: thumbnail exceeds YouTube's 2MB limit"

        resp = await client.post(
            f"{THUMBNAIL_URL}?videoId={video_id}",
            headers={"Content-Type": ctype},
            content=blob,
        )
        if resp.status_code >= 400:
            return f"failed: {resp.text[:120]}"
        return "set"

    async def health(self) -> dict:
        """Token refresh succeeds = credentials alive. No quota spent on uploads."""
        if not self.configured:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await self._access_token(client)
                return {"configured": True, "live": True}
        except Exception as exc:  # noqa: BLE001
            return {"configured": True, "live": False, "error": str(exc)[:200]}
