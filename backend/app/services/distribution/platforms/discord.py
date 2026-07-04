"""
Discord client — Phase 2 (council decree 2026-07-04).

Posts announcements via channel webhooks. Highest value-per-effort platform
for DirHaven's community. Supports a global default webhook plus optional
per-project overrides (DISCORD_WEBHOOK_URL_<SLUG> env style via config map).
"""
import httpx

from app.config import settings
from app.core.exceptions import DistributionError


class DiscordClient:
    def __init__(self):
        self.default_webhook = settings.discord_webhook_url

    def _webhook_for(self, project_slug: str) -> str:
        overrides = settings.discord_webhook_overrides or {}
        url = overrides.get(project_slug) or overrides.get(project_slug.replace("-", "_")) or self.default_webhook
        if not url:
            raise DistributionError("No Discord webhook configured", "discord")
        return url

    async def post_message(
        self,
        text: str,
        media_url: str | None = None,
        project_slug: str = "",
        username: str | None = None,
    ) -> dict:
        payload: dict = {"content": text[:2000]}
        if username:
            payload["username"] = username[:80]
        if media_url:
            # Discord unfurls URLs; embed keeps it clean for images.
            payload["embeds"] = [{"image": {"url": media_url}}] if not media_url.endswith(
                (".mp4", ".mov", ".webm")
            ) else []
            if not payload["embeds"]:
                payload["content"] = f"{payload['content']}\n{media_url}"[:2000]

        url = self._webhook_for(project_slug)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{url}?wait=true", json=payload)
            response.raise_for_status()
            data = response.json()
            return {"id": data.get("id"), "channel_id": data.get("channel_id"), "status": "posted"}

    async def health(self, project_slug: str = "") -> dict:
        """GET the webhook — cheap liveness check, no message sent."""
        try:
            url = self._webhook_for(project_slug)
        except DistributionError:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                return {"configured": True, "live": response.status_code == 200}
        except Exception:
            return {"configured": True, "live": False}
