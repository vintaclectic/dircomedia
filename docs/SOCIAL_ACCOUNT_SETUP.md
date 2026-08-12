# SOCIAL ACCOUNT SETUP — the connection wizard

**Task YH9AE4D · Path A (owner-only) · 2026-08-12**

This is the run-through for connecting DirCo's social accounts to the broadcast
spine. Follow it top to bottom once; after that the wizard maintains itself and
you only come back when something goes red.

**Time to first live post: ~15 minutes** (X alone: ~5).

---

## THE ONE THING TO UNDERSTAND FIRST

Most people wire five platforms, see five green lights, and assume they're
posting. Green means *the token is valid*, not *the post went out*. Those are
different claims and the gap between them is where automated posting silently
dies for weeks.

So this system separates three things that are easy to conflate:

| Layer | What it is | Where it lives |
|---|---|---|
| **App credentials** | The developer app (client ID + secret). One per platform, shared by all DirCo brands. | `.env` |
| **Account token** | The token that proves *you* authorized that app to post as your account. | `platform_credentials` (encrypted) |
| **Brand voice** | Which DirCo app a given post *sounds like*. | `brand_configs/*.yaml` |

**You connect ONE social account per platform.** You do not connect seven X
accounts for seven apps. The DirCo account posts, and the `project` slug on each
broadcast picks the voice it posts in. That's why `brand_configs/` has seven
files and the credential vault has one row per platform.

If you ever *do* want a dedicated @handle per app, the vault's
`UNIQUE(platform, account_id)` already allows multiple rows per platform — no
migration needed. That's Path B.

---

## STEP 0 — the encryption key (do this first, once)

Every stored token is Fernet-encrypted at rest. If the key is missing the wizard
**refuses to store anything** rather than writing a plaintext token to disk.

Check it:

```bash
cd /home/vinta/dircomedia/backend
grep -q '^CREDENTIAL_ENCRYPTION_KEY=.\+' .env && echo "KEY PRESENT" || echo "KEY MISSING"
```

If missing, generate and paste it into `backend/.env`:

