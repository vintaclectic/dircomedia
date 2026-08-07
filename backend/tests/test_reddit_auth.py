"""Reddit auth: prove the 401 explains the POLICY wall, not a config bug.

Context (verified live 2026-08-06): this account's Reddit app returns 401 on
EVERY grant type, including `client_credentials` — a grant that needs no user,
no password, and no 2FA. That isolates the fault to the app credentials
themselves.

Two traps this file exists to prevent, in both directions:

1. UNDER-stating it: the obvious fix ("go make a new app at prefs/apps")
   stopped being true. Reddit ended self-service API access in Nov 2025.
   prefs/apps still hands out an id/secret, but registration is no longer
   access — new credentials must clear a manual Responsible-Builder review with
   no SLA that routinely rejects small projects.

2. OVER-stating it (added 2026-08-07, after Vinta correctly called this out):
   the message previously said Reddit was "UNAVAILABLE" / permanently closed.
   That conflated two different things. The Responsible Builder Policy gates
   API *tokens*; it does not gate *people*. Posting to subreddits from your own
   account in a browser needs no app, no token, and no approval — that channel
   was never closed. And even the API is gated-and-slow, not shut: there is a
   real application path to a real free tier.

So these tests assert the error message tells the *whole* truth in both
directions: the creds are dead and re-registration isn't instant access, AND
the failure is scoped to automation rather than to Reddit as a channel.
"""
import pytest

from app.services.distribution.platforms import reddit as reddit_mod


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(
                f"raise_for_status() reached with {self.status_code}; the 401 "
                "branch should have raised a descriptive error first."
            )


class _FakeClient:
    """Stands in for httpx.AsyncClient as an async context manager."""

    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *args, **kwargs):
        return self._response


@pytest.fixture
def client(monkeypatch):
    c = reddit_mod.RedditClient()
    # A refresh token keeps _auth_data() on the happy path so the test
    # exercises the 401 handling, not the "not configured" guard.
    c.refresh_token = "fake-refresh-token"
    c.client_id = "fake-id"
    c.client_secret = "fake-secret"
    c._access_token = ""
    c._token_expiry = 0.0
    return c


def _patch_response(monkeypatch, response: _FakeResponse):
    monkeypatch.setattr(
        reddit_mod.httpx, "AsyncClient", lambda *a, **k: _FakeClient(response)
    )


@pytest.mark.asyncio
async def test_401_names_policy_wall_not_just_bad_creds(monkeypatch, client):
    """The 401 must say this is a policy wall no code can fix."""
    _patch_response(monkeypatch, _FakeResponse(401))

    with pytest.raises(RuntimeError) as exc:
        await client._get_access_token()

    msg = str(exc.value).lower()
    # It still has to identify the proximate cause...
    assert "401" in msg and "client_credentials" in msg
    # ...and it must rule out the two wrong suspects that cost days already.
    assert "2fa" in msg
    assert "no code change" in msg or "no code change fixes it" in msg
    # ...and it must name the actual 2026 blocker.
    assert "policy" in msg
    assert "self-service" in msg
    assert "review" in msg


@pytest.mark.asyncio
async def test_401_does_not_promise_a_new_app_just_works(monkeypatch, client):
    """Regression: the old message told operators to create a new app as if
    that restored access. It doesn't — registration != approval since Nov 2025.
    Fail if the message ever implies a self-serve fix again."""
    _patch_response(monkeypatch, _FakeResponse(401))

    with pytest.raises(RuntimeError) as exc:
        await client._get_access_token()

    msg = str(exc.value).lower()
    # If prefs/apps is mentioned at all, the caveat must be adjacent.
    if "prefs/apps" in msg:
        assert "review" in msg or "grants nothing" in msg, (
            "Mentioning prefs/apps without the approval caveat recreates the "
            "exact dead-end advice this test exists to prevent."
        )
    # And it must point at a rail that actually works right now.
    assert "manually" in msg or "own account" in msg


@pytest.mark.asyncio
async def test_401_tells_caller_to_stop_retrying(monkeypatch, client):
    """A retry loop against a policy wall burns quota forever. Say so."""
    _patch_response(monkeypatch, _FakeResponse(401))

    with pytest.raises(RuntimeError) as exc:
        await client._get_access_token()

    assert "do not retry" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_401_scopes_failure_to_automation_not_to_reddit(monkeypatch, client):
    """Regression (Vinta, 2026-08-07): the message must NEVER claim Reddit is
    closed to us.

    The old text said Reddit was "UNAVAILABLE as a distribution rail", which
    caused the council to write off the single highest-traffic channel
    available to this funnel. The Responsible Builder Policy gates API tokens,
    not people — manual posting from your own account is unaffected.

    This test fails if the doom framing ever comes back."""
    _patch_response(monkeypatch, _FakeResponse(401))

    with pytest.raises(RuntimeError) as exc:
        await client._get_access_token()

    msg = str(exc.value).lower()

    # It must explicitly scope the breakage to automation...
    assert "automated" in msg, "must say only AUTOMATED posting is blocked"
    # ...and explicitly deny that Reddit itself is closed.
    assert "not closed" in msg

    # And it must never resurrect the absolutist framing.
    for banned in ("permanently closed", "unavailable as a distribution",
                   "reddit is closed"):
        assert banned not in msg, f"doom framing regressed: {banned!r}"


@pytest.mark.asyncio
async def test_successful_auth_still_caches_token(monkeypatch, client):
    """Guard the happy path: the 401 branch must not shadow real success."""
    _patch_response(
        monkeypatch,
        _FakeResponse(200, {"access_token": "tok-123", "expires_in": 3600}),
    )

    token = await client._get_access_token()

    assert token == "tok-123"
    assert client._access_token == "tok-123"
    assert client._token_expiry > 0


@pytest.mark.asyncio
async def test_cached_token_is_reused_without_network(monkeypatch, client):
    """A still-valid cached token must not trigger another auth round trip."""
    import time

    client._access_token = "cached-tok"
    client._token_expiry = time.time() + 3600

    def _boom(*a, **k):
        raise AssertionError("network hit despite a valid cached token")

    monkeypatch.setattr(reddit_mod.httpx, "AsyncClient", _boom)

    assert await client._get_access_token() == "cached-tok"
