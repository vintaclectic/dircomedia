#!/usr/bin/env python3
"""
youtube_auth.py — one-time YouTube refresh-token minter (task TA3SQSM).

Mirrors scripts/reddit_oauth.py: you click "allow" in a browser, this catches
the redirect on localhost, exchanges the code, and prints the exact .env line
to paste. Nothing is written automatically — by design, so the token is
reviewed before it lands in a credentials file.

PREREQUISITE (one time, ~2 minutes — docs/PLATFORM_CONNECTIONS.md §5):
  1. https://console.cloud.google.com → create project `dircomedia`
  2. APIs & Services → Enable APIs → enable **YouTube Data API v3**
  3. OAuth consent screen → External → add yourself as a Test user
     ⚠ IMPORTANT: in *Testing* mode refresh tokens expire every 7 days. Click
       **PUBLISH APP** on the consent screen to get a permanent token. The
       "unverified app" warning is irrelevant — you are the only user who will
       ever consent, and you just click "Advanced → Go to dircomedia".
  4. Credentials → Create OAuth client ID → **Desktop app** → copy the
     client ID + secret into backend/.env as:
         YOUTUBE_CLIENT_ID=...
         YOUTUBE_CLIENT_SECRET=...

THEN RUN (from dircomedia/backend):
    ./.venv/bin/python scripts/youtube_auth.py

Scopes requested:
  youtube.upload    — insert videos (the whole point)
  youtube.force-ssl — set thumbnails, edit metadata after upload
"""
import http.server
import secrets
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
PORT = 8731  # uncommon port — avoids colliding with the API on 8000
REDIRECT_URI = f"http://localhost:{PORT}/oauth/youtube/callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.force-ssl"
)

_captured: dict = {}


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/oauth/youtube/callback"):
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        _captured.update({k: v[0] for k, v in params.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = "code" in _captured
        self.wfile.write(
            (
                "<html><body style='font-family:system-ui;background:#0b0b0f;"
                "color:#e8e8f0;display:flex;align-items:center;justify-content:center;"
                "height:100vh;margin:0'><div style='text-align:center'>"
                f"<h1 style='color:{'#5ee6a8' if ok else '#ff6b6b'}'>"
                f"{'YouTube connected.' if ok else 'Authorization failed.'}</h1>"
                "<p>Return to the terminal.</p></div></body></html>"
            ).encode()
        )

    def log_message(self, *args):  # silence the default stderr spam
        pass


def main() -> int:
    env = load_env(ENV_PATH)
    client_id = env.get("YOUTUBE_CLIENT_ID", "")
    client_secret = env.get("YOUTUBE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print(
            "\n  YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET are empty in\n"
            f"  {ENV_PATH}\n\n"
            "  Do the 2-minute Google Cloud setup in this file's docstring\n"
            "  (or docs/PLATFORM_CONNECTIONS.md §5), paste the two values,\n"
            "  then re-run this script.\n",
            file=sys.stderr,
        )
        return 2

    state = secrets.token_urlsafe(24)
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",       # required to get a refresh token
            "prompt": "consent",            # forces a NEW refresh token every run
            "state": state,
            "include_granted_scopes": "true",
        }
    )
    url = f"{AUTH_URL}?{query}"

    print("\n" + "=" * 72)
    print("  1. Open this URL and click Allow (choose Vinta's YouTube channel):\n")
    print(f"     {url}\n")
    print("     If Google warns 'app isn't verified' → Advanced → Go to dircomedia.")
    print(f"  2. Waiting for the redirect on {REDIRECT_URI} ...")
    print("=" * 72 + "\n")

    try:
        webbrowser.open(url)
    except Exception:
        pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        # 5 minutes is plenty for a human to click through Google's consent.
        for _ in range(300):
            if _captured:
                break
            threading.Event().wait(1)
        httpd.shutdown()

    if "code" not in _captured:
        print(
            f"  No authorization code received. Error: {_captured.get('error', 'timeout')}",
            file=sys.stderr,
        )
        return 1
    if _captured.get("state") != state:
        print("  State mismatch — aborting (possible CSRF).", file=sys.stderr)
        return 1

    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": _captured["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"  Token exchange failed: {resp.text[:400]}", file=sys.stderr)
        return 1

    data = resp.json()
    refresh = data.get("refresh_token")
    if not refresh:
        print(
            "  Google returned no refresh_token. This happens when the account\n"
            "  already granted consent — re-run (prompt=consent is set, which\n"
            "  should force a new one), or revoke access at\n"
            "  https://myaccount.google.com/permissions and try again.",
            file=sys.stderr,
        )
        return 1

    print("\n" + "=" * 72)
    print("  SUCCESS — paste this line into dircomedia/backend/.env:\n")
    print(f"YOUTUBE_REFRESH_TOKEN={refresh}\n")
    print("  Then verify with:")
    print("    ./.venv/bin/python scripts/youtube_test_upload.py --health")
    print("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
