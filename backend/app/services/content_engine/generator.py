import os
import anthropic
from typing import Optional

from app.config import settings
from app.services.content_engine.brand_voice import load_brand_voice

# ── Hermes/OpenRouter fallback (Vinta directive 2026-07-18) ──────────────────
# The Anthropic account periodically runs out of credits, which killed the
# whole video/content pipeline at the very first step (script-gen). When an
# OpenRouter key is present we route text generation there (OpenAI-compatible),
# defaulting to Hermes — cheap, resilient, and it dogfoods Vintinuum's own
# muscle. Anthropic stays the default when no OpenRouter key is set, so
# existing behaviour is unchanged.
_OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
_HERMES_MODEL = os.environ.get("HERMES_MODEL", "nousresearch/hermes-4-70b").strip()
_USE_OPENROUTER = bool(_OPENROUTER_KEY)


class ContentGenerator:
    def __init__(self):
        self._use_or = _USE_OPENROUTER
        if self._use_or:
            # Lazy import so the dep is only needed when actually used.
            from openai import AsyncOpenAI
            self.oai = AsyncOpenAI(api_key=_OPENROUTER_KEY, base_url="https://openrouter.ai/api/v1")
        # Anthropic client kept for fallback / when no OpenRouter key.
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def _complete(self, *, model: str, system: str, prompt: str, max_tokens: int) -> str:
        """Provider-agnostic single-shot completion → returns raw text.
        Uses OpenRouter/Hermes when configured, else Anthropic. Strips any
        <think>…</think> reasoning blocks (Hermes-4 is a reasoning model)."""
        if self._use_or:
            r = await self.oai.chat.completions.create(
                model=_HERMES_MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            text = r.choices[0].message.content or ""
        else:
            r = await self.client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = r.content[0].text
        # Strip reasoning blocks so JSON parsing downstream never chokes on them.
        import re
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
        return text

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
        # Routes to Hermes/OpenRouter when configured (resilient to Anthropic
        # credit outages), else Anthropic.
        text = await self._complete(
            model=settings.content_text_model,
            max_tokens=1024,
            system=brand.system_prompt or "You are a social media content expert. Always return valid JSON.",
            prompt=prompt,
        )

        import json, re
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

        text = await self._complete(
            model=settings.video_script_model,
            max_tokens=1500,
            system="You are a video director and scriptwriter. Return valid JSON.",
            prompt=prompt,
        )

        import json, re
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"narration": description, "visual_prompts": [description], "music_mood": "hype", "text_overlays": []}
