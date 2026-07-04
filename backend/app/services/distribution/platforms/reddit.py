import httpx
from app.config import settings


class RedditClient:
    BASE_URL = "https://oauth.reddit.com"
    AUTH_URL = "https://www.reddit.com/api/v1/access_token"

    def __init__(self):
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self.username = settings.reddit_username
        self.password = settings.reddit_password
        self._access_token: str = ""

    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.AUTH_URL,
                auth=(self.client_id, self.client_secret),
                data={
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                },
                headers={"User-Agent": "DirCoMedia/1.0"},
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
        return self._access_token

    async def _headers(self) -> dict:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": "DirCoMedia/1.0",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def submit_post(
        self,
        subreddit: str,
        title: str,
        text: str = None,
        url: str = None,
        flair_id: str = None,
    ) -> dict:
        """Submit a text or link post to a subreddit."""
        headers = await self._headers()
        payload = {
            "sr": subreddit,
            "title": title,
            "kind": "link" if url else "self",
            "resubmit": True,
            "nsfw": False,
            "spoiler": False,
        }
        if url:
            payload["url"] = url
        elif text:
            payload["text"] = text
        if flair_id:
            payload["flair_id"] = flair_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/submit",
                headers=headers,
                data=payload,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "post_id": data.get("json", {}).get("data", {}).get("id"),
                "url": data.get("json", {}).get("data", {}).get("url"),
            }

    async def submit_video(self, subreddit: str, title: str, video_url: str) -> dict:
        return await self.submit_post(subreddit=subreddit, title=title, url=video_url)
