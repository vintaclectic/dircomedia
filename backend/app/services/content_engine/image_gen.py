import httpx
from app.config import settings
from app.services.content_engine.brand_voice import load_brand_voice


class ImageGenerator:
    def __init__(self):
        self.replicate_token = settings.replicate_api_token

    async def generate(
        self,
        project_slug: str,
        prompt: str,
        aspect_ratio: str = "1:1",
        model: str = "flux-1.1-pro",
    ) -> str:
        """Generate an image and return the URL."""
        brand = load_brand_voice(project_slug)
        full_prompt = f"{prompt}, {brand.tone} style, high quality, professional"

        headers = {
            "Authorization": f"Token {self.replicate_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
                headers=headers,
                json={
                    "input": {
                        "prompt": full_prompt,
                        "aspect_ratio": aspect_ratio,
                        "output_format": "webp",
                        "output_quality": 90,
                    }
                },
            )
            response.raise_for_status()
            prediction = response.json()

            # Poll for completion
            import asyncio
            prediction_url = prediction["urls"]["get"]
            for _ in range(60):
                await asyncio.sleep(2)
                poll = await client.get(prediction_url, headers=headers)
                poll_data = poll.json()
                if poll_data["status"] == "succeeded":
                    return poll_data["output"][0]
                if poll_data["status"] == "failed":
                    raise RuntimeError(f"Image generation failed: {poll_data.get('error')}")

            raise TimeoutError("Image generation timed out")
