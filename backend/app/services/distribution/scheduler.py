from datetime import datetime
from typing import Optional

from app.services.distribution.platforms.twitter import TwitterClient
from app.services.distribution.platforms.tiktok import TikTokClient
from app.services.distribution.platforms.instagram import InstagramClient
from app.services.distribution.platforms.reddit import RedditClient
from app.services.distribution.platforms.discord import DiscordClient
from app.services.distribution.platforms.telegram import TelegramClient
from app.services.distribution.platforms.youtube import YouTubeClient
from app.services.distribution.platforms.bluesky import BlueskyClient
from app.core.exceptions import DistributionError


class DistributionScheduler:
    def __init__(self):
        self.twitter = TwitterClient()
        self.tiktok = TikTokClient()
        self.instagram = InstagramClient()
        self.reddit = RedditClient()
        self.discord = DiscordClient()
        self.telegram = TelegramClient()
        self.youtube = YouTubeClient()
        self.bluesky = BlueskyClient()

    async def post(
        self,
        platforms: list[str],
        body: str,
        media_url: Optional[str] = None,
        content_type: str = "text",
        project_slug: str = "",
        subreddits: list[str] = None,
    ) -> dict[str, dict]:
        """Post content to all specified platforms. Returns results per platform."""
        results = {}

        # Re-bind X to the connection wizard's stored token, if one exists
        # (YH9AE4D, 2026-08-12). Done per-post rather than in __init__ because
        # __init__ is sync and the vault read is async — and because a token
        # refreshed or reconnected after this scheduler was constructed must
        # take effect on the very next post, not on the next process restart.
        # Falls back to the .env client on any failure.
        if "twitter" in platforms:
            self.twitter = await TwitterClient.from_vault()

        for platform in platforms:
            try:
                if platform == "twitter":
                    results["twitter"] = await self._post_twitter(body, media_url, content_type)
                elif platform == "tiktok":
                    results["tiktok"] = await self._post_tiktok(body, media_url)
                elif platform == "instagram":
                    results["instagram"] = await self._post_instagram(body, media_url, content_type)
                elif platform == "reddit":
                    results["reddit"] = await self._post_reddit(
                        body, media_url, project_slug, subreddits or []
                    )
                elif platform == "discord":
                    results["discord"] = await self.discord.post_message(
                        body, media_url=media_url, project_slug=project_slug
                    )
                elif platform == "telegram":
                    results["telegram"] = await self.telegram.post_message(body, media_url=media_url)
                elif platform == "bluesky":
                    results["bluesky"] = await self.bluesky.post_message(body, media_url=media_url)
                elif platform == "youtube":
                    if not media_url or content_type not in ("video", "reel"):
                        raise DistributionError("YouTube requires a video", "youtube")
                    title, _, rest = body.partition("\n\n")
                    results["youtube"] = await self.youtube.upload_video(
                        video_url=media_url, title=title or body[:100], description=rest or body
                    )
            except Exception as e:
                results[platform] = {"error": str(e), "status": "failed"}
        return results

    async def _post_twitter(self, text: str, media_url: Optional[str], content_type: str) -> dict:
        if media_url and content_type == "video":
            media_id = await self.twitter.upload_media(media_url, "video/mp4")
            return await self.twitter.post_tweet(text, media_ids=[media_id])
        return await self.twitter.post_tweet(text)

    async def _post_tiktok(self, caption: str, video_url: Optional[str]) -> dict:
        if not video_url:
            raise DistributionError("TikTok requires a video URL", "tiktok")
        return await self.tiktok.post_video(video_url, caption)

    async def _post_instagram(self, caption: str, media_url: Optional[str], content_type: str) -> dict:
        if not media_url:
            raise DistributionError("Instagram requires media", "instagram")
        if content_type in ("video", "reel"):
            return await self.instagram.post_reel(media_url, caption)
        return await self.instagram.post_image(media_url, caption)

    async def _post_reddit(
        self, text: str, media_url: Optional[str], project_slug: str, subreddits: list[str]
    ) -> dict:
        if not subreddits:
            # Default subreddits per project
            defaults = {
                "dirhaven-rp": ["FiveM", "GrandTheftAutoV"],
                "dirmegle": ["SocialNetworking"],
                "medaled": ["gaming"],
                "agentis": ["artificial", "MachineLearning"],
                "vintinuum": ["artificial", "singularity"],
            }
            subreddits = defaults.get(project_slug, ["test"])

        results = {}
        for sub in subreddits[:2]:  # Max 2 subreddits per post
            if media_url:
                results[sub] = await self.reddit.submit_video(sub, text[:300], media_url)
            else:
                results[sub] = await self.reddit.submit_post(sub, text[:300], text=text)
        return results
