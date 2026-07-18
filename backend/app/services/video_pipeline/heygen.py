import httpx
import asyncio
from app.config import settings


class HeyGenClient:
    BASE_URL = "https://api.heygen.com"

    def __init__(self):
        self.api_key = settings.heygen_api_key
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def generate_voiceover(
        self,
        text: str,
        voice_id: str = "en-US-AndrewMultilingualNeural",
        speed: float = 1.0,
    ) -> dict:
        """Generate a voiceover audio file from text."""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.BASE_URL}/v2/video.generate",
                headers=self.headers,
                json={
                    "video_inputs": [
                        {
                            "character": {
                                "type": "talking_photo",
                                "talking_photo_id": "default",
                            },
                            "voice": {
                                "type": "text",
                                "input_text": text,
                                "voice_id": voice_id,
                                "speed": speed,
                            },
                        }
                    ],
                    "dimension": {"width": 1920, "height": 1080},
                },
            )
            response.raise_for_status()
            return response.json()

    async def text_to_speech(self, text: str, voice_id: str = "en-US-AndrewMultilingualNeural") -> dict:
        """Generate audio-only voiceover.

        HeyGen's /v1/text_to_speech.generate endpoint returns 404 (deprecated).
        Rather than couple the whole pipeline to HeyGen's API churn, we generate
        the voiceover with the local Piper TTS service (port 8769) — free,
        reliable, no external dependency. Returns {audio_path, audio_url,
        duration}. Falls back to the HeyGen HTTP call only if Piper is down.
        """
        import os, subprocess, tempfile, wave
        try:
            piper_host = os.environ.get("PIPER_HOST", "127.0.0.1")
            piper_port = os.environ.get("PIPER_PORT", "8769")
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"http://{piper_host}:{piper_port}/synth-pcm",
                    json={"text": text},
                )
                r.raise_for_status()
                pcm = r.content
            # PCM int16 mono 16kHz → wav on disk
            out_dir = os.environ.get("MEDIA_UPLOAD_DIR", "/tmp")
            os.makedirs(out_dir, exist_ok=True)
            fd, wav_path = tempfile.mkstemp(suffix=".wav", dir=out_dir)
            os.close(fd)
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(pcm)
            duration = len(pcm) / 2 / 16000.0
            return {"audio_path": wav_path, "audio_url": wav_path,
                    "duration": duration, "narration": text, "engine": "piper"}
        except Exception as piper_err:
            # Last-resort: try HeyGen (may 404 — surfaces the real error).
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/text_to_speech.generate",
                    headers=self.headers,
                    json={"text": text, "voice_id": voice_id, "speed": 1.0},
                )
                response.raise_for_status()
                return response.json()

    async def get_video_status(self, video_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.BASE_URL}/v1/video_status.get",
                headers=self.headers,
                params={"video_id": video_id},
            )
            response.raise_for_status()
            return response.json()

    async def poll_until_done(self, video_id: str, max_polls: int = 60) -> str:
        for _ in range(max_polls):
            await asyncio.sleep(5)
            status = await self.get_video_status(video_id)
            data = status.get("data", {})
            if data.get("status") == "completed":
                return data["video_url"]
            if data.get("status") == "failed":
                raise RuntimeError(f"HeyGen video failed: {data.get('error')}")
        raise TimeoutError(f"HeyGen video {video_id} timed out")
