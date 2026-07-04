import httpx
from app.config import settings


class CreatomateClient:
    BASE_URL = "https://api.creatomate.com/v1"

    def __init__(self):
        self.api_key = settings.creatomate_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def render(self, template_id: str, modifications: dict) -> dict:
        """Render a video using a Creatomate template."""
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self.BASE_URL}/renders",
                headers=self.headers,
                json={
                    "template_id": template_id,
                    "modifications": modifications,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_render_status(self, render_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.BASE_URL}/renders/{render_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def wrap_recording(
        self,
        video_url: str,
        project_slug: str,
        overlay_config: dict,
    ) -> dict:
        """Wrap a screen recording with cinematic overlays."""
        modifications = {
            "video-source": {"source": video_url},
            "brand-logo": {"source": overlay_config.get("logo_url", "")},
            "title-text": {"text": overlay_config.get("title", "")},
            "outro-text": {"text": overlay_config.get("outro", "")},
            "color-accent": {"color": overlay_config.get("brand_color", "#ffffff")},
            "music-track": {"source": overlay_config.get("music_url", "")},
        }
        return await self.render(
            template_id=overlay_config.get("template_id", ""),
            modifications=modifications,
        )

    async def poll_until_done(self, render_id: str, max_polls: int = 120) -> dict:
        import asyncio
        for _ in range(max_polls):
            await asyncio.sleep(5)
            status = await self.get_render_status(render_id)
            if status["status"] in ("succeeded", "failed"):
                return status
        raise TimeoutError(f"Render {render_id} timed out")
