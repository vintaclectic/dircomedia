"""
The OAuth flow engine (YH9AE4D) — one implementation, five platforms.

Everything that varies per platform lives in providers.py; this module is the
mechanism: build authorize URL → exchange code → look up identity → refresh.

NOTHING IN HERE LOGS A TOKEN. Error paths deliberately truncate provider
response bodies to 300 chars and are only ever surfaced from endpoints that
already require the owner token — but even then, token-bearing fields are
stripped before an error is stored or returned.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any, Optional

import httpx

from app.services.oauth.providers import (
    OAuthProvider, get_provider, credentials_for,
)

TIMEOUT = 25


class OAuthError(RuntimeError):
    """A provider-side failure worth showing Vinta (never contains a token)."""


# ── PKCE ─────────────────────────────────────────────────────────────────────

def make_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) — S256."""
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


# ── authorize ────────────────────────────────────────────────────────────────

def build_authorize_url(
    provider: OAuthProvider, *, client_id: str, redirect_uri: str,
    state: str, code_challenge: Optional[str] = None,
) -> str:
    from urllib.parse import urlencode

    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": " ".join(provider.scopes),
        **provider.extra_authorize_params,
    }
    if provider.uses_pkce and code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    # TikTok is the one provider that names the app credential `client_key`
    # instead of `client_id` on the authorize step.
    if provider.key == "tiktok":
        params["client_key"] = params.pop("client_id")
    return f"{provider.authorize_url}?{urlencode(params)}"


# ── token exchange / refresh ─────────────────────────────────────────────────

def _auth_and_body(provider: OAuthProvider, data: dict) -> tuple[Optional[tuple], dict]:
    """Split credentials between HTTP Basic and the form body per provider."""
    cid, csec = credentials_for(provider.key)
    if provider.client_auth == "basic":
        return (cid, csec), data
    body = dict(data)
    if provider.key == "tiktok":
        body["client_key"] = cid
    else:
        body["client_id"] = cid
    body["client_secret"] = csec
    return None, body


def _scrub(text: str) -> str:
    """Strip anything token-shaped out of a provider error before it's stored."""
    out = text[:300]
    for marker in ("access_token", "refresh_token", "code="):
        if marker in out:
            out = out.split(marker)[0] + f"<{marker} redacted>"
    return out


async def exchange_code(
    provider: OAuthProvider, *, code: str, redirect_uri: str,
    code_verifier: Optional[str] = None,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if provider.uses_pkce and code_verifier:
        data["code_verifier"] = code_verifier

    auth, body = _auth_and_body(provider, data)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if provider.key == "reddit":
        from app.config import settings as cfg
        headers["User-Agent"] = cfg.reddit_user_agent

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(provider.token_url, data=body, auth=auth, headers=headers)
    if r.status_code != 200:
        raise OAuthError(f"{provider.label} token exchange failed (HTTP {r.status_code}): {_scrub(r.text)}")

    payload = r.json()
    # TikTok nests older responses under `data`; v2 returns flat. Handle both.
    if "access_token" not in payload and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not payload.get("access_token"):
        raise OAuthError(f"{provider.label} returned no access token: {_scrub(str(payload))}")
    return payload


async def refresh_token(provider: OAuthProvider, *, refresh: str) -> dict[str, Any]:
    """Exchange a refresh token for a fresh access token.

    Instagram has no refresh_token at all — a still-valid long-lived token is
    re-exchanged for a new 60-day one. That asymmetry is handled here so the
    worker doesn't have to know about it.
    """
    if provider.key == "instagram":
        cid, csec = credentials_for("instagram")
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://graph.facebook.com/v21.0/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": cid,
                    "client_secret": csec,
                    "fb_exchange_token": refresh,  # the CURRENT access token
                },
            )
        if r.status_code != 200:
            raise OAuthError(f"Instagram token re-exchange failed (HTTP {r.status_code}): {_scrub(r.text)}")
        return r.json()

    data = {"grant_type": "refresh_token", "refresh_token": refresh}
    auth, body = _auth_and_body(provider, data)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if provider.key == "reddit":
        from app.config import settings as cfg
        headers["User-Agent"] = cfg.reddit_user_agent

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(provider.token_url, data=body, auth=auth, headers=headers)
    if r.status_code != 200:
        raise OAuthError(f"{provider.label} refresh failed (HTTP {r.status_code}): {_scrub(r.text)}")
    payload = r.json()
    if "access_token" not in payload and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not payload.get("access_token"):
        raise OAuthError(f"{provider.label} refresh returned no access token.")
    return payload


# ── identity ─────────────────────────────────────────────────────────────────

def _dig(obj: Any, path: list[str]) -> Optional[str]:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return str(cur) if cur is not None else None


async def fetch_identity(provider: OAuthProvider, access_token: str) -> tuple[str, Optional[str]]:
    """(account_id, account_name). Returns ('', None) if the probe fails — a
    connection with an unknown handle is still a working connection, and failing
    the whole flow over a cosmetic lookup would be the wrong trade."""
    if not provider.identity_url:
        return "", None
    try:
        headers, params = {}, {}
        if provider.identity_auth == "query":
            params["access_token"] = access_token
            params["fields"] = "id,name"
        else:
            headers["Authorization"] = f"Bearer {access_token}"
        if provider.key == "reddit":
            from app.config import settings as cfg
            headers["User-Agent"] = cfg.reddit_user_agent

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(provider.identity_url, headers=headers, params=params)
        if r.status_code != 200:
            return "", None
        body = r.json()
        return (_dig(body, provider.identity_id_path) or ""), _dig(body, provider.identity_name_path)
    except Exception:
        return "", None


async def probe_token(provider: OAuthProvider, access_token: str) -> tuple[bool, Optional[str]]:
    """Cheap liveness check: (ok, error). Used by the health rail and by
    'Test Connection' after a manual paste — the moment of truth that turns a
    pasted string into a verified connection."""
    if not provider.identity_url:
        return True, None
    try:
        headers, params = {}, {}
        if provider.identity_auth == "query":
            params["access_token"] = access_token
        else:
            headers["Authorization"] = f"Bearer {access_token}"
        if provider.key == "reddit":
            from app.config import settings as cfg
            headers["User-Agent"] = cfg.reddit_user_agent

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(provider.identity_url, headers=headers, params=params)
        if r.status_code == 200:
            return True, None
        return False, f"HTTP {r.status_code}: {_scrub(r.text)}"
    except Exception as e:
        return False, f"{e.__class__.__name__}: {str(e)[:160]}"


def expires_at_from(payload: dict) -> Optional[int]:
    """Normalize every provider's expiry dialect into one Unix timestamp."""
    for key in ("expires_in", "expires_in_seconds"):
        if payload.get(key):
            try:
                return int(time.time()) + int(payload[key])
            except (TypeError, ValueError):
                pass
    return None
