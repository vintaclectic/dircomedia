import asyncio

import httpx
from app.config import settings


class TwitterClient:
    BASE_URL = "https://api.twitter.com/2"

    def __init__(self, user_token: str | None = None):
        """`user_token` is an OAuth 2.0 user access token from the connection
        wizard's credential vault. When present it takes PRECEDENCE over the
        .env OAuth 1.0a key set and the client signs with `Bearer <token>`
        instead of an HMAC-SHA1 signature.

        Why the switch is load-bearing (YH9AE4D, 2026-08-12): the wizard mints
        OAuth 2.0 user-context tokens, but .env carries OAuth 1.0a consumer
        keys. These are NOT interchangeable — signing an OAuth 2.0 token as if
        it were 1.0a produces a signature X rejects with a 401 that reads like
        "bad credentials", sending you to rotate keys that were never wrong.
        A vault connection that the poster couldn't see would show green on the
        health rail and still never post: the exact silent-rot failure the
        wizard exists to end.
        """
        self.user_token = user_token
        self.bearer_token = settings.twitter_bearer_token
        self.api_key = settings.twitter_api_key
        self.api_secret = settings.twitter_api_secret
        self.access_token = settings.twitter_access_token
        self.access_secret = settings.twitter_access_secret

    @classmethod
    async def from_vault(cls) -> "TwitterClient":
        """Build a client from the wizard's stored token, falling back to .env.

        Never raises: if the vault is empty, unreadable, or the key is missing,
        the caller still gets a working .env-backed client. Degrading to the
        previous behaviour is always better than taking the poster down.
        """
        try:
            from app.database import AsyncSessionLocal
            from app.services.oauth import store

            async with AsyncSessionLocal() as db:
                token = await store.get_access_token(db, "twitter")
            if token:
                return cls(user_token=token)
        except Exception:
            pass
        return cls()

    @property
    def credential_source(self) -> str:
        """'oauth_wizard' | 'env' — surfaced in post results so a failure names
        which credential set was actually used."""
        return "oauth_wizard" if self.user_token else "env"

    def _oauth_headers(
        self, method: str, url: str, params: dict = None, json_body: bool = True
    ) -> dict:
        """Generate OAuth 1.0a headers for user-context endpoints.

        `params` MUST include every form-encoded field and query param of the
        request — OAuth 1.0a folds them into the signature base string, so
        omitting them produces a signature the server computes differently and
        rejects with 401. Only a JSON body is excluded from the base string.

        `json_body=False` is for form-encoded requests (the v1.1 media upload):
        it drops the JSON Content-Type so httpx can set the correct
        multipart/urlencoded type with its boundary.
        """
        import time, hashlib, hmac, base64, urllib.parse, secrets

        # Vault (OAuth 2.0 user context) wins over .env (OAuth 1.0a). Bearer
        # auth signs nothing, so we return early before building a base string.
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            if json_body:
                headers["Content-Type"] = "application/json"
            return headers

        def encode(s: str) -> str:
            return urllib.parse.quote(str(s), safe="")

        oauth_params = {
            "oauth_consumer_key": self.api_key,
            "oauth_nonce": secrets.token_hex(16),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.access_token,
            "oauth_version": "1.0",
        }

        # Combine oauth params + any extra query params for signature base
        all_params = {**oauth_params, **(params or {})}
        sorted_params = "&".join(
            f"{encode(k)}={encode(v)}"
            for k, v in sorted(all_params.items())
        )
        base_string = f"{method.upper()}&{encode(url)}&{encode(sorted_params)}"
        signing_key = f"{encode(self.api_secret)}&{encode(self.access_secret)}"

        signature = base64.b64encode(
            hmac.new(
                signing_key.encode("ascii"),
                base_string.encode("ascii"),
                hashlib.sha1,
            ).digest()
        ).decode()

        oauth_params["oauth_signature"] = signature

        auth_header = "OAuth " + ", ".join(
            f'{k}="{encode(v)}"'
            for k, v in sorted(oauth_params.items())
        )
        headers = {"Authorization": auth_header}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def verify_credentials(self) -> dict:
        """Confirm the OAuth 1.0a user context is live and return the account.

        This is the rail's proof-of-life: it answers *which account will post*
        before anything is published, so a misconfigured key set fails loudly
        here instead of silently posting nowhere.
        """
        url = f"{self.BASE_URL}/users/me"
        params = {"user.fields": "public_metrics,created_at"}
        headers = self._oauth_headers("GET", url, params=params)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json().get("data", {})

    async def post_tweet(self, text: str, media_ids: list[str] = None) -> dict:
        url = f"{self.BASE_URL}/tweets"
        payload = {"text": text[:280]}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        headers = self._oauth_headers("POST", url)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def delete_tweet(self, tweet_id: str) -> dict:
        """Delete a tweet by id (v2 DELETE /2/tweets/:id). Used to pull a post that
        went out with bad copy (Vinta 2026-08-07 — a metadata leak leaked into a
        live tweet). OAuth 1.0a user context, same signing as post_tweet."""
        url = f"{self.BASE_URL}/tweets/{tweet_id}"
        headers = self._oauth_headers("DELETE", url)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def tweet_metrics(self, tweet_ids: list[str]) -> dict:
        """Fetch public engagement for up to 100 tweets (v2 GET /2/tweets?ids=...).
        Returns {tweet_id: {like_count, reply_count, retweet_count, quote_count,
        impression_count}}. Powers the drip's learn-and-adapt cadence
        (Vinta 2026-08-11: 'learn how best they work, use stats'). App-only bearer
        auth is fine for public_metrics; non_public (impressions) needs user-context,
        so we sign with OAuth 1.0a to get impressions when the account owns the tweet."""
        if not tweet_ids:
            return {}
        out = {}
        for i in range(0, len(tweet_ids), 100):
            batch = tweet_ids[i:i + 100]
            url = f"{self.BASE_URL}/tweets"
            params = {"ids": ",".join(batch),
                      "tweet.fields": "public_metrics,non_public_metrics,created_at"}
            headers = self._oauth_headers("GET", url, params=params)
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(url, headers=headers, params=params)
                if r.status_code != 200:
                    # fall back to public_metrics only (bearer) if non_public denied
                    params.pop("tweet.fields", None)
                    params["tweet.fields"] = "public_metrics,created_at"
                    r = await client.get(url, headers={"Authorization": f"Bearer {self.bearer_token}"}, params=params)
                    if r.status_code != 200:
                        continue
                for t in (r.json().get("data") or []):
                    pm = t.get("public_metrics", {}) or {}
                    nm = t.get("non_public_metrics", {}) or {}
                    out[t["id"]] = {
                        "like_count": pm.get("like_count", 0),
                        "reply_count": pm.get("reply_count", 0),
                        "retweet_count": pm.get("retweet_count", 0),
                        "quote_count": pm.get("quote_count", 0),
                        "impression_count": nm.get("impression_count", pm.get("impression_count", 0)),
                        "created_at": t.get("created_at"),
                    }
        return out

    async def upload_media(self, file_path: str, media_type: str = "video/mp4") -> str:
        """Upload media and return media_id."""
        # Uses v1.1 media upload (chunked for video)
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        import os, base64

        file_size = os.path.getsize(file_path)

        async with httpx.AsyncClient(timeout=300) as client:
            # INIT — form params are part of the signature base string.
            init_data = {
                "command": "INIT",
                "total_bytes": str(file_size),
                "media_type": media_type,
                "media_category": "tweet_video" if "video" in media_type else "tweet_image",
            }
            init_resp = await client.post(
                upload_url,
                headers=self._oauth_headers(
                    "POST", upload_url, params=init_data, json_body=False
                ),
                data=init_data,
            )
            init_resp.raise_for_status()
            media_id = init_resp.json()["media_id_string"]

            # APPEND chunks. The binary `media` part is multipart and is NOT
            # signed; only the accompanying form fields are.
            chunk_size = 4 * 1024 * 1024
            segment = 0
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    append_data = {
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": str(segment),
                    }
                    append_resp = await client.post(
                        upload_url,
                        headers=self._oauth_headers(
                            "POST", upload_url, json_body=False
                        ),
                        data=append_data,
                        files={"media": chunk},
                    )
                    append_resp.raise_for_status()
                    segment += 1

            # FINALIZE
            final_data = {"command": "FINALIZE", "media_id": media_id}
            final_resp = await client.post(
                upload_url,
                headers=self._oauth_headers(
                    "POST", upload_url, params=final_data, json_body=False
                ),
                data=final_data,
            )
            final_resp.raise_for_status()

            # Video transcodes asynchronously; attaching the id too early makes
            # the tweet fail. Wait for STATE=succeeded before returning.
            info = final_resp.json().get("processing_info")
            while info and info.get("state") in ("pending", "in_progress"):
                await asyncio.sleep(int(info.get("check_after_secs", 5)))
                status_params = {"command": "STATUS", "media_id": media_id}
                status_resp = await client.get(
                    upload_url,
                    headers=self._oauth_headers(
                        "GET", upload_url, params=status_params, json_body=False
                    ),
                    params=status_params,
                )
                status_resp.raise_for_status()
                info = status_resp.json().get("processing_info")
                if info and info.get("state") == "failed":
                    raise RuntimeError(f"X media processing failed: {info.get('error')}")

            return media_id
