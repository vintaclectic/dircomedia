"""
OAuth connection wizard API (YH9AE4D, council build 2026-08-12).

TWO ROUTERS, and the split is the whole security design:

  router       — owner-only. Everything Vinta's dashboard calls: status, start,
                 manual save, test, disconnect, refresh. Mounted under the global
                 require_owner dependency in main.py.

  public_router— NOT owner-guarded, by necessity. The provider redirects the
                 BROWSER back to /callback; that request carries no Authorization
                 header and never can. Guarding it with the owner token would
                 make every OAuth flow fail 401.

    So what authenticates the callback? The single-use `state` token. It was
    minted by an owner-authenticated /start call, is bound to one platform, dies
    in 10 minutes, and is deleted the instant it's redeemed. An attacker who hits
    /callback without a valid state gets nothing; one who replays a captured
    callback URL finds the state already burned. That is exactly the property
    OAuth's state parameter exists to provide, and it's why this is the one
    endpoint in DirCoMedia that isn't behind the owner token.
"""
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.crypto import crypto_available
from app.services.oauth import flow as oauth_flow
from app.services.oauth.providers import (
    PROVIDERS, PLATFORM_ORDER, get_provider, credentials_for, app_configured,
)
from app.services.oauth import store

router = APIRouter()
public_router = APIRouter()

# The redirect URI the provider sends the browser back to. Must match the value
# registered in each developer app EXACTLY (scheme, host, path, no trailing
# slash) — a mismatch is the single most common OAuth failure, so the wizard
# shows this string with a copy button rather than making Vinta retype it.
def _redirect_uri(request: Request, platform: str) -> str:
    from app.config import settings as cfg
    base = (getattr(cfg, "oauth_redirect_base", "") or "").rstrip("/")
    if not base:
        base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/oauth/{platform}/callback"


# ── status ───────────────────────────────────────────────────────────────────

class PlatformStatusOut(BaseModel):
    platform: str
    label: str
    mode: str                      # 'oneclick' | 'manual'
    status: str                    # 'connected'|'expiring'|'expired'|'needs_reconnect'|'disconnected'
    account_name: Optional[str] = None
    expires_at: Optional[int] = None
    expires_in_days: Optional[float] = None
    app_configured: bool
    needs_reconnect: bool = False
    last_error: Optional[str] = None
    scopes: Optional[str] = None
    redirect_uri: str
    developer_portal: str
    docs_url: str


EXPIRING_WINDOW_DAYS = 3


def _derive_status(row, now: int) -> tuple[str, Optional[float]]:
    """One place that decides ✅/⚠️/❌ so the dashboard, the picker, and the
    health endpoint can never disagree about what 'connected' means."""
    if row is None:
        return "disconnected", None
    if row.needs_reconnect:
        return "needs_reconnect", None
    if row.expires_at is None:
        return "connected", None          # non-expiring credential
    remaining = row.expires_at - now
    days = round(remaining / 86400, 2)
    if remaining <= 0:
        return "expired", days
    if remaining <= EXPIRING_WINDOW_DAYS * 86400:
        return "expiring", days
    return "connected", days


@router.get("/status", response_model=list[PlatformStatusOut])
async def connection_status(request: Request, db: AsyncSession = Depends(get_db)):
    """The health wall's single source of truth (Screen 1 + Screen 3)."""
    rows = {c.platform: c for c in await store.list_credentials(db)}
    now = int(time.time())
    out = []
    for key in PLATFORM_ORDER:
        p = get_provider(key)
        row = rows.get(key)
        status, days = _derive_status(row, now)
        out.append(PlatformStatusOut(
            platform=key,
            label=p.label,
            mode=p.mode,
            status=status,
            account_name=getattr(row, "account_name", None),
            expires_at=getattr(row, "expires_at", None),
            expires_in_days=days,
            app_configured=app_configured(key),
            needs_reconnect=bool(getattr(row, "needs_reconnect", False)),
            last_error=getattr(row, "last_error", None),
            scopes=getattr(row, "scopes", None),
            redirect_uri=_redirect_uri(request, key),
            developer_portal=p.developer_portal,
            docs_url=p.docs_url,
        ))
    return out


@router.get("/encryption-status")
async def encryption_status():
    """Lets the UI warn BEFORE a save that would fail closed."""
    return {"configured": crypto_available()}


# ── one-click flow ───────────────────────────────────────────────────────────

class StartOut(BaseModel):
    authorize_url: str
    state: str
    expires_in: int


