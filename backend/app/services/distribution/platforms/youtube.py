"""
YouTube client — Phase 2 (council decree 2026-07-04).

YouTube Data API v3 via raw httpx (no google client lib needed):
  - OAuth refresh-token flow (offline access, owner-only)
  - Resumable video upload (videos.insert, uploadType=resumable)

Quota reality: video upload costs 1,600 units of the 10,000/day default —
~6 uploads/day ceiling. Fine for owner cadence. Community posts have NO
public API (extension-assisted or manual). See docs/PLATFORM_CONNECTIONS.md §5.
"""
import httpx

from app.config import settings
from app.core.exceptions import DistributionError

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


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
            raise DistributionError("YouTube OAuth not configured", "youtube")
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    async def upload_video(
        self,
        video_url: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        privacy: str = "public",
    ) -> dict:
        """Stream a video from a URL into a resumable YouTube upload."""
        if not video_url:
            raise DistributionError("YouTube requires a video URL", "youtube")

        async with httpx.AsyncClient(timeout=600) as client:
            token = await self._access_token(client)

            # Fetch the media (R2 or any public URL) into memory/stream.
            media = await client.get(video_url)
            media.raise_for_status()
            body = media.content

            # 1. Initiate resumable session
            init = await client.post(
                f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/*",
                    "X-Upload-Content-Length": str(len(body)),
                },
                json={
                    "snippet": {
                        "title": title[:100] or "DirCo update",
                        "description": description[:4900],
                        "tags": (tags or [])[:15],
                        "categoryId": "20",  # Gaming — DirCo's home turf
                    },
                    "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
                },
            )
            init.raise_for_status()
            session_uri = init.headers.get("Location")
            if not session_uri:
                raise DistributionError("YouTube did not return an upload session", "youtube")

            # 2. Upload the bytes
            up = await client.put(
                session_uri,
                headers={"Content-Type": "video/*", "Content-Length": str(len(body))},
                content=body,
            )
            up.raise_for_status()
            data = up.json()
            return {
                "id": data.get("id"),
                "url": f"https://youtu.be/{data.get('id')}",
                "status": "posted",
            }

    async def health(self) -> dict:
        """Token refresh succeeds = credentials alive. No quota spent on uploads."""
        if not self.configured:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await self._access_token(client)
                return {"configured": True, "live": True}
        except Exception:
            return {"configured": True, "live": False}