```bash
./.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```dotenv
CREDENTIAL_ENCRYPTION_KEY=<paste the key>
```

> **Rotating this key invalidates every stored credential.** You'd reconnect all
> platforms. Set it once and leave it alone.

---

## STEP 1 — start the backend

```bash
cd /home/vinta/dircomedia/backend
./.venv/bin/python -m uvicorn app.main:app --port 8000
```

Confirm encryption is live (the wizard reads this before it will save anything):

```bash
TOK=$(grep -E '^OWNER_API_TOKEN=' backend/.env | cut -d= -f2-)
curl -s -H "X-Owner-Token: $TOK" http://127.0.0.1:8000/api/v1/oauth/encryption-status
# {"configured":true}
```

Every `/api/v1/oauth/*` route is owner-guarded and **fails closed** — no token,
`401`, no exceptions.

---

## STEP 2 — open the wizard

```bash
cd /home/vinta/dircomedia/frontend && npm run dev
```

| Page | URL | Use |
|---|---|---|
| **Wizard** | `http://localhost:3000/setup/connect` | First-time run-through |
| **Per-platform** | `/setup/connect/[platform]` | One platform, step by step |
| **Connections rail** | `/settings/connections` | Ongoing health, reconnects |

`OAUTH_REDIRECT_BASE` in `.env` **must exactly match** the callback URL you
register with each developer portal, scheme and port included. A trailing slash
mismatch is a rejected redirect.

---

## STEP 3 — connect each platform

Two lanes, because the platforms genuinely differ:

- **One-click** (X, Reddit, Pinterest) — full OAuth round trip in a popup.
- **Paste-a-token** (Instagram, TikTok) — these require app review or a
  Facebook Page link before they'll issue a posting token, so you mint it in
  the platform's own tool and paste it in.

Pasted tokens are **probed against the live API before they're stored.** A
wizard that accepts a bad paste and says "connected" is worse than one that
rejects it, because the failure resurfaces days later as a missed post.

### X / Twitter — start here

Highest reach, and the only platform the auto-tap posts to today.

1. <https://developer.x.com/en/portal/dashboard> → your app → **User authentication settings**
2. Set **App permissions: Read and write** ← *the single most common failure.*
   Miss this and OAuth succeeds, the token stores, the health rail goes green,
   and every post returns 403. If posting 403s, this is why.
3. **Type of App:** Web App / Automated App
4. **Callback URI:** `http://localhost:8000/api/v1/oauth/twitter/callback`
5. Copy **Client ID** + **Client Secret** → paste into the wizard's X card
6. Click **Connect** → authorize → the popup returns you connected

> If you changed permissions *after* connecting, the old token keeps the old
> scopes. Disconnect and reconnect — the permission is baked into the token.

### Reddit

1. <https://www.reddit.com/prefs/apps> → **create app**
2. Choose **web app** — *not* "script". A script app returns `invalid_grant` on
   token exchange, which reads like a bad secret and costs you an hour.
3. **redirect uri:** `http://localhost:8000/api/v1/oauth/reddit/callback`
4. Paste client ID + secret into the wizard → **Connect**

> The current stored Reddit row is flagged `needs_reconnect`: the existing
> `REDDIT_CLIENT_ID`/`SECRET` are invalid, revoked, or from a deleted app. No
> code change fixes that — create a fresh **web app** and reconnect. Note this
> blocks *automated* posting only.

### Pinterest

1. <https://developers.pinterest.com/apps/> → create app → request `pins:write`
2. **Redirect URI:** `http://localhost:8000/api/v1/oauth/pinterest/callback`
3. Paste `PINTEREST_APP_ID` / `PINTEREST_APP_SECRET` → **Connect**

### Instagram (paste-a-token)

Requires a **Business or Creator** account linked to a Facebook Page.

1. <https://developers.facebook.com/tools/explorer/>
2. Permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`
3. Generate the token, then **exchange it for a long-lived (60-day) token**
4. Paste into the wizard's Instagram card

> Instagram has **no refresh token.** The 60-day token is renewed by
> re-exchange, which the refresh worker handles — but if it lapses you reconnect
> by hand. The rail warns you before expiry.

### TikTok (paste-a-token)

1. <https://developers.tiktok.com/> → create app → **Content Posting API**
2. Requires app review before it will issue a posting scope
3. Paste the access token into the wizard's TikTok card

---

## STEP 4 — prove it actually posts

Do all three. Each one rules out a different failure.

**1. Token is valid** (per-platform card → **Test Connection**, or):

```bash
TOK=$(grep -E '^OWNER_API_TOKEN=' backend/.env | cut -d= -f2-)
curl -s -X POST -H "X-Owner-Token: $TOK" \
  http://127.0.0.1:8000/api/v1/oauth/twitter/test
# {"ok":true,"platform":"twitter","account_name":"<your handle>"}
```

If this returns `Unsupported Authentication` or `403`, the token is app-only or
lacks write permission — revisit Step 3's permission note.

**2. The spine accepts a candidate** — approve-first, so nothing goes public:

```bash
node /home/vinta/vintinuum-api/broadcast.js \
  --project vintinuum --kind update \
  --title "Connection test" \
  --body "Testing the DirCoMedia broadcast spine." \
  --platforms twitter --mode approve-first

node /home/vinta/vintinuum-api/broadcast.js --pending
```

**3. Approve it** in `/approvals` and confirm it lands on the account. Until you
approve, nothing is public — that's the whole design.

---

## HOW A POST ACTUALLY REACHES X

```
Work Journal row (Notes: "BROADCAST: ...")
  └─ broadcast.js --tap        sweeps notes into candidates
      └─ POST /api/v1/broadcast   (approve-first — queued, NOT posted)
          └─ /approvals             ← you approve here
              └─ DistributionScheduler.post()
                  └─ TwitterClient.from_vault()   ← wizard token wins over .env
                      └─ POST /2/tweets
```

**The vault takes precedence over `.env` on the posting path.** This was the gap
this build closed: the health rail already read the vault, but the *poster* only
read `.env`, so a wizard-connected account showed green and never posted.

The credential switch matters because the two lanes aren't interchangeable — the
wizard mints **OAuth 2.0 user tokens** (`Bearer`), while `.env` holds **OAuth
1.0a** consumer keys (HMAC-SHA1 signature). Sign one as the other and X returns
a 401 that reads like a bad key, sending you to rotate credentials that were
never wrong. `TwitterClient` picks the right mode automatically and reports
which it used via `credential_source` (`oauth_wizard` | `env`).

The client is rebound from the vault **per post**, not at startup, so a
reconnect takes effect on the very next send rather than the next restart. If
the vault is empty or unreadable it falls back to `.env` — degrading beats
taking the poster down.

---

## TROUBLESHOOTING

| Symptom | Cause | Fix |
|---|---|---|
| `401` on any `/api/v1/oauth/*` | Missing/wrong owner token | Send `X-Owner-Token` from `.env` |
| `503 refusing to store a credential in plaintext` | No encryption key | Step 0 |
| Redirect rejected by platform | `OAUTH_REDIRECT_BASE` ≠ registered URI | Match them exactly, incl. port + slash |
| `invalid_grant` on Reddit | App is type "script" | Create a **web** app |
| OAuth works, posting 403s | App lacks **Read and write** | Fix permission, then **disconnect + reconnect** |
| "Connection failed" page after authorize | Expired/replayed CSRF state (600s TTL) | Just start the flow again |
| Card green but nothing posts | Candidate never approved | Check `/approvals` |
| Instagram stops after ~60 days | Long-lived token lapsed | Re-mint and paste |

**Security properties worth knowing:** tokens are Fernet-encrypted at rest and
never logged; CSRF `state` is single-use, persisted (survives reload and
multi-worker), and expires in 600s; X/TikTok use **PKCE S256**, so a stolen
authorization code is not redeemable by anyone else; every route fails closed.

---

## DAY-TO-DAY

- **`/settings/connections`** is the rail to watch. Red = act; it tells you
  whether a token expired on its own (worker will retry) or needs you.
- The refresh worker renews tokens before expiry. `needs_reconnect` means it
  gave up and it's on you.
- **approve-first is the default and stays that way.** `auto` mode is per
  project/platform and only when you say so.
- **Never commit `backend/.env`.** It holds every secret here and is gitignored.

---

## FILE MAP

| Path | Role |
|---|---|
| `backend/app/api/v1/oauth.py` | All 8 wizard endpoints |
| `backend/app/services/oauth/providers.py` | Per-platform specs — **add a platform here** |
| `backend/app/services/oauth/flow.py` | PKCE, token exchange, probes |
| `backend/app/services/oauth/store.py` | Encrypted read/write |
| `backend/app/services/oauth/refresh.py` | Auto-refresh worker |
| `backend/app/core/crypto.py` | Fernet, fail-closed |
| `backend/app/models/credential.py` | Vault + CSRF state schema |
| `backend/app/services/distribution/platforms/twitter.py` | `from_vault()` posting path |
| `frontend/app/setup/connect/` | The wizard |
| `frontend/app/settings/connections/` | Health rail |

Adding a sixth platform is a dict entry in `providers.py` — not a new endpoint.
