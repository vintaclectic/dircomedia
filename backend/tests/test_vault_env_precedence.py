"""A dead vault entry must never shadow a live .env lane (ZBG52ZY, 2026-08-27).

This failure has now shipped twice: X's wizard token expired, and because the
vault unconditionally won the merge, the dashboard reported the entire rail
dead while OAuth 1.0a keys in .env were posting fine. "Nothing works" was the
UI lying, not an outage. These tests pin both halves of the fix.
"""
import time

import pytest

from app.services.distribution import health


@pytest.mark.asyncio
async def test_dead_vault_entry_does_not_shadow_live_env(monkeypatch):
    async def fake_vault():
        return {
            "twitter": {
                "configured": True, "source": "oauth_wizard", "live": False,
                "account": "stale_handle", "needs_reconnect": True,
                "expires_in_days": -1.48, "error": "HTTP 403",
            }
        }

    async def fake_twitter():
        return {"configured": True, "live": True, "account": "Vintaclectic"}

    monkeypatch.setattr(health, "vault_health", fake_vault)
    monkeypatch.setattr(health, "twitter_health", fake_twitter)

    merged = await health.check_all()
    tw = merged["twitter"]

    assert tw["live"] is True, "a live .env lane must survive a dead vault row"
    assert tw["account"] == "Vintaclectic"
    assert tw["source"] == "env"
    # The reconnect prompt must survive so the UI can still nudge Vinta.
    assert tw["vault_state"]["needs_reconnect"] is True


@pytest.mark.asyncio
async def test_live_vault_entry_still_wins(monkeypatch):
    async def fake_vault():
        return {"twitter": {"configured": True, "source": "oauth_wizard",
                            "live": True, "account": "wizard_acct"}}

    async def fake_twitter():
        return {"configured": True, "live": True, "account": "env_acct"}

    monkeypatch.setattr(health, "vault_health", fake_vault)
    monkeypatch.setattr(health, "twitter_health", fake_twitter)

    tw = (await health.check_all())["twitter"]
    assert tw["account"] == "wizard_acct", "a working wizard token still wins"


@pytest.mark.asyncio
async def test_expired_token_is_not_handed_out():
    """get_access_token must refuse an expired row so callers fall back."""
    from app.services.oauth import store

    class Row:
        needs_reconnect = False
        expires_at = int(time.time()) - 3600
        access_token = "enc"

    async def fake_get_credential(db, platform):
        return Row()

    orig = store.get_credential
    store.get_credential = fake_get_credential
    try:
        assert await store.get_access_token(None, "twitter") is None
    finally:
        store.get_credential = orig
