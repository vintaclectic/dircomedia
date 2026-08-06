"""OAuth 1.0a signature correctness for the X rail.

These tests exist because a signature bug is *silent*: the code looks right,
the request is well-formed, and X simply answers 401 — so a broken media
upload reads as "X is down" rather than "we signed it wrong". The media
upload path was in exactly that state (form params omitted from the base
string) and nothing caught it.

Signatures are verified against RFC 5849 by recomputing them independently,
so these pass or fail without touching the network.
"""
import base64
import hashlib
import hmac
import urllib.parse

import pytest

from app.services.distribution.platforms.twitter import TwitterClient


CONSUMER_KEY = "test_consumer_key"
CONSUMER_SECRET = "test_consumer_secret"
ACCESS_TOKEN = "test_access_token"
ACCESS_SECRET = "test_access_secret"


@pytest.fixture
def client(monkeypatch):
    tw = TwitterClient()
    tw.api_key = CONSUMER_KEY
    tw.api_secret = CONSUMER_SECRET
    tw.access_token = ACCESS_TOKEN
    tw.access_secret = ACCESS_SECRET
    return tw


def parse_auth_header(header: str) -> dict:
    """Turn `OAuth k="v", k2="v2"` into a dict of decoded values."""
    assert header.startswith("OAuth ")
    out = {}
    for part in header[len("OAuth "):].split(", "):
        k, _, v = part.partition("=")
        out[k] = urllib.parse.unquote(v.strip('"'))
    return out


def expected_signature(method: str, url: str, all_params: dict) -> str:
    """Independently recompute the RFC 5849 signature."""
    def enc(s):
        return urllib.parse.quote(str(s), safe="")

    norm = "&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(all_params.items()))
    base = f"{method.upper()}&{enc(url)}&{enc(norm)}"
    key = f"{enc(CONSUMER_SECRET)}&{enc(ACCESS_SECRET)}"
    return base64.b64encode(
        hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    ).decode()


def test_signature_includes_form_params(client):
    """The regression: form fields MUST be folded into the signature base.

    Signing INIT without command/total_bytes/media_type produces a signature
    X computes differently, so every media upload 401s.
    """
    url = "https://upload.twitter.com/1.1/media/upload.json"
    form = {
        "command": "INIT",
        "total_bytes": "12345",
        "media_type": "video/mp4",
        "media_category": "tweet_video",
    }
    header = client._oauth_headers("POST", url, params=form, json_body=False)
    got = parse_auth_header(header["Authorization"])

    oauth_only = {k: v for k, v in got.items() if k != "oauth_signature"}
    # Signing with the form params must match; signing without must NOT.
    assert got["oauth_signature"] == expected_signature("POST", url, {**oauth_only, **form})
    assert got["oauth_signature"] != expected_signature("POST", url, oauth_only)


def test_signature_includes_query_params(client):
    """Query params count toward the base string exactly like form fields."""
    url = "https://api.twitter.com/2/users/me"
    params = {"user.fields": "public_metrics"}
    header = client._oauth_headers("GET", url, params=params)
    got = parse_auth_header(header["Authorization"])

    oauth_only = {k: v for k, v in got.items() if k != "oauth_signature"}
    assert got["oauth_signature"] == expected_signature("GET", url, {**oauth_only, **params})


def test_json_body_is_not_signed(client):
    """A JSON body is excluded from the base string — only oauth_* are signed."""
    url = "https://api.twitter.com/2/tweets"
    header = client._oauth_headers("POST", url)
    got = parse_auth_header(header["Authorization"])

    oauth_only = {k: v for k, v in got.items() if k != "oauth_signature"}
    assert got["oauth_signature"] == expected_signature("POST", url, oauth_only)
    assert header["Content-Type"] == "application/json"


def test_form_requests_omit_json_content_type(client):
    """httpx must set multipart/urlencoded itself (with its boundary).

    Forcing application/json on a form post makes X reject the body.
    """
    url = "https://upload.twitter.com/1.1/media/upload.json"
    header = client._oauth_headers("POST", url, params={"command": "STATUS"}, json_body=False)
    assert "Content-Type" not in header


def test_required_oauth_fields_present(client):
    url = "https://api.twitter.com/2/tweets"
    got = parse_auth_header(client._oauth_headers("POST", url)["Authorization"])
    for field in (
        "oauth_consumer_key", "oauth_nonce", "oauth_signature_method",
        "oauth_timestamp", "oauth_token", "oauth_version", "oauth_signature",
    ):
        assert field in got, f"missing {field}"
    assert got["oauth_signature_method"] == "HMAC-SHA1"
    assert got["oauth_version"] == "1.0"
    assert got["oauth_consumer_key"] == CONSUMER_KEY
    assert got["oauth_token"] == ACCESS_TOKEN


def test_nonce_is_unique_per_request(client):
    """A replayed nonce lets X reject the second request as a duplicate."""
    url = "https://api.twitter.com/2/tweets"
    nonces = {
        parse_auth_header(client._oauth_headers("POST", url)["Authorization"])["oauth_nonce"]
        for _ in range(25)
    }
    assert len(nonces) == 25
