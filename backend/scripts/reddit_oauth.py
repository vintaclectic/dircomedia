#!/usr/bin/env python3
"""
reddit_oauth.py — FALLBACK Reddit refresh-token minter (NO PASSWORD EVER).

╔══════════════════════════════════════════════════════════════════════════════╗
║  READ THIS FIRST: THE DASHBOARD IS THE HAPPY PATH, NOT THIS SCRIPT.          ║
║                                                                              ║
║  The app has a real OAuth wizard that does everything below with one click   ║
║  and stores the refresh token ENCRYPTED in the credential vault (this script ║
║  can only print a value for you to paste into .env by hand):                 ║
║                                                                              ║
║      GET /api/v1/oauth/reddit/start   → returns the authorize URL            ║
║      (Reddit redirects back to /api/v1/oauth/reddit/callback, which           ║
║       exchanges the code and persists the token automatically)               ║
║                                                                              ║
║  Use this script ONLY when the browser cannot reach the callback host —       ║
║  e.g. the API is bound to a localhost the browser can't see.                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Why a token flow at all: Vinta's Reddit account uses Google login, so it has no
password — the password grant cannot authenticate it. The 3-legged "authorize"
flow works regardless of how you log in and (with duration=permanent) yields a
refresh token.

THE REDIRECT URI IS NOT CONFIGURABLE HERE, AND THAT IS THE POINT.
It is derived from the app's live route table via app.services.oauth.redirects,
so this script, the wizard, and the token exchange cannot disagree. On 2026-09-25
this script read REDDIT_REDIRECT_URI from .env, which pointed at
/oauth/reddit/callback — a path the app has never served (measured: 404, while
/api/v1/oauth/reddit/callback returned 200). Reddit requires the redirect_uri on
token exchange to byte-match the app's registered URI, so that mismatch broke the
exchange on its own. Deriving the value removes the failure mode entirely.

USAGE (from dircomedia/backend):
    ./.venv/bin/python scripts/reddit_oauth.py
"""
import base64
import secrets
import sys
import urllib.parse
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"
# Import the app package so the redirect URI comes from ONE place.
sys.path.insert(0, str(BACKEND_DIR))


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


def canonical_uri() -> str:
    """The redirect URI, from the app's own single source of truth.

    Falls back to the module's documented template only if the app package
    cannot be imported at all, and says so loudly rather than silently using a
    different string than the server would.
    """
    try:
        from app.services.oauth.redirects import canonical_redirect_uri
        return canonical_redirect_uri("reddit")
    except Exception as exc:
        print(f"WARNING: could not import the app's redirect module "
              f"({exc.__class__.__name__}); falling back to the documented path.")
        env = load_env(ENV_PATH)
        base = (env.get("OAUTH_REDIRECT_BASE") or "http://localhost:8000").rstrip("/")
        return f"{base}/api/v1/oauth/reddit/callback"