@router.get("/{platform}/start", response_model=StartOut)
async def oauth_start(platform: str, request: Request, db: AsyncSession = Depends(get_db)):
    if platform not in PROVIDERS:
        raise HTTPException(404, f"Unknown platform '{platform}'.")
    if not crypto_available():
        raise HTTPException(503, "CREDENTIAL_ENCRYPTION_KEY is not configured; refusing to start a flow whose token could not be stored safely.")
    p = get_provider(platform)
    cid, csec = credentials_for(platform)
    if not (cid and csec):
        raise HTTPException(
            400,
            f"{p.label} developer app is not configured. Add the client ID and secret "
            f"in Manual Setup first ({p.developer_portal}).",
        )

    redirect_uri = _redirect_uri(request, platform)
    verifier = challenge = None
    if p.uses_pkce:
        verifier, challenge = oauth_flow.make_pkce_pair()

    state = await store.issue_state(db, platform, redirect_uri, verifier)
    return StartOut(
        authorize_url=oauth_flow.build_authorize_url(
            p, client_id=cid, redirect_uri=redirect_uri,
            state=state, code_challenge=challenge,
        ),
        state=state,
        expires_in=store.STATE_TTL_SECONDS,
    )


def _popup_close_page(ok: bool, platform: str, message: str) -> HTMLResponse:
    """The popup's last act: tell the opener what happened, then close itself.

    postMessage is targeted at the opener only. We never put the token — or
    anything derived from it — in this page; the opener re-fetches /status from
    the owner-authenticated API to learn the new state. The popup carries a
    verdict, not a secret.
    """
    import json
    payload = json.dumps({"source": "dircomedia-oauth", "ok": ok, "platform": platform, "message": message})
    color = "#00DD88" if ok else "#FF3B47"
    title = "Connected" if ok else "Connection failed"
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · DirCoMedia</title></head>
<body style="margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#020205;color:#f5f5f7;font-family:system-ui,-apple-system,sans-serif;padding:24px;">
  <div style="max-width:380px;width:100%;text-align:center;">
    <div style="width:48px;height:48px;border-radius:50%;margin:0 auto 18px;
      background:{color}22;border:1px solid {color}66;display:flex;align-items:center;
      justify-content:center;font-size:22px;color:{color};">{"&#10003;" if ok else "!"}</div>
    <h1 style="font-size:19px;margin:0 0 10px;letter-spacing:-0.02em;">{title}</h1>
    <p style="font-size:13.5px;line-height:1.55;color:#8a8a98;margin:0 0 20px;
      word-break:break-word;">{message}</p>
    <p style="font-size:11px;color:#56565f;margin:0;">You can close this window.</p>
  </div>
  <script>
    try {{ if (window.opener) window.opener.postMessage({payload}, "*"); }} catch (e) {{}}
    setTimeout(function () {{ try {{ window.close(); }} catch (e) {{}} }}, {1200 if ok else 4000});
  </script>
</body></html>"""
    return HTMLResponse(html)


@public_router.get("/{platform}/callback", response_class=HTMLResponse)
async def oauth_callback(
    platform: str,
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    error_description: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Provider redirect target. Authenticated by the single-use state token.

    Returns an HTML page (never JSON) because a human's browser lands here — a
    raw JSON blob in a popup is a dead end for the person staring at it.
    """
    if platform not in PROVIDERS:
        return _popup_close_page(False, platform, f"Unknown platform '{platform}'.")
    p = get_provider(platform)

    if error:
        return _popup_close_page(
            False, platform,
            f"{p.label} denied the authorization: {(error_description or error)[:200]}",
        )
    if not code:
        return _popup_close_page(False, platform, "No authorization code was returned.")

    # CSRF gate — everything below only runs for a state we ourselves minted.
    try:
        st = await store.consume_state(db, state or "", platform)
    except ValueError as e:
        return _popup_close_page(False, platform, str(e))

    try:
        payload = await oauth_flow.exchange_code(
            p, code=code, redirect_uri=st.redirect_uri, code_verifier=st.code_verifier,
        )
    except oauth_flow.OAuthError as e:
        return _popup_close_page(False, platform, str(e))
    except Exception as e:
        return _popup_close_page(False, platform, f"Token exchange error: {e.__class__.__name__}")

    access = payload["access_token"]
    account_id, account_name = await oauth_flow.fetch_identity(p, access)

    try:
        await store.upsert_credential(
            db,
            platform=platform,
            access_token=access,
            refresh_token=payload.get("refresh_token"),
            expires_at=oauth_flow.expires_at_from(payload),
            account_id=account_id,
            account_name=account_name,
            scopes=payload.get("scope") or " ".join(p.scopes),
        )
    except Exception as e:
        return _popup_close_page(False, platform, f"Could not store credential: {e.__class__.__name__}")

    who = f" as @{account_name}" if account_name else ""
    return _popup_close_page(True, platform, f"{p.label} connected{who}. You can post to {p.label} from DirCoMedia now.")


# ── manual setup ─────────────────────────────────────────────────────────────

class ManualAppIn(BaseModel):
    """Developer-app credentials (client id/secret) — the prerequisite for a
    one-click flow. Written to .env, not the token vault, because the platform
    clients read them from settings."""
    client_id: str
    client_secret: str


ENV_KEYS = {
    "twitter": ("TWITTER_API_KEY", "TWITTER_API_SECRET"),
    "reddit": ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"),
    "instagram": ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET"),
    "tiktok": ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"),
    "pinterest": ("PINTEREST_APP_ID", "PINTEREST_APP_SECRET"),
}


