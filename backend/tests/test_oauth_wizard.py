"""
OAuth connection wizard — security + contract regression tests (YH9AE4D).

These lock down the properties that are expensive to rediscover by hand:
encryption at rest, CSRF state validation, status derivation, and the
frontend/backend enum contract. If any of these break, the wizard is either
insecure or lying to the dashboard — both are ship-blockers.
"""
import os
import time

import pytest
from cryptography.fernet import Fernet

# The crypto module reads os.environ at first use; make sure a key exists before
# anything imports it, so the suite is independent of the developer's .env.
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.core import crypto  # noqa: E402
from app.api.v1.oauth import _derive_status, EXPIRING_WINDOW_DAYS  # noqa: E402
from app.services.oauth.providers import (  # noqa: E402
    PROVIDERS, PLATFORM_ORDER, get_provider,
)
from app.services.oauth import flow as oauth_flow  # noqa: E402


# ── encryption at rest ───────────────────────────────────────────────────────

def test_encrypt_roundtrip():
    secret = "ACCESS-TOKEN-abcdef123456"
    blob = crypto.encrypt(secret)
    assert blob != secret
    assert secret not in blob                  # THE property that matters
    assert blob.startswith("gAAAAA")           # Fernet magic
    assert crypto.decrypt(blob) == secret


def test_encrypt_none_and_empty_roundtrip_as_none():
    # A NULL column is the honest representation of "no refresh token".
    assert crypto.encrypt(None) is None
    assert crypto.encrypt("") is None
    assert crypto.decrypt(None) is None
    assert crypto.decrypt("") is None


def test_encrypt_is_nondeterministic():
    # Fernet embeds a random IV, so identical plaintexts must not produce
    # identical ciphertext — otherwise the DB leaks "these two are the same".
    a, b = crypto.encrypt("same-token"), crypto.encrypt("same-token")
    assert a != b
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same-token"


def test_decrypt_with_wrong_key_fails_closed(monkeypatch):
    blob = crypto.encrypt("secret-token")
    crypto._fernet.cache_clear()
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(crypto.CredentialCryptoError):
        crypto.decrypt(blob)
    crypto._fernet.cache_clear()


def test_missing_key_fails_closed_never_plaintext(monkeypatch):
    crypto._fernet.cache_clear()
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "")
    assert crypto.crypto_available() is False
    with pytest.raises(crypto.CredentialCryptoError):
        crypto.encrypt("would-have-been-plaintext")
    crypto._fernet.cache_clear()


def test_redact_never_exposes_token_head():
    assert crypto.redact("supersecrettoken1234") == "********1234"
    assert crypto.redact("") == "<none>"
    assert "supersecret" not in crypto.redact("supersecrettoken1234")


# ── status derivation (the dashboard's single source of truth) ───────────────

class _Row:
    def __init__(self, expires_at=None, needs_reconnect=False):
        self.expires_at = expires_at
        self.needs_reconnect = needs_reconnect


def test_status_derivation_covers_every_state():
    now = int(time.time())
    assert _derive_status(None, now)[0] == "disconnected"
    assert _derive_status(_Row(needs_reconnect=True), now)[0] == "needs_reconnect"
    assert _derive_status(_Row(expires_at=None), now)[0] == "connected"
    assert _derive_status(_Row(expires_at=now - 60), now)[0] == "expired"
    assert _derive_status(_Row(expires_at=now + 3600), now)[0] == "expiring"
    assert _derive_status(_Row(expires_at=now + 30 * 86400), now)[0] == "connected"


def test_expiring_window_boundary():
    now = int(time.time())
    inside = now + EXPIRING_WINDOW_DAYS * 86400 - 60
    outside = now + EXPIRING_WINDOW_DAYS * 86400 + 60
    assert _derive_status(_Row(expires_at=inside), now)[0] == "expiring"
    assert _derive_status(_Row(expires_at=outside), now)[0] == "connected"


def test_needs_reconnect_outranks_a_valid_expiry():
    # A credential we cannot renew is NOT "connected" just because its clock
    # hasn't run out — that would hide a broken rail behind a green dot.
    now = int(time.time())
    row = _Row(expires_at=now + 30 * 86400, needs_reconnect=True)
    assert _derive_status(row, now)[0] == "needs_reconnect"


