"""
Bluesky client — Phase 3 (council decree 2026-07-04).

AT Protocol via plain httpx: createSession with handle + app password, then
app.bsky.feed.post records. Ten-minute integration, open network, no gatekeeper.
Setup: bsky.app → Settings → App Passwords → create one → env keys.
"""
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.core.exceptions import DistributionError

BASE = "https://bsky.social/xrpc"


class BlueskyClient:
    def __init__(self):
        self.handle = settings.bluesky_handle
        self.app_password = settings.bluesky_app_password

    @property
    def configured(self) -> bool:
        return bool(self.handle and self.app_password)

    async def _session(self, client: httpx.AsyncClient) -> dict:
        if not self.configured:
            raise DistributionError("Bluesky not configured", "bluesky")
        response = await client.post(
            f"{BASE}/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
        )
        response.raise_for_status()
        return response.json()  # {accessJwt, did, ...}

    async def post_message(self, text: str, media_url: str | None = None) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            session = await self._session(client)
            headers = {"Authorization": f"Bearer {session['accessJwt']}"}

            record: dict = {
                "$type": "app.bsky.feed.post",
                "text": text[:300],  # Bluesky grapheme limit
                "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }

            # Optional image embed (video embeds need heavier processing — Phase 4).
            if media_url and not media_url.endswith((".mp4", ".mov", ".webm")):
                try:
                    media = await client.get(media_url)
                    media.raise_for_status()
                    blob_resp = await client.post(
                        f"{BASE}/com.atproto.repo.uploadBlob",
                        headers={**headers, "Content-Type": media.headers.get("content-type", "image/jpeg")},
                        content=media.content,
                    )
                    blob_resp.raise_for_status()
                    record["embed"] = {
                        "$type": "app.bsky.embed.images",
                        "images": [{"alt": text[:100], "image": blob_resp.json()["blob"]}],
                    }
                except Exception:
                    pass  # image best-effort; the text still posts

            response = await client.post(
                f"{BASE}/com.atproto.repo.createRecord",
                headers=headers,
                json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
            )
            response.raise_for_status()
            data = response.json()
            return {"id": data.get("uri", ""), "cid": data.get("cid", ""), "status": "posted"}

    async def health(self) -> dict:
        if not self.configured:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await self._session(client)
                return {"configured": True, "live": True}
        except Exception:
            return {"configured": True, "live": False}
