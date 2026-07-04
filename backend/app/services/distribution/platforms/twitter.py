import httpx
from app.config import settings


class TwitterClient:
    BASE_URL = "https://api.twitter.com/2"

    def __init__(self):
        self.bearer_token = settings.twitter_bearer_token
        self.api_key = settings.twitter_api_key
        self.api_secret = settings.twitter_api_secret
        self.access_token = settings.twitter_access_token
        self.access_secret = settings.twitter_access_secret

    def _oauth_headers(self, method: str, url: str, params: dict = None) -> dict:
        """Generate OAuth 1.0a headers for user-context endpoints."""
        import time, hashlib, hmac, base64, urllib.parse, secrets

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
        return {"Authorization": auth_header, "Content-Type": "application/json"}

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

    async def upload_media(self, file_path: str, media_type: str = "video/mp4") -> str:
        """Upload media and return media_id."""
        # Uses v1.1 media upload (chunked for video)
        upload_url = "https://upload.twitter.com/1.1/media/upload.json"
        import os, base64

        file_size = os.path.getsize(file_path)
        headers = self._oauth_headers("POST", upload_url)

        async with httpx.AsyncClient(timeout=300) as client:
            # INIT
            init_resp = await client.post(
                upload_url,
                headers=headers,
                data={
                    "command": "INIT",
                    "total_bytes": file_size,
                    "media_type": media_type,
                    "media_category": "tweet_video" if "video" in media_type else "tweet_image",
                },
            )
            init_resp.raise_for_status()
            media_id = init_resp.json()["media_id_string"]

            # APPEND chunks
            chunk_size = 4 * 1024 * 1024
            segment = 0
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    await client.post(
                        upload_url,
                        headers=self._oauth_headers("POST", upload_url),
                        data={"command": "APPEND", "media_id": media_id, "segment_index": segment},
                        files={"media": chunk},
                    )
                    segment += 1

            # FINALIZE
            final_resp = await client.post(
                upload_url,
                headers=self._oauth_headers("POST", upload_url),
                data={"command": "FINALIZE", "media_id": media_id},
            )
            final_resp.raise_for_status()
            return media_id
