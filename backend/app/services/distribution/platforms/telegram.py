"""
Telegram client — Phase 2 (council decree 2026-07-04).

Posts to a channel via the Bot API. Near-zero friction; the brain already
speaks Telegram, so DirCo announcements ride the same rails.
"""
import httpx

from app.config import settings
from app.core.exceptions import DistributionError


class TelegramClient:
    BASE_URL = "https://api.telegram.org"

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.channel_id = settings.telegram_channel_id

    def _url(self, method: str) -> str:
        if not self.bot_token:
            raise DistributionError("No Telegram bot token configured", "telegram")
        return f"{self.BASE_URL}/bot{self.bot_token}/{method}"

    async def post_message(self, text: str, media_url: str | None = None) -> dict:
        if not self.channel_id:
            raise DistributionError("No Telegram channel configured", "telegram")

        async with httpx.AsyncClient(timeout=60) as client:
            if media_url and media_url.endswith((".mp4", ".mov", ".webm")):
                response = await client.post(
                    self._url("sendVideo"),
                    json={"chat_id": self.channel_id, "video": media_url, "caption": text[:1024]},
                )
            elif media_url:
                response = await client.post(
                    self._url("sendPhoto"),
                    json={"chat_id": self.channel_id, "photo": media_url, "caption": text[:1024]},
                )
            else:
                response = await client.post(
                    self._url("sendMessage"),
                    json={"chat_id": self.channel_id, "text": text[:4096]},
                )
            response.raise_for_status()
            data = response.json()
            msg = data.get("result", {})
            return {"id": str(msg.get("message_id", "")), "status": "posted"}

    async def health(self) -> dict:
        """getMe — cheap liveness probe."""
        if not self.bot_token:
            return {"configured": False, "live": None}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(self._url("getMe"))
                ok = response.status_code == 200 and response.json().get("ok", False)
                return {"configured": bool(self.channel_id), "live": ok}
        except Exception:
            return {"configured": bool(self.channel_id), "live": False}
