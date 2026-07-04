"""
Feedback loop: uses analytics insights to adjust content generation parameters.
Called periodically to update brand config weighting based on performance.
"""
from app.services.analytics.analyzer import StrategyAnalyzer


class FeedbackLoop:
    def __init__(self):
        self.analyzer = StrategyAnalyzer()

    async def get_adjusted_params(
        self, project_slug: str, snapshots: list
    ) -> dict:
        """Return adjusted generation params based on performance data."""
        strategy = await self.analyzer.analyze(project_slug, snapshots)

        return {
            "preferred_content_types": strategy["recommended_content_types"],
            "target_platforms": strategy["best_platforms"],
            "posting_schedule": strategy["recommended_posting_times"],
            "strategy_notes": strategy["insights"],
        }

    async def should_generate_more_video(self, project_slug: str, snapshots: list) -> bool:
        if not snapshots:
            return False
        video_snapshots = [s for s in snapshots if getattr(s, "platform", "") in ("tiktok", "instagram")]
        if not video_snapshots:
            return False
        avg_video_engagement = sum(s.engagement_rate for s in video_snapshots) / len(video_snapshots)
        return avg_video_engagement > 3.0
