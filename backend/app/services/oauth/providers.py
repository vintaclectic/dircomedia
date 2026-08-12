"""
OAuth provider registry — one declarative spec per platform (YH9AE4D).

Every platform difference (PKCE or not, Basic auth or body auth, where the
account handle lives in the /me response, whether refresh tokens exist at all)
is data in this file, so the route layer in api/v1/oauth.py stays one flow
instead of five. Adding a sixth platform is a dict entry, not a new endpoint.

THE THREE THINGS THAT DIFFER PER PLATFORM, and why each matters:
  1. PKCE (X, TikTok, Pinterest-optional) — the code_verifier proves the caller
     that redeems the code is the caller that started the flow. Without it, a
     stolen authorization code is redeemable by anyone.
  2. Client auth style — X and Reddit want HTTP Basic; TikTok and Instagram want
     the secret in the form body. Sending the wrong one is a 401 that reads like
     bad credentials and costs an hour.
  3. Token lifetime — Instagram's long-lived token is 60 days and REFRESHES BY
     RE-EXCHANGE (no refresh_token exists); everyone else hands back a real
     refresh_token. The worker has to know which.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.config import settings


@dataclass(frozen=True)
class OAuthProvider:
    key: str                       # our canonical platform name
    label: str                     # human name for UI
    authorize_url: str
    token_url: str
    scopes: list[str]
    # 'oneclick' = full OAuth round trip from the dashboard.
    # 'manual'   = Vinta pastes a token he minted in the platform's own tool
    #              (Instagram/TikTok need app review or a FB Page link first).
    mode: str
    uses_pkce: bool = False
    client_auth: str = "body"      # 'basic' | 'body'
    # Where to look up the connected account after token exchange.
    identity_url: Optional[str] = None
    identity_id_path: list[str] = field(default_factory=list)
    identity_name_path: list[str] = field(default_factory=list)
    identity_auth: str = "bearer"  # 'bearer' | 'query'
    supports_refresh: bool = True
    extra_authorize_params: dict = field(default_factory=dict)
    docs_url: str = ""
    developer_portal: str = ""


def _client_id(platform: str) -> str:
    return {
        "twitter": settings.twitter_api_key,
        "reddit": settings.reddit_client_id,
        "instagram": settings.instagram_app_id,
        "tiktok": settings.tiktok_client_key,
        "pinterest": getattr(settings, "pinterest_app_id", ""),
    }.get(platform, "")


def _client_secret(platform: str) -> str:
    return {
        "twitter": settings.twitter_api_secret,
        "reddit": settings.reddit_client_secret,
        "instagram": settings.instagram_app_secret,
        "tiktok": settings.tiktok_client_secret,
        "pinterest": getattr(settings, "pinterest_app_secret", ""),
    }.get(platform, "")


PROVIDERS: dict[str, OAuthProvider] = {
    "twitter": OAuthProvider(
        key="twitter",
        label="X",
        authorize_url="https://twitter.com/i/oauth2/authorize",
        token_url="https://api.twitter.com/2/oauth2/token",
        scopes=["tweet.read", "tweet.write", "users.read", "offline.access"],
        mode="oneclick",
        uses_pkce=True,
        client_auth="basic",
        identity_url="https://api.twitter.com/2/users/me",
        identity_id_path=["data", "id"],
        identity_name_path=["data", "username"],
        docs_url="https://developer.x.com/en/docs/authentication/oauth-2-0",
        developer_portal="https://developer.x.com/en/portal/dashboard",
    ),
    "reddit": OAuthProvider(
        key="reddit",
        label="Reddit",
        authorize_url="https://www.reddit.com/api/v1/authorize",
        token_url="https://www.reddit.com/api/v1/access_token",
        scopes=["identity", "submit", "read"],
        mode="oneclick",
        client_auth="basic",
        identity_url="https://oauth.reddit.com/api/v1/me",
        identity_id_path=["id"],
        identity_name_path=["name"],
        # duration=permanent is the ONLY way Reddit hands back a refresh token.
        # Omit it and the connection silently dies in one hour, forever.
        extra_authorize_params={"duration": "permanent"},
        docs_url="https://github.com/reddit-archive/reddit/wiki/OAuth2",
        developer_portal="https://www.reddit.com/prefs/apps",
    ),
    "instagram": OAuthProvider(
        key="instagram",
        label="Instagram",
        authorize_url="https://www.facebook.com/v21.0/dialog/oauth",
        token_url="https://graph.facebook.com/v21.0/oauth/access_token",
        scopes=[
            "instagram_basic",
            "instagram_content_publish",
            "pages_show_list",
            "pages_read_engagement",
        ],
        # Manual: publishing needs a Professional IG account linked to a FB Page,
        # which no OAuth popup can create on Vinta's behalf. Guided paste instead
        # of a one-click button that would fail for reasons the UI can't explain.
        mode="manual",
        client_auth="body",
        identity_url="https://graph.facebook.com/v21.0/me",
        identity_id_path=["id"],
        identity_name_path=["name"],
        identity_auth="query",
        # No refresh_token: a live long-lived token is re-exchanged for a fresh
        # 60-day one (fb_exchange_token). The worker special-cases this.
        supports_refresh=True,
        docs_url="https://developers.facebook.com/docs/instagram-api/getting-started",
        developer_portal="https://developers.facebook.com/apps/",
    ),
    "tiktok": OAuthProvider(
        key="tiktok",
        label="TikTok",
        authorize_url="https://www.tiktok.com/v2/auth/authorize/",
        token_url="https://open.tiktokapis.com/v2/oauth/token/",
        scopes=["user.info.basic", "video.publish", "video.upload"],
        # Manual: Direct Post requires TikTok's app audit. Until that clears, a
        # one-click flow would hand back a token that can't publish.
        mode="manual",
        uses_pkce=True,
        client_auth="body",
        identity_url="https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name",
        identity_id_path=["data", "user", "open_id"],
        identity_name_path=["data", "user", "display_name"],
        docs_url="https://developers.tiktok.com/doc/oauth-user-access-token-management",
        developer_portal="https://developers.tiktok.com/apps",
    ),
    "pinterest": OAuthProvider(
        key="pinterest",
        label="Pinterest",
        authorize_url="https://www.pinterest.com/oauth/",
        token_url="https://api.pinterest.com/v5/oauth/token",
        scopes=["boards:read", "boards:write", "pins:read", "pins:write"],
        mode="oneclick",
        client_auth="basic",
        identity_url="https://api.pinterest.com/v5/user_account",
        identity_id_path=["id"],
        identity_name_path=["username"],
        docs_url="https://developers.pinterest.com/docs/getting-started/authentication/",
        developer_portal="https://developers.pinterest.com/apps/",
    ),
}

# The canonical order the UI renders in. Frontend imports this order from the
# API rather than hardcoding it, so the two can never disagree.
PLATFORM_ORDER = ["twitter", "reddit", "pinterest", "instagram", "tiktok"]


def get_provider(platform: str) -> OAuthProvider:
    p = PROVIDERS.get(platform)
    if not p:
        raise KeyError(platform)
    return p


def credentials_for(platform: str) -> tuple[str, str]:
    """(client_id, client_secret) for the platform's developer app."""
    return _client_id(platform), _client_secret(platform)


def app_configured(platform: str) -> bool:
    """True when the developer app's id+secret exist — the precondition for any
    OAuth flow. The wizard checks this BEFORE opening a popup, because a popup
    that dies on a missing client_id looks like a bug in DirCoMedia rather than
    a step Vinta hasn't done yet."""
    cid, csec = credentials_for(platform)
    return bool(cid and csec)
