"""
YouTube SEO engine — task TA3SQSM (2026-08-14).

YouTube is not a social feed; it is a SEARCH ENGINE with a recommendation
engine bolted on. Copy that wins on X ("Karma v2 is live") dies here, because
nobody types "karma v2 is live" into the search bar. The metadata has to carry
the QUERY a human would actually type.

So this module does not "write a title." It produces the whole discovery
package — title, description, tags, chapters — shaped by how YouTube's systems
actually rank:

  1. TITLE (<=100 chars, but <=60 is the real budget — mobile truncates ~60).
     Front-load the query. Curiosity gap AFTER the keyword, never before.
  2. DESCRIPTION — the first 150 chars are the search snippet AND the only part
     shown before "...more". Keyword-dense but human. The rest carries chapters,
     links, and the semantic field the recommender embeds.
  3. TAGS — 500-char total budget across all tags. Low direct ranking weight
     today, but real for disambiguation of made-up brand words ("DirHaven",
     "Vintinuum") that the recommender has never seen.
  4. CHAPTERS — timestamps starting at 00:00 turn one video into many search
     surfaces (key moments) and measurably lift retention.

Model routing mirrors generator.py: OpenRouter/Hermes when configured (survives
Anthropic credit outages), else Anthropic. Every AI call is wrapped so a
failure NEVER blocks an upload — we degrade to deterministic heuristics and
still ship valid metadata. A dead SEO model must not cost Vinta a publish.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from app.config import settings
from app.services.content_engine.brand_voice import load_brand_voice

# ── Hard limits straight from the YouTube Data API v3 contract ───────────────
TITLE_MAX = 100          # API rejects >100
TITLE_TARGET = 60        # mobile/search truncation — the REAL budget
DESC_MAX = 5000          # API rejects >5000
SNIPPET_CHARS = 150      # what shows before "...more"
TAGS_CHAR_BUDGET = 500   # API rejects when the sum of tags exceeds this
TAG_MAX_LEN = 30

# Characters YouTube forbids in titles/descriptions outright ('<' and '>').
_ANGLE = re.compile(r"[<>]")


def sanitize_title(raw: str, fallback: str = "DirCo update") -> str:
    """API-safe, mobile-safe title. Never raises, never returns empty."""
    text = _ANGLE.sub("", str(raw or "")).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        text = fallback
    if len(text) > TITLE_MAX:
        # Cut on a word boundary so we never publish a severed word.
        text = text[:TITLE_MAX].rsplit(" ", 1)[0].rstrip(" -–—|:,")
    return text or fallback


def sanitize_description(raw: str) -> str:
    text = _ANGLE.sub("", str(raw or ""))
    return text[:DESC_MAX]


def sanitize_tags(raw: list[str] | None) -> list[str]:
    """Enforce YouTube's 500-char aggregate tag budget.

    The API counts the SUM of all tag lengths, not the count — exceeding it
    fails the whole insert. We greedily keep the highest-value (earliest) tags
    until the budget is spent, so a too-generous model never breaks an upload.
    """
    out: list[str] = []
    used = 0
    seen: set[str] = set()
    for tag in raw or []:
        clean = _ANGLE.sub("", str(tag or "")).replace(",", " ").strip()
        clean = re.sub(r"\s+", " ", clean)[:TAG_MAX_LEN].strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        # +1 approximates the separator YouTube counts between tags.
        cost = len(clean) + 1
        if used + cost > TAGS_CHAR_BUDGET:
            continue
        out.append(clean)
        seen.add(key)
        used += cost
    return out


def format_chapters(chapters: list[dict] | None) -> str:
    """Render chapters as a YouTube-recognised timestamp block.

    YouTube only activates chapters when the FIRST timestamp is 00:00 and there
    are >=3 of them, each >=10s apart. If the model gives us something that
    can't satisfy that, we return '' rather than publishing dead text.
    """
    if not chapters:
        return ""
    rows: list[tuple[int, str]] = []
    for ch in chapters:
        try:
            secs = int(ch.get("time_seconds", ch.get("t", -1)))
        except (TypeError, ValueError):
            continue
        label = _ANGLE.sub("", str(ch.get("label", ch.get("title", "")))).strip()
        if secs < 0 or not label:
            continue
        rows.append((secs, label))
    if len(rows) < 3:
        return ""
    rows.sort(key=lambda r: r[0])
    if rows[0][0] != 0:
        rows.insert(0, (0, "Intro"))
    # Drop chapters closer than 10s to their predecessor (YouTube's minimum).
    spaced: list[tuple[int, str]] = []
    for secs, label in rows:
        if spaced and secs - spaced[-1][0] < 10:
            continue
        spaced.append((secs, label))
    if len(spaced) < 3:
        return ""
    lines = []
    for secs, label in spaced:
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        stamp = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        lines.append(f"{stamp} {label}")
    return "\n".join(lines)


class YouTubeSEO:
    """Generates the full discovery package for a YouTube upload."""

    SYSTEM = (
        "You are a YouTube growth strategist who has taken channels from zero to "
        "millions of views. You think in SEARCH INTENT, not slogans. You know the "
        "title's job is to win the click from a results page where 20 other "
        "thumbnails are shouting, and that the first 150 characters of the "
        "description are what the ranking system and the human both read first. "
        "You never write clickbait that the video cannot pay off — a bounced "
        "viewer costs more than a lost click. Always return valid JSON only."
    )

    def __init__(self):
        self._or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        self._use_or = bool(self._or_key)
        self._hermes = os.environ.get("HERMES_MODEL", "nousresearch/hermes-4-70b").strip()
        self._oai = None
        self._anthropic = None

    # ── provider-agnostic completion (mirrors ContentGenerator._complete) ────
    async def _complete(self, prompt: str, max_tokens: int = 1200) -> str:
        if self._use_or:
            if self._oai is None:
                from openai import AsyncOpenAI
                self._oai = AsyncOpenAI(
                    api_key=self._or_key, base_url="https://openrouter.ai/api/v1"
                )
            r = await self._oai.chat.completions.create(
                model=self._hermes,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            )
            text = r.choices[0].message.content or ""
        else:
            if self._anthropic is None:
                import anthropic
                self._anthropic = anthropic.AsyncAnthropic(
                    api_key=settings.anthropic_api_key
                )
            r = await self._anthropic.messages.create(
                model=settings.content_text_model,
                max_tokens=max_tokens,
                system=self.SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = r.content[0].text
        return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()

    def _prompt(
        self,
        *,
        brand,
        topic: str,
        body: str,
        duration: Optional[int],
        keywords: list[str],
    ) -> str:
        dur = (
            f"\nVideo length: {duration} seconds."
            f" {'This is a SHORT — the title must land in under 45 characters and there are NO chapters.' if duration and duration <= 60 else 'Long-form — chapters are expected.'}"
            if duration
            else ""
        )
        seed = f"\nSeed keywords the brand cares about: {', '.join(keywords)}" if keywords else ""
        return f"""Write the YouTube discovery package for this video.

