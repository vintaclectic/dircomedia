"""
REGRESSION GUARD for the 2026-09-25 Reddit redirect-URI defect.

THE BUG THIS LOCKS DOWN:
  .env carried REDDIT_REDIRECT_URI=http://localhost:8000/oauth/reddit/callback.
  The app only ever served /api/v1/oauth/{platform}/callback. Measured against
  the live process that day: the env path returned 404, the real path 200. Reddit
  requires the redirect_uri sent on token exchange to byte-match the URI
  registered on the app, so the divergence broke the authorization_code exchange
  on its own — and NOTHING in the system compared the two values.

The tests below make that class of drift a test failure instead of an HTTP 401
someone has to debug by hand.
"""
from __future__ import annotations

import pytest

from app.main import app
from app.services.oauth.providers import PLATFORM_ORDER
from app.services.oauth.redirects import (
    canonical_redirect_uri,
    callback_path_template,
    served_callback_paths,
    redirect_uri_drift,
    route_mismatch,
)


def _concrete_callback_paths() -> set[str]:
    """Every callback path the app actually serves, placeholder intact."""
    return {
        p for p in (getattr(r, "path", "") or "" for r in app.routes)
        if p.endswith("/callback") and "{platform}" in p
    }


# ── the core guard ───────────────────────────────────────────────────────────

def test_callback_route_is_mounted_exactly_once():
    """If this fails, the redirect URI is not well-defined and every OAuth flow
    breaks with a provider error that reads like bad credentials."""
    assert route_mismatch(app) is None, route_mismatch(app)
    assert len(served_callback_paths(app)) == 1


@pytest.mark.parametrize("platform", PLATFORM_ORDER)
def test_canonical_redirect_uri_path_is_a_route_the_app_serves(platform, monkeypatch):
    """THE REGRESSION TEST FOR THE ACTUAL BUG.

    The path portion of the canonical redirect URI must correspond to a real
    mounted route. Had this test existed, the /oauth/reddit/callback value could
    never have shipped: that path matches no route.
    """
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    uri = canonical_redirect_uri(platform, app=app)

    assert uri.startswith("http://localhost:8000/"), uri
    path = uri[len("http://localhost:8000"):]

    # Re-templatize the concrete platform back into the placeholder form and
    # require an exact match against a served route.
    templated = path.replace(f"/{platform}/", "/{platform}/")
    assert templated in _concrete_callback_paths(), (
        f"redirect URI path {path!r} for {platform} maps to {templated!r}, which is "
        f"NOT a route this app serves. Served: {sorted(_concrete_callback_paths())}. "
        "This is exactly the 2026-09-25 defect."
    )


def test_the_historical_bad_path_is_rejected(monkeypatch):
    """The specific dead path from the incident must never be canonical again.

    NOTE the comparison is on the FULL path, not a suffix: the correct path
    '/api/v1/oauth/reddit/callback' legitimately *ends with* the bad path's
    text '/oauth/reddit/callback'. A suffix check here is a false positive
    (it failed exactly that way on first run), which is why this asserts
    equality against the dead URI instead.
    """
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    assert "/oauth/reddit/callback" not in _concrete_callback_paths()
    uri = canonical_redirect_uri("reddit", app=app)
    assert uri != "http://localhost:8000/oauth/reddit/callback", (
        f"canonical redirect URI regressed to the 404 path: {uri}"
    )
    assert uri == "http://localhost:8000/api/v1/oauth/reddit/callback", uri


def test_callback_template_is_derived_from_routes_not_hardcoded():
    """The template must come from the route table, so remounting the router
    moves the redirect URI with it instead of silently diverging."""
    assert callback_path_template(app) in _concrete_callback_paths()


# ── drift detection ──────────────────────────────────────────────────────────

def test_drift_is_detected_when_env_disagrees_with_routes(monkeypatch):
    """Simulate the original broken .env and assert we now SHOUT about it."""
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.reddit_redirect_uri",
        "http://localhost:8000/oauth/reddit/callback",  # the historical bad value
        raising=False,
    )
    warning = redirect_uri_drift("reddit", app=app)
    assert warning is not None, "the original defect would pass silently again"
    assert "/api/v1/oauth/reddit/callback" in warning, warning
    assert "IGNORED" in warning or "ignored" in warning


def test_no_drift_reported_when_env_matches_the_served_route(monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    monkeypatch.setattr(
        "app.config.settings.reddit_redirect_uri",
        "http://localhost:8000/api/v1/oauth/reddit/callback",
        raising=False,
    )
    assert redirect_uri_drift("reddit", app=app) is None


def test_blank_env_var_means_no_drift(monkeypatch):
    """An unset legacy var is the desired end state, not a warning."""
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    monkeypatch.setattr("app.config.settings.reddit_redirect_uri", "", raising=False)
    assert redirect_uri_drift("reddit", app=app) is None


def test_trailing_slash_in_base_cannot_double_up(monkeypatch):
    """'//callback' would be a byte-mismatch against the registered URI."""
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000/", raising=False
    )
    uri = canonical_redirect_uri("reddit", app=app)
    assert "//api" not in uri, uri
    assert uri == "http://localhost:8000/api/v1/oauth/reddit/callback", uri


