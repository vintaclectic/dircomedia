import httpx
from app.config import settings


class AnalyticsCollector:
    async def collect_all(self, project_slug: str, project_id: str) -> list[dict]:
        """Collect analytics from all configured platforms."""
        snapshots = []

        try:
            twitter_data = await self._collect_twitter(project_id)
            snapshots.extend(twitter_data)
        except Exception:
            pass

        try:
            instagram_data = await self._collect_instagram(project_id)
            snapshots.extend(instagram_data)
        except Exception:
            pass

        return snapshots

    async def _collect_twitter(self, project_id: str) -> list[dict]:
        headers = {"Authorization": f"Bearer {settings.twitter_bearer_token}"}
        snapshots = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Get recent tweets and their metrics
            resp = await client.get(
                "https://api.twitter.com/2/users/me/tweets",
                headers=headers,
                params={
                    "tweet.fields": "public_metrics,created_at",
                    "max_results": 10,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for tweet in data.get("data", []):
                    metrics = tweet.get("public_metrics", {})
                    impressions = metrics.get("impression_count", 0)
                    likes = metrics.get("like_count", 0)
                    replies = metrics.get("reply_count", 0)
                    retweets = metrics.get("retweet_count", 0)
                    engagement = (likes + replies + retweets) / max(impressions, 1) * 100

                    snapshots.append({
                        "project_id": project_id,
                        "platform": "twitter",
                        "post_id": tweet["id"],
                        "impressions": impressions,
                        "likes": likes,
                        "comments": replies,
                        "shares": retweets,
                        "engagement_rate": engagement,
                        "raw_data": metrics,
                    })
        return snapshots

    async def _collect_instagram(self, project_id: str) -> list[dict]:
        snapshots = []
        access_token = settings.instagram_access_token

        async with httpx.AsyncClient(timeout=30) as client:
            # Get IG account media insights
            resp = await client.get(
                "https://graph.facebook.com/v19.0/me/media",
                params={
                    "fields": "id,timestamp,insights.metric(impressions,reach,likes,comments,shares,saved)",
                    "access_token": access_token,
                    "limit": 10,
                },
            )
            if resp.status_code == 200:
                for media in resp.json().get("data", []):
                    insights = {i["name"]: i["values"][0]["value"]
                                for i in media.get("insights", {}).get("data", [])}
                    impressions = insights.get("impressions", 0)
                    likes = insights.get("likes", 0)
                    comments = insights.get("comments", 0)
                    shares = insights.get("shares", 0)
                    saves = insights.get("saved", 0)
                    engagement = (likes + comments + shares + saves) / max(impressions, 1) * 100

                    snapshots.append({
                        "project_id": project_id,
                        "platform": "instagram",
                        "post_id": media["id"],
                        "impressions": impressions,
                        "reach": insights.get("reach", 0),
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "saves": saves,
                        "engagement_rate": engagement,
                        "raw_data": insights,
                    })
        return snapshots
