import httpx
import asyncio
from app.config import settings


class RunwayClient:
    BASE_URL = "https://api.dev.runwayml.com/v1"

    def __init__(self):
        self.api_key = settings.runway_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        }

    async def generate_video(
        self,
        prompt: str,
        duration: int = 10,
        ratio: str = "1280:720",
        model: str = "gen4_turbo",
    ) -> dict:
        """Generate a video from a text prompt."""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.BASE_URL}/text_to_video",
                headers=self.headers,
                json={
                    "promptText": prompt,
                    "model": model,
                    "duration": duration,
                    "ratio": ratio,
                },
            )
            response.raise_for_status()
            return response.json()

    async def image_to_video(
        self,
        image_url: str,
        prompt: str,
        duration: int = 10,
        model: str = "gen4_turbo",
    ) -> dict:
        """Animate a still image into video."""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.BASE_URL}/image_to_video",
                headers=self.headers,
                json={
                    "promptImage": image_url,
                    "promptText": prompt,
                    "model": model,
                    "duration": duration,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_task(self, task_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def poll_until_done(self, task_id: str, max_polls: int = 60) -> str:
        """Poll task until done, returns output URL."""
        for _ in range(max_polls):
            await asyncio.sleep(10)
            task = await self.get_task(task_id)
            if task["status"] == "SUCCEEDED":
                return task["output"][0]
            if task["status"] == "FAILED":
                raise RuntimeError(f"Runway task failed: {task.get('failure')}")
        raise TimeoutError(f"Runway task {task_id} timed out")
