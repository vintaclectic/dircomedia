import time

import httpx
from app.config import settings


class RedditClient:
    """Reddit poster.

    Auth priority (Vinta directive 2026-07-18 — 'no password ever'):
      1. refresh_token  → grant_type=refresh_token  (3-legged OAuth; works for
         Google-login accounts that have NO password). Mint the refresh token
         once via scripts/reddit_oauth.py, store as REDDIT_REFRESH_TOKEN.
      2. password        → grant_type=password       (legacy fallback only; needs
         a real Reddit password, which Google-OAuth accounts do not have).

    Access tokens are cached with their expiry so we refresh only when needed
    instead of on every post.
    """

    BASE_URL = "https://oauth.reddit.com"
    AUTH_URL = "https://www.reddit.com/api/v1/access_token"

    def __init__(self):
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self.username = settings.reddit_username
        self.password = settings.reddit_password
        self.refresh_token = settings.reddit_refresh_token
        self.user_agent = settings.reddit_user_agent
        self.reddit_redirect_uri_hint = settings.reddit_redirect_uri
        self._access_token: str = ""
        self._token_expiry: float = 0.0  # epoch seconds; 0 = none

    def _auth_data(self) -> dict:
        """Choose the OAuth grant based on what's configured. Refresh-token
        first (no password), password only as a legacy fallback."""
        if self.refresh_token:
            return {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        if self.username and self.password:
            return {
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
        raise RuntimeError(
            "Reddit not configured: set REDDIT_REFRESH_TOKEN (preferred — run "
            "scripts/reddit_oauth.py) or REDDIT_USERNAME+REDDIT_PASSWORD (legacy)."
        )

    async def _get_access_token(self) -> str:
        # Reuse the cached token until ~60s before it expires.
        if self._access_token and time.time() < (self._token_expiry - 60):
            return self._access_token
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.AUTH_URL,
                auth=(self.client_id, self.client_secret),
                data=self._auth_data(),
                headers={"User-Agent": self.user_agent},
            )
            if response.status_code == 401:
                # Verified 2026-08-06: this account's app returns 401 for EVERY
                # grant type, including client_credentials — which needs no user
                # and no password. That isolates the fault to the app
                # credentials themselves, not 2FA and not the password.
                #
                # CORRECTION (2026-08-07, third pass): the previous message said
                # Reddit was "permanently closed." That overstated it and was
                # wrong in the way that matters. Two separate things had been
                # collapsed into one:
                #
                #   1. The PROGRAMMATIC API. Reddit ended self-service access in
                #      Nov 2025. prefs/apps still hands out an id/secret in ~5
                #      min, but registration is no longer access — new creds must
                #      clear a manual "Responsible Builder" review (no SLA, small
                #      projects often rejected). Gated and slow: NOT closed.
                #      There is a real application path, and an approved app gets
                #      a genuine free tier (100 QPM, non-commercial).
                #
                #   2. Reddit as a DISTRIBUTION CHANNEL. Never restricted at all.
                #      The Responsible Builder Policy governs API tokens, not
                #      people. Posting to subreddits from Vinta's own account in
                #      a browser needs no app, no token, and no approval, and is
                #      the highest-traffic rail available to this funnel today.
                #
                # So: this 401 blocks AUTOMATED posting only. It does not block
                # reaching Reddit. Never again report "Reddit is closed to us."
                raise RuntimeError(
                    "Reddit rejected the app credentials (401 on every grant, "
                    "including client_credentials, which needs no user and no "
                    "password). REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET are "
                    "invalid, revoked, or belong to a deleted app — this is NOT "
                    "a 2FA or password problem, and NO code change fixes it.\n"
                    "SCOPE OF THIS FAILURE: it blocks AUTOMATED posting only. "
                    "Reddit is NOT closed to us. Posting manually from your own "
                    "account requires no API, no app, and no approval — that "
                    "rail is open right now and is the fastest one available.\n"
                    "TO RESTORE AUTOMATION: Reddit ended self-service API keys "
                    "under its Nov-2025 Responsible Builder policy, so "
                    "registering at prefs/apps yields an id/secret instantly "
                    "but grants nothing until it clears manual review. That "
                    "review is gated and has no SLA (days to weeks, small "
                    "projects are often rejected), so treat it as a background "
                    "bet, never a dependency for anything time-sensitive.\n"
                    "Do not retry this call in a loop; it will keep returning "
                    "401 until an approved app exists."
                )
            response.raise_for_status()
            body = response.json()
            self._access_token = body["access_token"]
            self._token_expiry = time.time() + int(body.get("expires_in", 3600))
        return self._access_token

    async def _headers(self) -> dict:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.user_agent,
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