def extract_code(raw: str) -> tuple[str | None, str | None]:
    """(code, problem). Returns the authorization code, or an HONEST diagnosis.

    THE BUG THIS REPLACES: the old version did
        code = (params.get("code") or [raw])[0]
    so when you pasted the AUTHORIZE url (which contains the literal substring
    'response_type=code', satisfying its `"code=" in raw` guard but having no
    `code` PARAMETER), it fell back to using THE ENTIRE URL as the authorization
    code, POSTed that, got an inevitable 401, and then blamed your app type.
    Verified 2026-09-25: that fallback produced a 199-char 'code'.

    A parser must never invent a value it did not find.
    """
    raw = (raw or "").strip()
    if not raw:
        return None, "You pasted nothing."

    # Reddit sometimes appends '#_' to the redirected URL.
    if "?" in raw:
        qs = urllib.parse.urlparse(raw).query or raw.split("?", 1)[-1]
        params = urllib.parse.parse_qs(qs)
    else:
        params = urllib.parse.parse_qs(raw) if "=" in raw else {}

    err = (params.get("error") or [None])[0]
    if err:
        if err == "access_denied":
            return None, ("Reddit says access_denied — you clicked Decline (or "
                          "the Allow never registered). Re-run and click Allow.")
        return None, f"Reddit returned an error in the URL: {err}"

    code = (params.get("code") or [None])[0]
    if code:
        return code.split("#", 1)[0].strip(), None

    # No `code` parameter. Diagnose WHY, precisely — never guess a value.
    if "/api/v1/authorize" in raw or "response_type=" in raw or "client_id=" in raw:
        return None, (
            "You pasted the AUTHORIZE URL, not the REDIRECTED URL.\n"
            "  That's the URL this script gave you to OPEN — not the one you end\n"
            "  up on after clicking Allow.\n"
            "  What to do: open it, click Allow, then look at your browser's\n"
            "  ADDRESS BAR. It will show a page that fails to load (that's\n"
            "  expected) whose URL contains '?code=' — copy THAT whole URL.\n"
            "  (Tell them apart: the authorize URL says 'response_type=code';\n"
            "   the redirected URL has an actual '&code=...' value in it.)"
        )
    if raw.startswith("http"):
        return None, (
            "That URL has no 'code=' parameter in it.\n"
            "  After clicking Allow, the address bar URL must contain '?code=' or\n"
            "  '&code='. If it contains 'error=access_denied' you clicked Decline."
        )
    # A bare token-looking string: accept it, but only because it is plausibly a
    # raw code and contains no URL structure to misread.
    if any(c in raw for c in " \t\n") or len(raw) > 512:
        return None, ("That doesn't look like an authorization code (it has "
                      "whitespace or is very long). Paste the full redirected URL.")
    return raw, None


def diagnose_exchange_failure(status: int, body: str, redirect_uri: str) -> str:
    """Map the ACTUAL Reddit response to its ACTUAL likely causes.

    The old version printed 'if this says invalid_grant or the app is a SCRIPT
    app, create a WEB app' on ANY non-200 — which is how a redirect-URI mismatch
    got misdiagnosed as an app-type problem. Evidence first, advice second.
    """
    low = (body or "").lower()
    lines = [f"\nToken exchange FAILED: HTTP {status}"]
    lines.append(f"Reddit said: {body[:300]}")
    lines.append(f"\nThe redirect_uri this script sent was:\n    {redirect_uri}")

    if status == 401:
        lines.append(
            "\nHTTP 401 on the token endpoint means Reddit rejected the REQUEST\n"
            "ITSELF (it is sent with HTTP Basic client_id:client_secret). The two\n"
            "causes worth checking, in order:\n"
            "  1. CLIENT CREDENTIALS — REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET do\n"
            "     not match the app at https://www.reddit.com/prefs/apps. The id is\n"
            "     the string UNDER the app name; the secret is the 'secret' field.\n"
            "  2. REDIRECT URI — the value above must be registered on that app\n"
            "     byte-for-byte (scheme, host, port, path, no trailing slash).\n"
            "     Copy/paste it; do not retype it."
        )
    if "invalid_grant" in low:
        lines.append(
            "\n'invalid_grant' means the CODE was rejected, not your credentials:\n"
            "  - the code already expired (they are short-lived — mint and paste\n"
            "    promptly; do not leave the tab sitting open),\n"
            "  - the code was already used once (they are SINGLE-USE — a second\n"
            "    attempt with the same code always fails; re-run from step 1), or\n"
            "  - the redirect_uri on this exchange differs from the one used on the\n"
            "    authorize request. Both must be identical AND registered."
        )
    if "unsupported_grant_type" in low:
        lines.append("\n'unsupported_grant_type' — the app type may not permit this "
                     "grant. THIS is the case where app type is actually implicated.")
    if status == 429:
        lines.append("\nHTTP 429 — rate limited. Wait and retry; nothing is misconfigured.")
    if status == 403:
        lines.append(
            "\nHTTP 403 — Reddit refused the request. Check that REDDIT_USER_AGENT is\n"
            "a descriptive custom string (Reddit blocks generic/default agents)."
        )
    lines.append("\nNothing above is an app-type problem unless Reddit explicitly "
                 "said so — do not go change your app type on a guess.")
    return "\n".join(lines)