# ── the ROUTER's own value, not just the helper ──────────────────────────────
# These exist because the first version of this file only tested
# canonical_redirect_uri() directly. A deliberately reinjected regression in
# api/v1/oauth.py::_redirect_uri PASSED all of them — the helper was correct
# while the router ignored it. Verified 2026-09-25. Test the seam, not the unit.

def test_router_redirect_uri_helper_matches_canonical(monkeypatch):
    """api/v1/oauth.py::_redirect_uri must defer to the single source of truth."""
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    from app.api.v1.oauth import _redirect_uri

    class _Req:  # only base_url is consulted, and only as a fallback
        base_url = "http://localhost:8000/"

    for platform in PLATFORM_ORDER:
        assert _redirect_uri(_Req(), platform) == canonical_redirect_uri(
            platform, app=app
        ), f"router disagrees with the canonical URI for {platform}"


def test_router_redirect_uri_is_a_served_route(monkeypatch):
    """The value the ROUTER hands to the provider must name a real route.

    THIS is the assertion that fails if _redirect_uri ever regresses to a
    hardcoded path, which is the exact shape of the 2026-09-25 defect.
    """
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    from app.api.v1.oauth import _redirect_uri

    class _Req:
        base_url = "http://localhost:8000/"

    for platform in PLATFORM_ORDER:
        uri = _redirect_uri(_Req(), platform)
        path = uri[len("http://localhost:8000"):]
        templated = path.replace(f"/{platform}/", "/{platform}/")
        assert templated in _concrete_callback_paths(), (
            f"the ROUTER returned redirect URI {uri!r} for {platform}, whose path "
            f"{templated!r} is NOT a route this app serves. Served: "
            f"{sorted(_concrete_callback_paths())}. This is the 2026-09-25 defect."
        )


# ── the script must use the same value ───────────────────────────────────────

def test_script_uses_the_canonical_uri(monkeypatch):
    """scripts/reddit_oauth.py must not carry its own idea of the redirect URI."""
    monkeypatch.setattr(
        "app.config.settings.oauth_redirect_base", "http://localhost:8000", raising=False
    )
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "reddit_oauth.py"
    spec = importlib.util.spec_from_file_location("reddit_oauth_script", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.canonical_uri() == canonical_redirect_uri("reddit", app=app)


# ── the honest-diagnostics guard (defect B) ──────────────────────────────────

def _script():
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parent.parent / "scripts" / "reddit_oauth.py"
    spec = importlib.util.spec_from_file_location("reddit_oauth_script2", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pasting_the_authorize_url_is_named_exactly():
    """Vinta's ACTUAL failure: he pasted the authorize URL. The old code used the
    whole URL as the 'code' and then blamed his app type."""
    mod = _script()
    authorize = (
        "https://www.reddit.com/api/v1/authorize?client_id=AAA&response_type=code"
        "&state=XYZ&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Foauth"
        "%2Freddit%2Fcallback&duration=permanent&scope=submit+identity+read"
    )
    code, problem = mod.extract_code(authorize)
    assert code is None, "the authorize URL must never be accepted as a code"
    assert "AUTHORIZE URL" in problem
    assert "code=" in problem
    # It must NOT send him to the app-type console on this evidence.
    assert "script" not in problem.lower() or "app type" not in problem.lower()


def test_real_redirected_url_yields_just_the_code():
    mod = _script()
    code, problem = mod.extract_code(
        "http://localhost:8000/api/v1/oauth/reddit/callback?state=XYZ&code=REALCODE123#_"
    )
    assert problem is None, problem
    assert code == "REALCODE123", code


def test_access_denied_is_named_as_a_declined_click():
    mod = _script()
    code, problem = mod.extract_code(
        "http://localhost:8000/api/v1/oauth/reddit/callback?error=access_denied&state=X"
    )
    assert code is None
    assert "access_denied" in problem and "Decline" in problem


def test_bare_code_is_accepted():
    mod = _script()
    code, problem = mod.extract_code("abc123-XYZ_code")
    assert problem is None, problem
    assert code == "abc123-XYZ_code"


def test_401_diagnosis_names_credentials_and_redirect_not_app_type():
    """The misdiagnosis that cost hours must be structurally impossible."""
    mod = _script()
    msg = mod.diagnose_exchange_failure(
        401, '{"message": "Unauthorized", "error": 401}',
        "http://localhost:8000/api/v1/oauth/reddit/callback",
    )
    assert "CLIENT CREDENTIALS" in msg
    assert "REDIRECT URI" in msg
    # The exact URI must be shown so a mismatch is visible, not guessed.
    assert "http://localhost:8000/api/v1/oauth/reddit/callback" in msg
    # And it must explicitly warn against changing app type on a guess.
    assert "do not go change your app type on a guess" in msg


def test_invalid_grant_diagnosis_names_expiry_reuse_and_mismatch():
    mod = _script()
    msg = mod.diagnose_exchange_failure(
        400, '{"error": "invalid_grant"}',
        "http://localhost:8000/api/v1/oauth/reddit/callback",
    )
    assert "SINGLE-USE" in msg
    assert "expired" in msg
    assert "redirect_uri" in msg