BRAND: {brand.name}
Tone: {brand.tone}
Personality: {brand.personality}
Audience: {brand.audience}
Content pillars: {', '.join(brand.content_pillars) or 'n/a'}
Never do this: {', '.join(brand.avoid) or 'n/a'}

VIDEO TOPIC: {topic}
WHAT HAPPENS IN IT: {body or topic}{dur}{seed}

Rules you must follow exactly:
1. TITLE: <= {TITLE_TARGET} characters. Lead with the phrase a human would
   actually TYPE INTO SEARCH to find this. Curiosity comes after the keyword,
   never before it. No ALL CAPS words, at most one "|" or "-" separator, no
   emoji spam (one is the maximum, and only if it earns its place).
2. DESCRIPTION: the FIRST sentence must restate the search phrase naturally and
   stand alone as a compelling snippet in under {SNIPPET_CHARS} characters.
   Then 2-4 short paragraphs of genuinely useful context. Write for a human who
   is deciding whether to keep watching, not for a crawler.
3. TAGS: 12-18 tags. Mix (a) the exact search phrase, (b) close variants people
   mistype or phrase differently, (c) the broad category, (d) brand terms.
   Every tag under {TAG_MAX_LEN} characters.
4. CHAPTERS: only if the video is longer than 120 seconds. First chapter MUST
   be time_seconds 0. At least 3, spaced at least 10 seconds apart. Label them
   with what a viewer would SKIP TO, not generic "Part 1".
