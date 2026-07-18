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

        # Generate voiceover (Piper-backed — see heygen.text_to_speech).
        vo_job = await self.heygen.text_to_speech(script.get("narration", description))
        vo_audio_url = vo_job.get("audio_url", "") or vo_job.get("audio_path", "")

        # Generate b-roll clips for each visual prompt. External gen-video APIs
        # (Runway) rot / 401 — treat them as OPTIONAL. Any failure just means we
        # assemble without generative b-roll.
        clip_urls = []
        for visual_prompt in script.get("visual_prompts", [description])[:3]:
            try:
                task = await self.runway.generate_video(
                    prompt=f"{visual_prompt}, {style}, high quality, {project_slug} brand",
                    duration=min(10, duration // max(1, len(script.get("visual_prompts", [1])))),
                )
                clip_url = await self.runway.poll_until_done(task["id"])
                if clip_url:
                    clip_urls.append(clip_url)
            except Exception as e:
                print(f"[hype-clip] runway skipped ({str(e)[:80]}) — assembling without b-roll")
                break

        # Assemble. Try Creatomate first; if it (or its API) fails, fall back to
        # the local ffmpeg builder that needs NO external render service — so a
        # clip is ALWAYS produced.
        slug_key = project_slug.replace("-", "_")
        try:
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
            out_url = render_result.get("url")
            status = render_result.get("status")
            if not out_url:
                raise RuntimeError("creatomate returned no url")
        except Exception as e:
            print(f"[hype-clip] creatomate skipped ({str(e)[:80]}) — local ffmpeg assembly")
            out_url = self._local_assemble(script, vo_job, project_slug, duration)
            status = "completed" if out_url else "failed"

        return {
            "content_id": content_id,
            "output_url": out_url,
            "script": script,
            "status": status,
        }

    def _local_assemble(self, script: dict, vo_job: dict, project_slug: str, duration: int) -> str:
        """No-external-service fallback: build a titled clip from the narration
        audio + script text using ffmpeg. Mirrors the proven direct-build path.
        Returns the output file path, or '' on failure."""
        import os, subprocess, wave, contextlib, tempfile
        try:
            audio = vo_job.get("audio_path") or vo_job.get("audio_url")
            if not audio or not os.path.exists(audio):
                return ""
            with contextlib.closing(wave.open(audio, "rb")) as w:
                adur = w.getnframes() / float(w.getframerate() or 16000)
            out_dir = os.environ.get("MEDIA_UPLOAD_DIR", "/tmp")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"hype_{project_slug}_{int(__import__('time').time())}.mp4")
            font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            # on-screen text = narration wrapped; keep it simple + safe via textfile
            tf = tempfile.NamedTemporaryFile("w", suffix=".txt", dir=out_dir, delete=False)
            narr = script.get("narration", "") or f"{project_slug}"
            tf.write("\n".join(narr[i:i+34] for i in range(0, min(len(narr), 170), 34))); tf.close()
            bf = tempfile.NamedTemporaryFile("w", suffix=".txt", dir=out_dir, delete=False)
            bf.write(project_slug.upper()); bf.close()
            vf = (f"drawtext=fontfile={font}:textfile={tf.name}:fontcolor=white:fontsize=54:"
                  f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing=16,"
                  f"drawtext=fontfile={font}:textfile={bf.name}:fontcolor=0x7c6cff:fontsize=40:"
                  f"x=(w-text_w)/2:y=h-200")
            subprocess.run(
                ["ffmpeg", "-f", "lavfi", "-i", f"color=c=0x0a0a12:s=1080x1920:d={adur:.2f}",
                 "-i", audio, "-vf", vf, "-c:v", "libx264", "-c:a", "aac",
                 "-pix_fmt", "yuv420p", "-r", "30", "-shortest", out_path, "-y"],
                check=True, capture_output=True, timeout=120,
            )
            return out_path if os.path.exists(out_path) else ""
        except Exception as e:
            print(f"[hype-clip] local ffmpeg assembly failed: {str(e)[:120]}")
            return ""
