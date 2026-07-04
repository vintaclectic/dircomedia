import httpx
from app.config import settings


class InstagramClient:
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.access_token = settings.instagram_access_token
        self.ig_user_id: str = ""  # Set after fetching account info

    async def get_user_id(self) -> str:
        if self.ig_user_id:
            return self.ig_user_id
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/me/accounts",
                params={"access_token": self.access_token},
            )
            resp.raise_for_status()
            pages = resp.json().get("data", [])
            if pages:
                self.ig_user_id = pages[0]["id"]
        return self.ig_user_id

    async def post_image(self, image_url: str, caption: str) -> dict:
        user_id = await self.get_user_id()
        async with httpx.AsyncClient(timeout=60) as client:
            # Create media container
            container_resp = await client.post(
                f"{self.BASE_URL}/{user_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self.access_token,
                },
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]

            # Publish
            publish_resp = await client.post(
                f"{self.BASE_URL}/{user_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
            )
            publish_resp.raise_for_status()
            return publish_resp.json()

    async def post_reel(self, video_url: str, caption: str, cover_url: str = None) -> dict:
        user_id = await self.get_user_id()
        async with httpx.AsyncClient(timeout=120) as client:
            params = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": self.access_token,
            }
            if cover_url:
                params["cover_url"] = cover_url

            container_resp = await client.post(
                f"{self.BASE_URL}/{user_id}/media", params=params
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]

            # Wait for video to process
            import asyncio
            for _ in range(30):
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"{self.BASE_URL}/{container_id}",
                    params={"fields": "status_code", "access_token": self.access_token},
                )
                if status_resp.json().get("status_code") == "FINISHED":
                    break

            publish_resp = await client.post(
                f"{self.BASE_URL}/{user_id}/media_publish",
                params={"creation_id": container_id, "access_token": self.access_token},
            )
            publish_resp.raise_for_status()
            return publish_resp.json()
