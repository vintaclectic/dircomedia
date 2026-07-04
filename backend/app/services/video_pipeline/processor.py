from app.services.video_pipeline.creatomate import CreatomateClient
from app.services.video_pipeline.runway import RunwayClient
from app.services.video_pipeline.heygen import HeyGenClient
from app.services.content_engine.generator import ContentGenerator
from app.services.content_engine.brand_voice import load_brand_voice


BRAND_COLORS = {
    "dirco": "#0066FF",
    "dirhaven_rp": "#FF4444",
    "dirhaven_app": "#00CC88",
    "dirmegle": "#FF6B00",
    "medaled": "#FFD700",
    "agentis": "#8B5CF6",
    "vintinuum": "#EC4899",
}

# Creatomate template IDs
# To find/create these: go to app.creatomate.com → Templates
# Each template has an ID in the URL: /templates/{id}
# RECORDING_TEMPLATES: accepts a "video-source" element + brand overlays
# HYPE_TEMPLATES: accepts "clips" array + narration audio + text overlays
RECORDING_TEMPLATES: dict[str, str] = {
    "dirco":        "",   # e.g. "abc123def456"
    "dirhaven_rp":  "",
    "dirhaven_app": "",
    "dirmegle":     "",
    "medaled":      "",
    "agentis":      "",
    "vintinuum":    "",
    "_default":     "",   # fallback if project has no template yet
}

HYPE_TEMPLATES: dict[str, str] = {
    "dirco":        "",
    "dirhaven_rp":  "",
    "dirhaven_app": "",
    "dirmegle":     "",
    "medaled":      "",
    "agentis":      "",
    "vintinuum":    "",
    "_default":     "",
}


def _get_template(mapping: dict[str, str], slug_key: str) -> str:
    """Return the template ID for a project, falling back to _default."""
    tid = mapping.get(slug_key, "") or mapping.get("_default", "")
    if not tid:
        raise ValueError(
            f"No Creatomate template configured for '{slug_key}'. "
            "Set the template ID in RECORDING_TEMPLATES or HYPE_TEMPLATES in processor.py."
        )
    return tid


class VideoProcessor:
    def __init__(self):
        self.creatomate = CreatomateClient()
        self.runway = RunwayClient()
        self.heygen = HeyGenClient()
        self.generator = ContentGenerator()

    async def process_recording(
        self,
        content_id: str,
        project_id: str,
        file_path: str,
        project_slug: str,
    ) -> dict:
        """Upload recording and wrap with cinematic overlays via Creatomate."""
        import aiofiles, httpx
        from app.config import settings

        brand = load_brand_voice(project_slug)
        slug_key = project_slug.replace("-", "_")

        # Phase 2: upload raw file to R2 — platforms need a publicly fetchable
        # URL; the old file:// placeholder could never render.
        from app.services.storage.r2 import upload_file, r2_configured
        if r2_configured():
            raw_url = await upload_file(file_path, key_prefix=f"recordings/{slug_key}")
        else:
            raw_url = f"file://{file_path}"  # dev fallback — configure R2 for real posting

        overlay_config = {
            "template_id": _get_template(RECORDING_TEMPLATES, slug_key),
            "logo_url": f"https://assets.dircomedia.app/logos/{slug_key}.png",
            "title": brand.name,
            "outro": "Follow for more",
            "brand_color": BRAND_COLORS.get(slug_key, "#ffffff"),
            "music_url": "",
        }

        render_job = await self.creatomate.wrap_recording(
            video_url=raw_url,
            project_slug=project_slug,
            overlay_config=overlay_config,
        )

        render_result = await self.creatomate.poll_until_done(render_job[0]["id"])
        return {
            "content_id": content_id,
            "output_url": render_result.get("url"),
            "status": render_result.get("status"),
        }

    async def generate_hype_clip(
        self,
        content_id: str,
        description: str,
        project_slug: str,
        duration: int = 30,
        style: str = "cinematic",
    ) -> dict:
        """Generate a full hype/promo clip: script → voiceover → video → assemble."""
        script = await self.generator.generate_video_script(
            project_slug=project_slug,
            description=description,
            duration=duration,
            style=style,
        )

        # Generate voiceover
        vo_job = await self.heygen.text_to_speech(script.get("narration", description))
        vo_audio_url = vo_job.get("audio_url", "")

        # Generate video clips for each visual prompt
        clip_urls = []
        for visual_prompt in script.get("visual_prompts", [description])[:3]:
            task = await self.runway.generate_video(
                prompt=f"{visual_prompt}, {style}, high quality, {project_slug} brand",
                duration=min(10, duration // len(script.get("visual_prompts", [1]))),
            )
            clip_url = await self.runway.poll_until_done(task["id"])
            clip_urls.append(clip_url)

        # Assemble with Creatomate
        slug_key = project_slug.replace("-", "_")
        modifications = {
            "clips": [{"source": url} for url in clip_urls],
            "narration": {"source": vo_audio_url},
            "text_overlays": script.get("text_overlays", []),
            "music_mood": script.get("music_mood", "hype"),
            "brand_color": BRAND_COLORS.get(slug_key, "#ffffff"),
        }

        render_job = await self.creatomate.render(
            template_id=_get_template(HYPE_TEMPLATES, slug_key),
            modifications=modifications,
        )
        render_result = await self.creatomate.poll_until_done(render_job[0]["id"])

        return {
            "content_id": content_id,
            "output_url": render_result.get("url"),
            "script": script,
            "status": render_result.get("status"),
        }
