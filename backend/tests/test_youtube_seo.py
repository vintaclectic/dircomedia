"""
YouTube SEO + upload-metadata regression tests (task TA3SQSM).

These lock down the properties that cause a SILENT, expensive failure: the
YouTube Data API rejects the entire videos.insert call when a title exceeds
100 chars or the SUM of tag lengths exceeds 500. A model that gets generous
with tags would otherwise kill an upload that already burned bandwidth — and
the error surfaces as an opaque 400 long after the model call is forgotten.

Also locked: the heuristic degrade path. If the SEO model is down (Anthropic
credits, OpenRouter outage), we must still emit VALID metadata and publish —
discovery is an optimisation, publishing is the job.
"""
import pytest

from app.services.content_engine.youtube_seo import (
    TAGS_CHAR_BUDGET,
    TITLE_MAX,
    YouTubeSEO,
    format_chapters,
    sanitize_description,
    sanitize_tags,
    sanitize_title,
)


class TestSanitizeTitle:
    def test_never_exceeds_api_limit(self):
        assert len(sanitize_title("x" * 500)) <= TITLE_MAX

    def test_truncates_on_word_boundary_not_mid_word(self):
        title = sanitize_title(("supercalifragilistic " * 20).strip())
        assert not title.endswith("supercalifragilisti")
        assert len(title) <= TITLE_MAX

    def test_strips_angle_brackets_the_api_rejects(self):
        assert "<" not in sanitize_title("a <script> b")
        assert ">" not in sanitize_title("a <script> b")

    def test_empty_falls_back_never_returns_blank(self):
        assert sanitize_title("") == "DirCo update"
        assert sanitize_title(None, fallback="Fallback") == "Fallback"

    def test_collapses_newlines_and_whitespace(self):
        assert sanitize_title("a\n\nb   c") == "a b c"

    def test_does_not_leave_dangling_separator(self):
        assert not sanitize_title(("word " * 30) + "|").endswith("|")


class TestSanitizeTags:
    def test_respects_aggregate_char_budget(self):
        tags = sanitize_tags([f"unique-tag-number-{i}" for i in range(200)])
        assert sum(len(t) + 1 for t in tags) <= TAGS_CHAR_BUDGET

    def test_dedupes_case_insensitively(self):
        assert sanitize_tags(["FiveM", "fivem", "FIVEM"]) == ["FiveM"]

    def test_drops_commas_that_would_split_tags(self):
        assert all("," not in t for t in sanitize_tags(["a,b", "c"]))

    def test_preserves_priority_order(self):
        """Earliest tags are the highest-value ones — they must survive."""
        tags = sanitize_tags(["primary keyword"] + [f"filler-{i}" * 3 for i in range(100)])
        assert tags[0] == "primary keyword"

    def test_handles_none_and_empty(self):
        assert sanitize_tags(None) == []
        assert sanitize_tags(["", "   "]) == []


class TestFormatChapters:
    def test_requires_at_least_three_to_activate(self):
        assert format_chapters([{"time_seconds": 0, "label": "Only"}]) == ""

    def test_forces_first_chapter_to_zero(self):
        out = format_chapters(
            [
                {"time_seconds": 30, "label": "A"},
                {"time_seconds": 60, "label": "B"},
                {"time_seconds": 90, "label": "C"},
            ]
        )
        assert out.startswith("00:00 ")

    def test_drops_chapters_closer_than_ten_seconds(self):
        """YouTube silently refuses chapters spaced <10s — emit none instead."""
        out = format_chapters(
            [
                {"time_seconds": 0, "label": "A"},
                {"time_seconds": 3, "label": "B"},
                {"time_seconds": 6, "label": "C"},
            ]
        )
        assert out == ""

    def test_renders_hours_when_long(self):
        out = format_chapters(
            [
                {"time_seconds": 0, "label": "A"},
                {"time_seconds": 60, "label": "B"},
                {"time_seconds": 3700, "label": "C"},
            ]
        )
        assert "1:01:40 C" in out

    def test_empty_input_is_safe(self):
        assert format_chapters(None) == ""
        assert format_chapters([]) == ""


class TestDescription:
    def test_never_exceeds_api_limit(self):
        assert len(sanitize_description("y" * 9000)) <= 5000


@pytest.mark.asyncio
class TestDegradePath:
    async def test_model_failure_still_yields_valid_metadata(self, monkeypatch):
        """A dead SEO model must never block a publish."""
        seo = YouTubeSEO()

        async def boom(*a, **k):
            raise RuntimeError("model offline")

        monkeypatch.setattr(seo, "_complete", boom)
        out = await seo.generate(
            project_slug="dirco",
            topic="Test topic that is genuinely useful",
            body="Body text",
        )
        assert out["generated_by"] == "heuristic"
        assert out["seo_error"]
        assert out["title"] and len(out["title"]) <= TITLE_MAX
        assert len(out["description"]) <= 5000
        assert sum(len(t) + 1 for t in out["tags"]) <= TAGS_CHAR_BUDGET

    async def test_malformed_model_json_degrades_cleanly(self, monkeypatch):
        seo = YouTubeSEO()

        async def garbage(*a, **k):
            return "I am not JSON at all."

        monkeypatch.setattr(seo, "_complete", garbage)
        out = await seo.generate(project_slug="dirco", topic="Topic", body="Body")
        assert out["generated_by"] == "heuristic"
        assert out["title"]

    async def test_oversized_model_output_is_clamped(self, monkeypatch):
        """The model can and will exceed limits — we clamp, never forward raw."""
        seo = YouTubeSEO()

        async def oversized(*a, **k):
            tags = ", ".join(f'"tag-{i}-long-keyword"' for i in range(200))
            return (
                '{"title": "' + "T" * 400 + '", "description": "' + "D" * 9000 + '",'
                ' "tags": [' + tags + '], "chapters": [], "search_phrase": "q"}'
            )

        monkeypatch.setattr(seo, "_complete", oversized)
        out = await seo.generate(project_slug="dirco", topic="Topic", body="Body")
        assert len(out["title"]) <= TITLE_MAX
        assert len(out["description"]) <= 5000
        assert sum(len(t) + 1 for t in out["tags"]) <= TAGS_CHAR_BUDGET
