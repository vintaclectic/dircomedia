from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.analytics import AnalyticsSnapshot


class StrategyAnalyzer:
    async def analyze(self, project_slug: str, snapshots: list) -> dict:
        if not snapshots:
            return self._default_strategy(project_slug)

        platform_stats = defaultdict(lambda: {"impressions": 0, "engagement": 0, "count": 0})
        for s in snapshots:
            p = s.platform
            platform_stats[p]["impressions"] += s.impressions
            platform_stats[p]["engagement"] += s.engagement_rate
            platform_stats[p]["count"] += 1

        # Best platform by engagement rate
        best_platforms = sorted(
            platform_stats.keys(),
            key=lambda p: platform_stats[p]["engagement"] / max(platform_stats[p]["count"], 1),
            reverse=True,
        )

        total_engagement = sum(
            platform_stats[p]["engagement"] / max(platform_stats[p]["count"], 1)
            for p in platform_stats
        )
        avg_engagement = total_engagement / max(len(platform_stats), 1)

        insights = self._build_insights(project_slug, platform_stats, best_platforms, avg_engagement)

        return {
            "insights": insights,
            "recommended_content_types": self._recommend_content_types(project_slug, platform_stats),
            "recommended_posting_times": self._recommend_posting_times(best_platforms),
            "best_platforms": best_platforms[:3],
        }

    def _build_insights(self, project_slug, platform_stats, best_platforms, avg_engagement) -> list[str]:
        insights = []
        if best_platforms:
            insights.append(f"Highest engagement on {best_platforms[0]} — prioritize this platform")
        if avg_engagement < 2.0:
            insights.append("Engagement below 2% — try more visual content (video/reels)")
        elif avg_engagement > 5.0:
            insights.append("Strong engagement — increase posting frequency")
        if len(platform_stats) < 3:
            insights.append("Expand to more platforms to increase reach")
        return insights

    def _recommend_content_types(self, project_slug: str, platform_stats: dict) -> list[str]:
        project_types = {
            "dirhaven-rp": ["video", "reel", "image"],
            "dirmegle": ["image", "text", "reel"],
            "medaled": ["image", "reel", "text"],
            "agentis": ["text", "image", "video"],
            "vintinuum": ["video", "image", "text"],
            "dirco": ["text", "image", "video"],
            "dirhaven-app": ["reel", "image", "text"],
        }
        base = project_types.get(project_slug, ["text", "image", "video"])
        if "instagram" in platform_stats or "tiktok" in platform_stats:
            if "reel" not in base:
                base.insert(0, "reel")
        return base

    def _recommend_posting_times(self, platforms: list[str]) -> dict:
        times = {}
        if "twitter" in platforms:
            times["twitter"] = ["09:00", "12:00", "17:00", "20:00"]
        if "instagram" in platforms:
            times["instagram"] = ["08:00", "12:00", "19:00"]
        if "tiktok" in platforms:
            times["tiktok"] = ["07:00", "12:00", "19:00", "21:00"]
        if "reddit" in platforms:
            times["reddit"] = ["10:00", "14:00", "20:00"]
        return times

    def _default_strategy(self, project_slug: str) -> dict:
        return {
            "insights": ["No data yet — start posting to gather insights"],
            "recommended_content_types": ["text", "image", "video"],
            "recommended_posting_times": {
                "twitter": ["09:00", "17:00"],
                "instagram": ["12:00", "19:00"],
                "tiktok": ["19:00", "21:00"],
            },
            "best_platforms": ["instagram", "tiktok", "twitter"],
        }