# ── provider registry contract ───────────────────────────────────────────────

def test_all_five_platforms_registered_and_ordered():
    assert set(PROVIDERS) == {"twitter", "reddit", "instagram", "tiktok", "pinterest"}
    assert set(PLATFORM_ORDER) == set(PROVIDERS)
    assert len(PLATFORM_ORDER) == 5


def test_every_provider_declares_a_complete_spec():
    for key in PLATFORM_ORDER:
        p = get_provider(key)
        assert p.authorize_url.startswith("https://"), key
        assert p.token_url.startswith("https://"), key
        assert p.scopes, key
        assert p.mode in ("oneclick", "manual"), key
        assert p.client_auth in ("basic", "body"), key


def test_reddit_requests_permanent_duration():
    # Without duration=permanent Reddit returns no refresh token and the
    # connection silently dies in one hour, forever.
    assert PROVIDERS["reddit"].extra_authorize_params.get("duration") == "permanent"


def test_twitter_requests_offline_access():
    # offline.access is what makes X refreshable at all.
    assert "offline.access" in PROVIDERS["twitter"].scopes


# ── PKCE + authorize URL construction ────────────────────────────────────────

def test_pkce_pair_is_valid_s256():
    import base64, hashlib
    verifier, challenge = oauth_flow.make_pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    assert challenge == expected
    assert "=" not in challenge          # must be unpadded per RFC 7636


def test_pkce_pairs_are_unique():
    pairs = {oauth_flow.make_pkce_pair()[0] for _ in range(50)}
    assert len(pairs) == 50


def test_authorize_url_carries_state_and_challenge():
    from urllib.parse import urlparse, parse_qs
    p = get_provider("twitter")
    verifier, challenge = oauth_flow.make_pkce_pair()
    url = oauth_flow.build_authorize_url(
        p, client_id="CID", redirect_uri="https://x.test/cb",
        state="STATE123", code_challenge=challenge,
    )
    q = parse_qs(urlparse(url).query)
    assert q["state"] == ["STATE123"]
    assert q["code_challenge"] == [challenge]
    assert q["code_challenge_method"] == ["S256"]
    assert q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["https://x.test/cb"]


def test_tiktok_uses_client_key_not_client_id():
    from urllib.parse import urlparse, parse_qs
    url = oauth_flow.build_authorize_url(
        get_provider("tiktok"), client_id="CK", redirect_uri="https://x.test/cb",
        state="S", code_challenge="C",
    )
    q = parse_qs(urlparse(url).query)
    assert q.get("client_key") == ["CK"]
    assert "client_id" not in q


# ── error scrubbing (no token ever reaches a stored error or a log) ──────────

def test_scrub_strips_token_material_from_provider_errors():
    dirty = 'error: {"access_token":"SECRETVALUE123","x":1}'
    clean = oauth_flow._scrub(dirty)
    assert "SECRETVALUE123" not in clean
    assert "redacted" in clean


def test_expiry_normalization():
    now = int(time.time())
    out = oauth_flow.expires_at_from({"expires_in": 7200})
    assert out is not None and abs(out - (now + 7200)) <= 2
    assert oauth_flow.expires_at_from({}) is None
    assert oauth_flow.expires_at_from({"expires_in": None}) is None


# ── frontend/backend contract ────────────────────────────────────────────────

def test_status_enum_matches_frontend_types():
    """The five status strings the UI switches on. Adding a sixth here without
    updating lib/types.ts would make the dashboard render an unstyled state."""
    from pathlib import Path
    types = Path(__file__).parents[2] / "frontend" / "lib" / "types.ts"
    if not types.exists():
        pytest.skip("frontend not present")
    src = types.read_text()
    for status in ("connected", "expiring", "expired", "needs_reconnect", "disconnected"):
        assert f'"{status}"' in src, f"ConnectionStatus missing {status}"
    for platform in PLATFORM_ORDER:
        assert f'"{platform}"' in src, f"ConnectPlatform missing {platform}"