@router.post("/{platform}/app")
async def save_app_credentials(platform: str, body: ManualAppIn):
    if platform not in PROVIDERS:
        raise HTTPException(404, f"Unknown platform '{platform}'.")
    cid, csec = body.client_id.strip(), body.client_secret.strip()
    if not cid or not csec:
        raise HTTPException(400, "Both client ID and client secret are required.")

    from app.api.v1.settings import _write_env
    from app.config import settings as cfg

    id_key, secret_key = ENV_KEYS[platform]
    _write_env({id_key: cid, secret_key: csec})

    # Update the live settings object too, so the very next /start works without
    # a restart. Vinta pasting a secret and then being told "restart the server"
    # is a wizard that isn't finished.
    attr_map = {
        "twitter": ("twitter_api_key", "twitter_api_secret"),
        "reddit": ("reddit_client_id", "reddit_client_secret"),
        "instagram": ("instagram_app_id", "instagram_app_secret"),
        "tiktok": ("tiktok_client_key", "tiktok_client_secret"),
        "pinterest": ("pinterest_app_id", "pinterest_app_secret"),
    }[platform]
    setattr(cfg, attr_map[0], cid)
    setattr(cfg, attr_map[1], csec)
    return {"saved": True, "platform": platform, "app_configured": True}


class ManualTokenIn(BaseModel):
    """A token Vinta minted himself (Graph API Explorer, TikTok sandbox, etc.)."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in_days: Optional[float] = None


@router.post("/{platform}/manual-token")
async def save_manual_token(platform: str, body: ManualTokenIn, db: AsyncSession = Depends(get_db)):
    """Paste-a-token lane (Instagram + TikTok, and a fallback for any platform).

    The token is PROBED before it's stored. A wizard that accepts a bad paste and
    reports success is worse than one that rejects it — the failure would surface
    days later as a silently missed post.
    """
    if platform not in PROVIDERS:
        raise HTTPException(404, f"Unknown platform '{platform}'.")
    if not crypto_available():
        raise HTTPException(503, "CREDENTIAL_ENCRYPTION_KEY is not configured; refusing to store a credential in plaintext.")
    p = get_provider(platform)
    token = body.access_token.strip()
    if not token:
        raise HTTPException(400, "Access token is required.")

    ok, err = await oauth_flow.probe_token(p, token)
    if not ok:
        raise HTTPException(400, f"{p.label} rejected that token: {err}")

    account_id, account_name = await oauth_flow.fetch_identity(p, token)
    expires_at = (
        int(time.time() + body.expires_in_days * 86400)
        if body.expires_in_days else None
    )
    # Instagram refreshes by re-exchanging the ACCESS token, so it is its own
    # refresh material. Storing it in both columns is what lets the generic
    # worker refresh Instagram without a special case at call time.
    refresh = body.refresh_token or (token if platform == "instagram" else None)
    if platform == "instagram" and expires_at is None:
        expires_at = int(time.time() + 60 * 86400)  # FB long-lived default

    await store.upsert_credential(
        db, platform=platform, access_token=token, refresh_token=refresh,
        expires_at=expires_at, account_id=account_id, account_name=account_name,
        scopes=" ".join(p.scopes),
    )
    return {
        "connected": True, "platform": platform,
        "account_name": account_name, "expires_at": expires_at,
    }


# ── manage ───────────────────────────────────────────────────────────────────

@router.post("/{platform}/test")
async def test_connection(platform: str, db: AsyncSession = Depends(get_db)):
    """Live proof-of-life for one platform. Powers 'Test Connection'."""
    if platform not in PROVIDERS:
        raise HTTPException(404, f"Unknown platform '{platform}'.")
    p = get_provider(platform)
    token = await store.get_access_token(db, platform)
    if not token:
        return {"ok": False, "platform": platform, "error": "Not connected."}
    ok, err = await oauth_flow.probe_token(p, token)
    if not ok:
        await store.mark_needs_reconnect(db, platform, err or "probe failed")
        return {"ok": False, "platform": platform, "error": err}
    _, account_name = await oauth_flow.fetch_identity(p, token)
    return {"ok": True, "platform": platform, "account_name": account_name}


@router.post("/{platform}/refresh")
async def refresh_now(platform: str, db: AsyncSession = Depends(get_db)):
    """Manual 'Refresh Now' — the same code path the worker runs on schedule."""
    if platform not in PROVIDERS:
        raise HTTPException(404, f"Unknown platform '{platform}'.")
    from app.services.oauth.refresh import refresh_one
    result = await refresh_one(db, platform)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or "Refresh failed.")
    return result


@router.delete("/{platform}")
async def disconnect(platform: str, db: AsyncSession = Depends(get_db)):
    """Revoke locally: the credential is deleted outright, not soft-flagged.

    A 'disconnected' row that still holds a live token is a loaded gun in a
    backup file. Deleting is the only honest implementation of Disconnect.
    """
    if platform not in PROVIDERS:
        raise HTTPException(404, f"Unknown platform '{platform}'.")
    removed = await store.delete_credential(db, platform)
    return {"disconnected": removed, "platform": platform}
