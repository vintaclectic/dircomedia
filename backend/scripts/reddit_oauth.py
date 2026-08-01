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
import secrets
import sys
import urllib.parse
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

    # ── HEADLESS-FRIENDLY paste-the-code flow ────────────────────────────────
    # This runs on a headless WSL server: there's no browser here, and the
    # redirect target (localhost:8000) is the SERVER's localhost, not your
    # Windows browser's — so a listener can't catch the redirect. Instead you
    # open the URL in YOUR browser, click Allow, and Reddit sends you to
    #   http://localhost:8000/oauth/reddit/callback?state=...&code=XXXXX
    # That page won't load (nothing serves it on your Windows box) — THAT'S FINE.
    # Just copy the whole redirected URL (or just the code=... value) from the
    # address bar and paste it back here.
    print("\n" + "=" * 72)
    print("STEP 1 — copy this URL, paste into YOUR browser, log in (Google is")
    print("fine), and click  ALLOW :\n")
    print(authorize_url)
    print("\n" + "-" * 72)
    print("STEP 2 — Reddit will redirect you to a 'localhost:8000' page that")
    print("does NOT load. That is expected. Copy the FULL redirected URL from")
    print("your address bar (it contains ...?state=...&code=...) and paste it")
    print("below. You can paste the whole URL or just the code value.")
    print("=" * 72 + "\n")

    try:
        raw = input("Paste the redirected URL (or the code) here: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNo input received. Re-run:  ./.venv/bin/python scripts/reddit_oauth.py")
        sys.exit(1)

    # Accept either a full URL or a bare code. Extract code + state if present.
    code = raw
    got_state = None
    if "code=" in raw or "state=" in raw:
        qs = urllib.parse.urlparse(raw).query or raw.split("?", 1)[-1]
        params = urllib.parse.parse_qs(qs)
        code = (params.get("code") or [raw])[0]
        got_state = (params.get("state") or [None])[0]
        err = (params.get("error") or [None])[0]
        if err:
            print(f"\nReddit returned an error in the URL: {err}")
            print("(access_denied = you clicked Decline; re-run and click Allow.)")
            sys.exit(1)
    # Reddit appends #_ to the code sometimes; strip trailing junk.
    code = code.split("#", 1)[0].strip()

    if got_state and got_state != state:
        print("\nNote: state in the URL doesn't match this run's state.")
        print("That's OK if you re-ran the script between opening the URL and pasting;")
        print("continuing with the pasted code.")
    if not code:
        print("\nNo code found in what you pasted. Re-run and paste the full redirected URL.")
        sys.exit(1)

    print("\nExchanging the authorization code for a refresh token…")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = httpx.post(
        "https://www.reddit.com/api/v1/access_token",
        data={
            "grant_type": "authorization_code",
            "code": code,
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
