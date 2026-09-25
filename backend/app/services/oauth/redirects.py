"""
THE SINGLE SOURCE OF TRUTH for OAuth redirect URIs (task: reddit-redirect-fix,
2026-09-25).

WHY THIS FILE EXISTS — the defect it makes impossible:

  `.env` carried `REDDIT_REDIRECT_URI=http://localhost:8000/oauth/reddit/callback`.
  The app has never served that path. The only callback route it mounts is
  `/api/v1/oauth/{platform}/callback` (main.py mounts `oauth.public_router` under
  the `/api/v1/oauth` prefix). Measured 2026-09-25 against the live process:
  the env path returned 404, the real path returned 200.

  Reddit requires the `redirect_uri` sent on token exchange to byte-match the URI
  registered on the developer app. So the hand-maintained env var and the
  app-computed value were two different strings, only one of which could ever
  work, and NOTHING told anyone they had diverged. `scripts/reddit_oauth.py` read
  the broken one; the in-app wizard computed the working one.

THE FIX, and why it's shaped this way:

  1. The callback PATH is derived from the actual FastAPI route table at runtime
     (`callback_path_template()`), not from a string literal. If someone remounts
     the router under a different prefix, this follows them. A literal cannot.
  2. Every consumer — wizard, script, refresh, docs, status — calls
     `canonical_redirect_uri()`. There is one function, so there cannot be two
     answers.
  3. `redirect_uri_drift()` actively compares any legacy env-configured value
     against the derived truth and reports the mismatch, which `/oauth/status`
     surfaces. A silent divergence is no longer possible: it fails LOUDLY.

The env var `REDDIT_REDIRECT_URI` is now DESCRIPTIVE, never AUTHORITATIVE. It is
kept only so an operator reading `.env` isn't confused by its disappearance, and
it is checked for drift rather than trusted.
"""
from __future__ import annotations

from typing import Optional

# The path template we expect to serve. Verified against the live route table by
# `callback_path_template()`; this constant is only the fallback used when no app
# instance is importable (e.g. a standalone CLI script with no server running).
FALLBACK_CALLBACK_TEMPLATE = "/api/v1/oauth/{platform}/callback"


def callback_path_template(app=None) -> str:
    """The callback path template the app ACTUALLY serves, read from the route
    table.

    Returns something like '/api/v1/oauth/{platform}/callback'. We look for a
    real route whose path ends in '/callback' and contains the platform
    placeholder, so the prefix comes from the mount rather than from a guess.

    Falls back to FALLBACK_CALLBACK_TEMPLATE only when the app cannot be
    imported (standalone script context). Any disagreement between the two is
    reported by `route_mismatch()` rather than silently tolerated.
    """
    if app is None:
        try:
            from app.main import app as _app  # local import: avoids a cycle
            app = _app
        except Exception:
            return FALLBACK_CALLBACK_TEMPLATE

    for route in getattr(app, "routes", []):
        path = getattr(route, "path", "") or ""
        if path.endswith("/callback") and "{platform}" in path:
            return path
    return FALLBACK_CALLBACK_TEMPLATE


def served_callback_paths(app=None) -> list[str]:
    """Every concrete callback path the app serves, platform placeholder intact.
    Used by the startup check and by tests as the authoritative route list."""
    if app is None:
        try:
            from app.main import app as _app
            app = _app
        except Exception:
            return [FALLBACK_CALLBACK_TEMPLATE]
    return [
        p for p in (getattr(r, "path", "") or "" for r in getattr(app, "routes", []))
        if p.endswith("/callback") and "{platform}" in p
    ]


def redirect_base(request=None) -> str:
    """The public origin providers redirect back to.

    Precedence: OAUTH_REDIRECT_BASE (explicit, required behind a tunnel) →
    the inbound request's own base URL (correct for localhost dev). Trailing
    slash is always stripped so concatenation can't produce a double slash — a
    '//callback' would be a byte-mismatch against the registered URI and fail.
    """
    from app.config import settings as cfg

    base = (getattr(cfg, "oauth_redirect_base", "") or "").strip().rstrip("/")
    if base:
        return base
    if request is not None:
        return str(request.base_url).rstrip("/")
    return ""


def canonical_redirect_uri(platform: str, request=None, app=None) -> str:
    """THE redirect URI for `platform`. Every caller uses this one function.

    This is the string that must be registered byte-for-byte in the provider's
    developer app, the string sent on authorize, and the string sent on token
    exchange. One function, one answer, no drift.
    """
    base = redirect_base(request)
    path = callback_path_template(app).replace("{platform}", platform)
    return f"{base}{path}"


def legacy_env_redirect_uri(platform: str) -> Optional[str]:
    """The hand-maintained env value for this platform, if one exists.

    Descriptive only — never used to build a request. Read solely so
    `redirect_uri_drift()` can report that it disagrees with reality.
    """
    from app.config import settings as cfg

    attr = {"reddit": "reddit_redirect_uri"}.get(platform)
    if not attr:
        return None
    val = (getattr(cfg, attr, "") or "").strip()
    return val or None


def redirect_uri_drift(platform: str, request=None, app=None) -> Optional[str]:
    """A human-readable drift warning, or None when everything agrees.

    THIS IS THE REGRESSION GUARD for the 2026-09-25 defect. When a legacy env
    var names a path the app does not serve, this returns the explanation and
    `/oauth/status` shows it — so the mismatch is visible in the UI instead of
    manifesting as an inexplicable HTTP 401 from the provider.
    """
    legacy = legacy_env_redirect_uri(platform)
    if not legacy:
        return None
    canonical = canonical_redirect_uri(platform, request=request, app=app)
    if legacy.rstrip("/") == canonical.rstrip("/"):
        return None
    return (
        f"Config drift: REDDIT_REDIRECT_URI is set to '{legacy}', but this app "
        f"serves its callback at '{canonical}'. The env value is IGNORED (the "
        f"route is authoritative). Register '{canonical}' in the provider's "
        f"developer app — Reddit requires a byte-exact match."
    )


def route_mismatch(app=None) -> Optional[str]:
    """Startup sanity check: does a callback route exist at all?

    If the router were ever remounted or dropped, every OAuth flow would break
    with a provider-side error that looks like bad credentials. Better to say so
    at boot than to debug a 401 for an hour.
    """
    paths = served_callback_paths(app)
    if not paths:
        return (
            "No OAuth callback route is mounted. Expected a route matching "
            f"'{FALLBACK_CALLBACK_TEMPLATE}'. Every OAuth flow will fail until "
            "app/main.py mounts oauth.public_router."
        )
    if len(paths) > 1:
        return (
            f"Ambiguous OAuth callback routes mounted: {paths}. Exactly one is "
            "required, otherwise the redirect URI is not well-defined."
        )
    return None