5. SEARCH_PHRASE: the single query you optimised the whole package for.

Return ONLY this JSON, no prose around it:
{{
  "title": "...",
  "description": "...",
  "tags": ["...", "..."],
  "chapters": [{{"time_seconds": 0, "label": "..."}}],
  "search_phrase": "..."
}}"""

    def _heuristic(self, *, brand, topic: str, body: str) -> dict:
        """Deterministic fallback. Never as good as the model, always valid.

        This exists because the alternative — failing the upload because an SEO
        model was rate-limited — is strictly worse than shipping decent
        metadata. Discovery is an optimisation; publishing is the job.
        """
        title = sanitize_title(topic or brand.name)
        first = (body or topic or brand.name).strip().split("\n")[0][:SNIPPET_CHARS]
        desc = f"{first}\n\n{body or ''}".strip()
        tags = sanitize_tags(
            [brand.name, *brand.content_pillars, *[h.lstrip("#") for h in brand.hashtags]]
        )
        return {
            "title": title,
            "description": sanitize_description(desc),
            "tags": tags,
            "chapters_text": "",
            "search_phrase": topic or brand.name,
            "generated_by": "heuristic",
        }

    async def generate(
        self,
        *,
        project_slug: str = "dirco",
        topic: str,
        body: str = "",
        duration: Optional[int] = None,
        keywords: Optional[list[str]] = None,
        link: Optional[str] = None,
    ) -> dict:
        """Produce API-ready YouTube metadata. Never raises."""
        brand = load_brand_voice(project_slug)

        try:
            raw = await self._complete(
                self._prompt(
                    brand=brand,
                    topic=topic,
                    body=body,
                    duration=duration,
                    keywords=keywords or [],
                )
            )
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                raise ValueError("no JSON in SEO model response")
            data = json.loads(match.group())
            generated_by = "hermes" if self._use_or else settings.content_text_model
        except Exception as exc:  # noqa: BLE001 — degrade, never block the upload
            out = self._heuristic(brand=brand, topic=topic, body=body)
            out["seo_error"] = str(exc)[:200]
            return self._finalize(out, brand=brand, link=link)

        chapters_text = (
            format_chapters(data.get("chapters")) if not duration or duration > 120 else ""
        )
        out = {
            "title": sanitize_title(data.get("title"), fallback=topic or brand.name),
            "description": sanitize_description(data.get("description") or body or topic),
            "tags": sanitize_tags(data.get("tags")),
            "chapters_text": chapters_text,
            "search_phrase": str(data.get("search_phrase") or topic)[:120],
            "generated_by": generated_by,
        }
        return self._finalize(out, brand=brand, link=link)

    def _finalize(self, out: dict, *, brand, link: Optional[str]) -> dict:
        """Assemble the final description: snippet → body → chapters → links.

        Order is deliberate. The snippet must survive truncation, chapters must
        sit above the link block (YouTube parses timestamps anywhere, but humans
        scan top-down), and hashtags go last where YouTube renders the first
        three above the title.
        """
        parts = [out["description"].strip()]
        if out.get("chapters_text"):
            parts.append("Chapters:\n" + out["chapters_text"])
        if link:
            parts.append(link.strip())
        tail = " ".join(
            h if h.startswith("#") else f"#{h}" for h in (brand.hashtags or [])[:3]
        )
        if tail:
            parts.append(tail)
        out["description"] = sanitize_description("\n\n".join(p for p in parts if p))
        out["title_length"] = len(out["title"])
        out["tags_chars"] = sum(len(t) + 1 for t in out["tags"])
        return out
