#!/usr/bin/env python3
"""
reddit_oauth.py — one-time Reddit refresh-token minter (NO PASSWORD EVER).

Why this exists: Vinta's Reddit account uses Google login, so it has no
password — the password grant can't authenticate it. The 3-legged OAuth
"authorize" flow works regardless of how you log in and yields a permanent
refresh token we store as REDDIT_REFRESH_TOKEN.

REQUIREMENT: the Reddit app MUST be type **web app** (not "script").
Script apps cannot issue refresh tokens via authorize. If your existing app
is a script app, create one new web app at https://www.reddit.com/prefs/apps
(30 seconds) with redirect URI exactly:  http://localhost:8000/oauth/reddit/callback

USAGE (run from dircomedia/backend, venv active):
    ./.venv/bin/python scripts/reddit_oauth.py

It will:
  1. print an authorize URL — open it, click "allow" (this is where Google
     login happens; no password is ever typed into our code),
  2. Reddit redirects to http://localhost:8000/oauth/reddit/callback?code=...&state=...
     — this tiny script runs a throwaway localhost:8000 listener to catch it,
  3. exchange the code for a refresh_token and print the exact line to paste
     into dircomedia/backend/.env.

Reads REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_REDIRECT_URI / REDDIT_USER_AGENT
from .env (same file the app uses). Nothing is written automatically — it
prints the value for you to review and paste, by design.
"""
import base64
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main():
    env = load_env(ENV_PATH)
    client_id = env.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = env.get("REDDIT_CLIENT_SECRET", "").strip()
    redirect_uri = env.get("REDDIT_REDIRECT_URI", "http://localhost:8000/oauth/reddit/callback").strip()
    user_agent = env.get("REDDIT_USER_AGENT", "web:com.dirco.media:v1.0 (by /u/dircomedia)").strip()

    if not client_id or not client_secret:
        print("ERROR: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET missing from", ENV_PATH)
        print("       (you can reuse the DirHaven app's id+secret, but that app must be a WEB app for this flow.)")
        sys.exit(1)

    # Parse the redirect URI so the listener binds the right host/port/path.
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000
    cb_path = parsed.path or "/oauth/reddit/callback"

    state = secrets.token_urlsafe(24)
    scopes = "submit identity read"  # submit = post; identity = whoami; read = sanity
    authorize_url = (
        "https://www.reddit.com/api/v1/authorize?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "state": state,
                "redirect_uri": redirect_uri,
                "duration": "permanent",  # permanent = we get a refresh_token
                "scope": scopes,
            }
        )
    )

    caught = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.urlparse(self.path)
            if q.path != cb_path:
                self.send_response(404)
                self.end_headers()
                return
            params = urllib.parse.parse_qs(q.query)
            caught["code"] = (params.get("code") or [None])[0]
            caught["state"] = (params.get("state") or [None])[0]
            caught["error"] = (params.get("error") or [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = (
                "<h2>Reddit authorization received — you can close this tab.</h2>"
                if caught.get("code")
                else f"<h2>Authorization failed: {caught.get('error')}</h2>"
            )
            self.wfile.write(f"<html><body style='font-family:sans-serif'>{msg}</body></html>".encode())

        def log_message(self, *a):
            pass  # quiet

    # NOTE: the DirCoMedia API also uses :8000. Stop it first if it's running,
    # OR run this on a machine where :8000 is free. This listener needs the port
    # only for the ~30 seconds of the OAuth round-trip.
    try:
        server = http.server.HTTPServer((host, port), Handler)
    except OSError as e:
        print(f"ERROR: cannot bind {host}:{port} — is the DirCoMedia API using it? ({e})")
        print(f"       Temporarily: pm2 stop dircomedia-api, run this, then pm2 start dircomedia-api.")
        sys.exit(1)

    print("\n" + "=" * 72)
    print("STEP 1 — open this URL, log in (Google is fine), click ALLOW:\n")
    print(authorize_url)
    print("\n(Trying to open it in your browser automatically…)")
    print("=" * 72 + "\n")
    try:
        webbrowser.open(authorize_url)
    except Exception:
        pass

    print(f"Listening on {host}:{port}{cb_path} for the redirect…")
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    t.join(timeout=300)  # 5 min to click allow
    server.server_close()

    if caught.get("error"):
        print(f"\nAuthorization denied/failed: {caught['error']}")
        sys.exit(1)
    if not caught.get("code"):
        print("\nTimed out waiting for the redirect (5 min). Re-run and click ALLOW faster.")
        sys.exit(1)
    if caught.get("state") != state:
        print("\nSTATE MISMATCH — possible CSRF, aborting. Re-run.")
        sys.exit(1)

    print("\nGot the authorization code — exchanging it for a refresh token…")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = httpx.post(
        "https://www.reddit.com/api/v1/access_token",
        data={
            "grant_type": "authorization_code",
            "code": caught["code"],
            "redirect_uri": redirect_uri,
        },
        headers={"Authorization": f"Basic {basic}", "User-Agent": user_agent},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"\nToken exchange failed: HTTP {resp.status_code}: {resp.text[:300]}")
        print("If this says 'invalid_grant' or the app is a SCRIPT app, create a WEB app at")
        print("https://www.reddit.com/prefs/apps with redirect", redirect_uri)
        sys.exit(1)

    body = resp.json()
    refresh = body.get("refresh_token")
    if not refresh:
        print("\nNo refresh_token in response (did you use duration=permanent? is the app a web app?):")
        print(body)
        sys.exit(1)

    print("\n" + "=" * 72)
    print("SUCCESS — paste this line into dircomedia/backend/.env (replace any existing one):\n")
    print(f"REDDIT_REFRESH_TOKEN={refresh}")
    print("\nThen: pm2 restart dircomedia-worker dircomedia-api")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