def main():
    env = load_env(ENV_PATH)
    client_id = env.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = env.get("REDDIT_CLIENT_SECRET", "").strip()
    user_agent = env.get(
        "REDDIT_USER_AGENT", "web:com.dirco.media:v1.0 (by /u/dircomedia)"
    ).strip()
    redirect_uri = canonical_uri()

    if not client_id or not client_secret:
        print("ERROR: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET missing from", ENV_PATH)
        print("       Add them via the dashboard (Manual Setup) or in .env directly.")
        sys.exit(1)

    # Lengths only — never echo a credential value.
    print(f"\nUsing REDDIT_CLIENT_ID (len {len(client_id)}), "
          f"REDDIT_CLIENT_SECRET (len {len(client_secret)}).")
    print(f"Canonical redirect URI (derived from the app's routes):\n    {redirect_uri}")
    print("\nThis EXACT string must be registered on your app at "
          "https://www.reddit.com/prefs/apps")

    state = secrets.token_urlsafe(24)
    authorize_url = (
        "https://www.reddit.com/api/v1/authorize?"
        + urllib.parse.urlencode({
            "client_id": client_id,
            "response_type": "code",
            "state": state,
            "redirect_uri": redirect_uri,
            "duration": "permanent",  # the only way Reddit returns a refresh_token
            "scope": "submit identity read",
        })
    )

    print("\n" + "=" * 74)
    print("STEP 1 — open this URL in YOUR browser, log in (Google is fine),")
    print("         and click  ALLOW :\n")
    print(authorize_url)
    print("\n" + "-" * 74)
    print("STEP 2 — Reddit then sends your browser to a page that will NOT load.")
    print("         THAT IS EXPECTED. Look at your ADDRESS BAR: the URL contains")
    print("         '&code=...'. Copy that WHOLE redirected URL and paste it below.")
    print("\n         Do NOT paste the URL from step 1 — that one has no code in it.")
    print("         Authorization codes are SINGLE-USE and short-lived, so paste")
    print("         promptly and re-run from step 1 if an attempt fails.")
    print("=" * 74 + "\n")

    try:
        raw = input("Paste the REDIRECTED URL (the one containing code=): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNo input received. Re-run: ./.venv/bin/python scripts/reddit_oauth.py")
        sys.exit(1)

    code, problem = extract_code(raw)
    if problem:
        print(f"\n{'=' * 74}\nCANNOT PROCEED — {problem}\n{'=' * 74}\n")
        sys.exit(1)

    # State is advisory here (this script cannot see the browser's cookie), but a
    # mismatch is worth surfacing: it means the paste came from a different run.
    got_state = (urllib.parse.parse_qs(
        urllib.parse.urlparse(raw).query
    ).get("state") or [None])[0] if "?" in raw else None
    if got_state and got_state != state:
        print("\nNote: the state in that URL is from a DIFFERENT run of this script.")
        print("Continuing with the pasted code (it is still Reddit-issued), but if")
        print("the exchange fails, re-run from step 1 for a fresh code.")

    print("\nExchanging the authorization code for a refresh token…")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
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
    except httpx.HTTPError as exc:
        print(f"\nNetwork error talking to Reddit: {exc.__class__.__name__}: {exc}")
        sys.exit(1)

    if resp.status_code != 200:
        print(diagnose_exchange_failure(resp.status_code, resp.text, redirect_uri))
        sys.exit(1)

    body = resp.json()
    refresh = body.get("refresh_token")
    if not refresh:
        # Reported without dumping the body: it contains a live access_token.
        print("\nExchange succeeded but Reddit returned NO refresh_token.")
        print(f"Keys returned: {sorted(body.keys())}")
        print("duration=permanent was sent, so this is a Reddit-side refusal to")
        print("issue long-lived credentials for this app/account — check the app's")
        print("standing at https://www.reddit.com/prefs/apps before retrying.")
        sys.exit(1)

    print("\n" + "=" * 74)
    print("SUCCESS — paste this line into dircomedia/backend/.env "
          "(replace any existing one):\n")
    print(f"REDDIT_REFRESH_TOKEN={refresh}")
    print("\nThen: pm2 restart dircomedia-worker dircomedia-api")
    print("\nNOTE: the dashboard wizard stores this ENCRYPTED in the credential")
    print("vault instead of in plaintext .env — prefer it when the browser can")
    print("reach the callback URL.")
    print("=" * 74 + "\n")


if __name__ == "__main__":
    main()
