import anthropic
from typing import Optional

from app.config import settings
from app.services.content_engine.brand_voice import load_brand_voice


class ContentGenerator:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_text(
        self,
        project_slug: str,
        topic: str,
        platforms: list[str],
        content_hint: Optional[str] = None,
    ) -> dict:
        brand = load_brand_voice(project_slug)

        platform_str = ", ".join(platforms)
        platform_notes = "\n".join(
            f"- {p}: {brand.get_platform_instructions(p)}"
            for p in platforms
            if brand.get_platform_instructions(p)
        )

        prompt = f"""You are creating social media content for {brand.name}.

Brand voice: {brand.tone}
Personality: {brand.personality}
Target audience: {brand.audience}
Content pillars: {', '.join(brand.content_pillars)}

Platform notes:
{platform_notes or 'Use platform best practices.'}

Avoid: {', '.join(brand.avoid)}

Topic: {topic}
{"Additional context: " + content_hint if content_hint else ""}

Generate a social media post optimized for: {platform_str}

Return JSON with:
- title: short hook/headline (max 10 words)
- body: the post text (platform-appropriate length)
- hashtags: list of 3-5 relevant hashtags

Make it punchy, authentic, and on-brand."""

        # frugal-max ruling (council 2026-07-04): Opus is never justified for
        # social post text. Model is env-configurable via CONTENT_TEXT_MODEL.
        response = await self.client.messages.create(
            model=settings.content_text_model,
            max_tokens=1024,
            system=brand.system_prompt or "You are a social media content expert. Always return valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )

        import json, re
        text = response.content[0].text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = {"title": topic, "body": text, "hashtags": brand.hashtags[:5]}

        return {
            "title": data.get("title", ""),
            "body": data.get("body", ""),
            "hashtags": data.get("hashtags", brand.hashtags[:5]),
            "prompt": prompt,
            "metadata": {
                "model": settings.content_text_model,
                "project": project_slug,
                "platforms": platforms,
                "brand_tone": brand.tone,
            },
        }

    async def generate_video_script(
        self,
        project_slug: str,
        description: str,
        duration: int = 30,
        style: str = "cinematic",
    ) -> dict:
        brand = load_brand_voice(project_slug)

        prompt = f"""Create a {duration}-second {style} video script for {brand.name}.

Description: {description}
Brand tone: {brand.tone}
Audience: {brand.audience}

Return JSON with:
- narration: the voiceover script (time-matched to {duration} seconds)
- visual_prompts: list of 3-5 visual scene descriptions for AI video generation
- music_mood: one of [epic, hype, chill, dramatic, energetic, mysterious]
- text_overlays: list of {{time_seconds, text}} objects for motion graphics"""

        response = await self.client.messages.create(
            model=settings.video_script_model,
            max_tokens=1500,
            system="You are a video director and scriptwriter. Return valid JSON.",
            messages=[{"role": "user", "content": prompt}],
        )

        import json, re
        text = response.content[0].text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"narration": description, "visual_prompts": [description], "music_mood": "hype", "text_overlays": []}
