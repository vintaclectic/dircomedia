import httpx
from app.config import settings


class TikTokClient:
    BASE_URL = "https://open.tiktokapis.com/v2"

    def __init__(self):
        self.client_key = settings.tiktok_client_key
        self.client_secret = settings.tiktok_client_secret
        self.access_token = settings.tiktok_access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    async def post_video(
        self,
        video_url: str,
        caption: str,
        privacy: str = "PUBLIC_TO_EVERYONE",
    ) -> dict:
        """Post a video to TikTok via URL."""
        async with httpx.AsyncClient(timeout=60) as client:
            # Initialize upload
            init_resp = await client.post(
                f"{self.BASE_URL}/post/publish/video/init/",
                headers=self._headers(),
                json={
                    "post_info": {
                        "title": caption[:2200],
                        "privacy_level": privacy,
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": video_url,
                    },
                },
            )
            init_resp.raise_for_status()
            data = init_resp.json().get("data", {})
            publish_id = data.get("publish_id")
            return {"publish_id": publish_id, "status": "submitted"}

    async def get_post_status(self, publish_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.BASE_URL}/post/publish/status/fetch/",
                headers=self._headers(),
                json={"publish_id": publish_id},
            )
            response.raise_for_status()
            return response.json()

    async def post_photo(self, image_url: str, caption: str) -> dict:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/post/publish/content/init/",
                headers=self._headers(),
                json={
                    "post_info": {
                        "title": caption[:2200],
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "photo_cover_index": 0,
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "photo_images": [image_url],
                        "photo_cover_index": 0,
                    },
                    "post_mode": "DIRECT_POST",
                    "media_type": "PHOTO",
                },
            )
            resp.raise_for_status()
            return resp.json()
