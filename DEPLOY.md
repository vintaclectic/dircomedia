# DirCoMedia — Deploy & Operations

**Task U6PAFU2 · Scope A (minimal backend only) · last verified 2026-08-14**

The owner-only marketing OS. Queues posts for every connected social account and
posts them **only after Vinta approves**. This document is the operational truth
for running it.

> ⚠️ **STATUS CORRECTION (2026-08-19, task W84PNK2):** this document's
> "healthy / SHIPPED" rows were measured on 2026-08-17 and are **stale**.
> As of 2026-08-19 the entire stack is **down**: zero `dircomedia-*` PM2
> processes, ports 4600/4601/8000 dead, and
> `https://dircomedia.vintaclectic.com` returning **502**. The hostname and
> tunnel are still correct — there is simply no origin behind them.
> Note also that `https://dircomedia.com` returning 200 is a **GoDaddy
> parked page**, not this app; it has never been routed here.

> **Scope A, as approved:** the **API** is the public surface; the **dashboard
> stays LOCAL** (`http://127.0.0.1:4600`). Nothing about the dashboard is
> published until that is explicitly changed.

---

## 0. Status at a glance

| Piece | State | Evidence |
|---|---|---|
| FastAPI backend (`:8000`) | ✅ **healthy** (fixed 2026-08-17, SKD4JWF) | `GET /health` → `200 {"status":"ok"}`. **Was crash-looping 982×** — `ProcessedContent.metadata` is a SQLAlchemy-reserved attribute and killed api+worker at import. Fixed via `content_metadata = Column("metadata", …)` (DB column unchanged, no migration). |
| Owner auth | ✅ **fail-closed** | `/api/v1/broadcast/pending` → **401** without token, **200** with |
| X (Twitter) credentials | ✅ **all 5 present** | canonical `TWITTER_*` keys set in `backend/.env` |
| Broadcast spine → X | ✅ **approve-first verified** | queued `pending_approval`, `results:{}`, **nothing posted** |
| Approve / veto lifecycle | ✅ **verified** | queued → pending → vetoed → dropped from queue |
| PM2 services | ⛔ **0 present** (2026-08-19, W84PNK2) — `pm2 list` shows no `dircomedia-*` process at all, and there is no `ecosystem.config.js` to restore them. Was: | `dircomedia-api`, `-gateway`, `-frontend`, `-worker`, `-tunnel` |
| **LIVE PUBLIC URL** | ⛔ **502 — ORIGIN DOWN** (re-measured 2026-08-19, W84PNK2). All five PM2 services are ABSENT (not stopped). Hostname is still correct; there is nothing behind it. Prior ✅ evidence retained below for reference only: | **https://dircomedia.vintaclectic.com** → dashboard HTTP **200**, 64,086 bytes, `<title>DirCo Media OS</title>` |
| Public API through gateway | ✅ **verified live** | `GET /api/v1/projects/` over the internet → **200** |
| Open liveness probe | ✅ **verified live** | `GET /__gateway/health` → `{"status":"ok"}` (no auth, by design) |
| `api.dircomedia.com` | ⛔ **530 / 1033 — tunnel minted in WRONG account** | SKD4JWF proved it: `cert.pem` accountID **a500348d…** and tunnel `AccountTag` **a500348d…** are BOTH the vintaclectic account, and no `api.dircomedia.com` CNAME exists. The dedicated tunnel did not escape the cross-account wall. Fix = `rm ~/.cloudflared/cert.pem` → `cloudflared tunnel login` **as the account owning dircomedia.com** → re-run `scripts/setup-tunnel.sh`. **Not needed to be live.** |
| **GoDaddy A/CNAME records** | ⛔ **INERT — do not edit** (re-measured 2026-08-17) | Both zones use Cloudflare nameservers (`alberto/paris` and `mona/toby`). GoDaddy is registrar-only; records added there are never read. |
| **Owner browser access** | ✅ **one command** | `bash scripts/open-dashboard.sh` → `http://127.0.0.1:4699` (verified 200, `<title>DirCo Media OS</title>`, `/api/v1/projects/` 200). |

### ✅ IT IS LIVE. Use this URL:

```
https://dircomedia.vintaclectic.com
```

**The 403 "DirCoMedia is locked" page is NOT a failure — it is the security
model working exactly as designed.** `gateway.js` refuses any internet request
that carries no owner identity, because this dashboard posts to Vinta's real
social accounts. An unauthenticated visitor *should* see that page.

Two prior deploy attempts read that intentional lock as a broken deploy and went
hunting for a tunnel bug that did not exist. The stack was serving correctly the
whole time. **Verify with the owner secret, never with a bare browser visit:**

```bash
SEC=$(grep -E '^GATEWAY_SHARED_SECRET=' /home/vinta/dircomedia/backend/.env | cut -d= -f2-)
curl -s -o /dev/null -w "%{http_code}\n" -H "x-gateway-secret: $SEC" \
  https://dircomedia.vintaclectic.com/          # -> 200, the real dashboard
```

To open it to a normal browser session, attach **Cloudflare Access** (Google SSO,
owner email only) to `dircomedia.vintaclectic.com` in Zero Trust — that hostname
is in the vintaclectic account, which we provably control — then set
`REQUIRE_ACCESS_JWT=1` in `backend/.env`. No new Cloudflare login required.

---

## 1. Architecture

```
                     Cloudflare edge
                            │
              ┌─────────────┴─────────────┐
              │                           │
      api.dircomedia.com          dircomedia.com
       (§5 — blocked)             (NOT routed — Scope A)
              │
              ▼
     FastAPI  127.0.0.1:8000   ←── owner-token gated (fail-closed)
              │
              ├── Celery worker (dircomedia-worker) — the fan-out that posts
              └── Postgres/SQLite via DATABASE_URL

   LOCAL ONLY:
     gateway  127.0.0.1:4600  ← the dashboard entrypoint. Serves /api/* from
              │                 FastAPI and everything else from Next under ONE
              │                 origin, so the browser never receives
              │                 OWNER_API_TOKEN.
              └── Next.js 127.0.0.1:4601   (never hit directly)
```

**Never expose `:4601` or `:8000` to a browser directly.** The gateway indirection
*is* the security model: it keeps the owner token server-side. An earlier build
inlined the token into public Next chunks via `NEXT_PUBLIC_OWNER_TOKEN` — anyone
loading the page could have posted to every one of Vinta's accounts. That is why
the dashboard is reached only through `:4600`.

---

## 2. Queue a post

Everything routes through the **brain's broadcast spine**. DirCoMedia does not
duplicate it.

```bash
node /home/vinta/vintinuum-api/broadcast.js \
  --project DirCoMedia \
  --kind update \
  --title "Ship title" \
  --body  "The post copy that actually goes out." \
  --platforms twitter \
  --mode approve-first
```

Verified response shape:

```json
{"ok":true,"uid":"…","synced":true,
 "detail":{"id":"2e6a6329-…","status":"pending_approval"}}
```

`status: "pending_approval"` is the proof the guard held. **`approve-first` is
absolute for X** — a queued broadcast has `results: {}` and has posted nowhere.

### The `BROADCAST:` note path (how most posts should be created)

Per the Work Journal → X law, any **user-facing** shipped work adds this to its
Work Journal row's Notes:

```
BROADCAST: <one-line tweet, ≤270 chars, brand voice>
```

A scheduled `node /home/vinta/vintinuum-api/broadcast.js --tap` sweeps those
notes into the approve-first queue. One row = one journal entry + one tweet
candidate.

- `BROADCAST: (hold) <copy>` — spools but `--tap` skips it until released.
- **Internal work** (refactors, recon, ops, typo fixes) gets **no** `BROADCAST:`
  line — journal-only. This keeps X from becoming dev-noise and protects the
  rate limit.

---

## 3. Approve / veto

```bash
TOK=$(grep -E '^OWNER_API_TOKEN=' /home/vinta/dircomedia/backend/.env | cut -d= -f2-)
API=http://127.0.0.1:8000        # after §5 lands: https://api.dircomedia.com

# See what is waiting
curl -s -H "X-Owner-Token: $TOK" $API/api/v1/broadcast/pending | python3 -m json.tool

# Inspect one
curl -s -H "X-Owner-Token: $TOK" $API/api/v1/broadcast/<ID> | python3 -m json.tool

# APPROVE → the worker fans it out and it POSTS PUBLICLY
curl -s -X POST -H "X-Owner-Token: $TOK" $API/api/v1/broadcast/<ID>/approve

# VETO → killed, never posts
curl -s -X POST -H "X-Owner-Token: $TOK" $API/api/v1/broadcast/<ID>/veto
```

⚠️ **`/approve` is the irreversible step.** It is the moment a post becomes
public. Read the `body` before approving. `/veto` is always safe.

Full route list (33 total): `curl -s $API/openapi.json`.

| Route | Method | Purpose |
|---|---|---|
| `/health` | GET | liveness — the only unauthenticated route |
| `/api/v1/broadcast/` | GET, POST | list all / create |
| `/api/v1/broadcast/pending` | GET | the approval queue |
| `/api/v1/broadcast/{id}` | GET | one broadcast |
| `/api/v1/broadcast/{id}/approve` | POST | **publish** |
| `/api/v1/broadcast/{id}/veto` | POST | kill |
| `/api/v1/distribution/health` | GET | per-platform connection health |

---

## 4. Health & service control

```bash
# Health (200 {"status":"ok"})
curl -s http://127.0.0.1:8000/health

# Per-platform connection health
curl -s -H "X-Owner-Token: $TOK" http://127.0.0.1:8000/api/v1/distribution/health

# Services
pm2 list | grep dircomedia
pm2 restart dircomedia-api        # the FastAPI backend
pm2 restart dircomedia-worker     # the Celery fan-out (restart if posts hang)
pm2 restart dircomedia-gateway    # the :4600 dashboard entrypoint
pm2 restart dircomedia-frontend   # Next.js :4601
pm2 logs dircomedia-api --lines 100
pm2 save                          # persist across reboot — run after any change
```

| PM2 name | What it runs | Port |
|---|---|---|
| `dircomedia-api` | `backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | 8000 |
| `dircomedia-worker` | Celery — performs the actual posting | — |
| `dircomedia-gateway` | `gateway.js` | 4600 |
| `dircomedia-frontend` | Next.js | 4601 |

**Dashboard (local only):** open **http://127.0.0.1:4600**.

### Health-check gotcha
A cold `/health` can take **~8s** on first hit after idle, then ~1ms. Use
`--max-time 20` when scripting, or a cold probe will look like an outage.

---

## 5. ⛔ `api.dircomedia.com` — optional vanity domain, NOT a blocker

> **READ THIS FIRST (2026-08-14, attempt #3).** DirCoMedia **is already live** at
> **https://dircomedia.vintaclectic.com** (§0). This section is about the *nicer
> domain name*, not about shipping. Do not treat it as a launch blocker again.
>
> **`scripts/setup-tunnel.sh` HAS ALREADY BEEN RUN — and it silently did the
> wrong thing.** It created tunnel `1427dc40-96da-497b-bd73-253afe8f926d`, which
> is up with 4 healthy edge connections right now… **in the wrong Cloudflare
> account.** Re-running it will not help. Proof, measured live:
>
> ```
> cert-dircomedia.pem decodes to:
>   zoneID    = a930c99ee0ef22118414f017f6b3602d   (vintaclectic.com)
>   accountID = a500348dbe17f05782b1d228158da3f1   (Bjustice@gmail.com)
> …byte-for-byte the SAME zone + account as the old cert.pem.
> Only the apiToken differs.
>
> GET /client/v4/zones            -> exactly 1 zone: vintaclectic.com
> GET /client/v4/zones?name=dircomedia.com -> [] (empty)
> ```
>
> **Vinta named this exact cause himself:** *"the login i use for vintaclectic
> tunnel with cloudflare is different from one i use with dircomedia."* Correct.
> When `cloudflared tunnel login` opened the browser, that browser was **already
> signed into `Bjustice@gmail.com`**, so Cloudflare never offered
> `dircomedia.com` — it just handed back another vintaclectic cert without
> warning. The telltale: routing DNS with this cert silently rewrites the
> hostname against its default zone —
> `cloudflared tunnel route dns dircomedia api.dircomedia.com` reported
> **`api.dircomedia.com.vintaclectic.com`**. That suffix is the fingerprint of a
> wrong-account cert.
>
> **To actually fix the vanity domain** (only if Vinta wants it):
> 1. `rm /home/vinta/.cloudflared/cert-dircomedia.pem`
> 2. In a browser, **fully sign out of Cloudflare** (or use a private window) and
>    sign in with **the account that owns `dircomedia.com`**.
> 3. `TUNNEL_ORIGIN_CERT=/home/vinta/.cloudflared/cert-dircomedia.pem cloudflared tunnel login`
>    — on the zone-picker page you **must see `dircomedia.com`**. If you do not,
>    you are still in the wrong account; stop and switch accounts.
> 4. Verify before proceeding — this one command prevents a 4th failed attempt:
>    ```bash
>    # must print dircomedia.com, NOT vintaclectic.com
>    python3 -c "import base64,json;print(json.loads(base64.b64decode(open('/home/vinta/.cloudflared/cert-dircomedia.pem').read().split('-----')[2].strip()))['zoneID'])"
>    ```
> 5. Then `bash /home/vinta/dircomedia/scripts/setup-tunnel.sh`.
>
> **Alternative with zero logins:** point a subdomain of the zone we already own
> (`dircomedia.vintaclectic.com`) — already done and live.

**Symptom:** `https://api.dircomedia.com/health` → **HTTP 530, `error code: 1033`**.

**This is not a config bug. Do not try to fix it by editing ingress rules** — the
rule in `~/.cloudflared/config.yml` is already correct and every variation still
1033s.

**Root cause (measured, not guessed):**

| Fact | Value |
|---|---|
| `NS dircomedia.com` | `mona.ns.cloudflare.com`, `toby.ns.cloudflare.com` → **zone IS on Cloudflare** |
| `vintinuum` tunnel account | `a500348dbe17f05782b1d228158da3f1` |
| That tunnel's `cert.pem` zone scope | `a930c99ee0ef22118414f017f6b3602d` = **vintaclectic.com only** |
| Zones its API token can enumerate | exactly one: `vintaclectic.com` |
| `dircomedia.com` zone location | a **different Cloudflare account** |

Cloudflare refuses a **cross-account tunnel CNAME with error 1033**. The DNS is
right; the **tunnel owner** is wrong.

> An older comment in `config.yml` claimed dircomedia.com was on GoDaddy
> nameservers. **That is stale and false** — it is on Cloudflare. The comment has
> been corrected in place so nobody re-chases it.

**DirHaven and DirMegle hit this identical wall** and each solved it the same
way: give the domain its **own tunnel in the account that owns its zone**
(`~/.cloudflared/dirhaven.yml`, `~/.cloudflared/dirmegle.yml`). A cloudflared
process binds to exactly one tunnel's credentials, so accounts cannot share a
daemon. DirCoMedia needs the same.

### The fix

```bash
bash /home/vinta/dircomedia/scripts/setup-tunnel.sh
```

The script is **idempotent** and does steps 2–6 automatically: creates the
tunnel, writes `~/.cloudflared/dircomedia.yml`, routes DNS, starts pm2
`dircomedia-tunnel`, and polls `https://api.dircomedia.com/health` until 200.

**Step 1 is a browser login only Vinta can do.** The script refuses to continue
without it and prints the exact commands:

```bash
cp ~/.cloudflared/cert.pem ~/.cloudflared/cert-vintaclectic.pem   # ← DO NOT SKIP
~/cloudflared tunnel login          # select the dircomedia.com zone
cp ~/.cloudflared/cert.pem ~/.cloudflared/cert-dircomedia.pem
cp ~/.cloudflared/cert-vintaclectic.pem ~/.cloudflared/cert.pem   # restore
bash /home/vinta/dircomedia/scripts/setup-tunnel.sh
```

⚠️ **`cloudflared tunnel login` overwrites `~/.cloudflared/cert.pem`.** Backing it
up first is mandatory — without it you break `api.vintaclectic.com`,
`board.vintaclectic.com`, and every other route on the main tunnel.

**If it still 530s after the script:** a **stale DNS record** for
`api.dircomedia.com` from the earlier cross-account attempt is shadowing the new
one. Delete that record in the Cloudflare dashboard for the dircomedia.com zone,
then re-run the script.

### Publishing the dashboard later (not Scope A)
Only after Cloudflare Access (Google SSO, owner email only) is configured on the
hostname:

```bash
ROUTE_DASHBOARD=1 bash /home/vinta/dircomedia/scripts/setup-tunnel.sh
# then set REQUIRE_ACCESS_JWT=1 in backend/.env and restart the gateway
```

---

## 6. Platform rollout order

Approved priority: **X (live) → Reddit → YouTube → Instagram.**

Credentials live in `backend/.env` (owner-only, **never** committed — it is
gitignored; keep it that way). Canonical X keys, never renamed:

```
TWITTER_API_KEY  TWITTER_API_SECRET  TWITTER_ACCESS_TOKEN
TWITTER_ACCESS_SECRET  TWITTER_BEARER_TOKEN
```

Reddit, Instagram, Pinterest, Bluesky credentials are already present. Connection
walkthroughs: `/home/vinta/dircomedia/docs/PLATFORM_CONNECTIONS.md`.

If a platform's keys are absent: **never fabricate a post or claim it went out.**
Spool the approve-first candidate anyway (it replays when keys land).

---

## 7. Safety rails (non-negotiable)

- **approve-first is absolute for X.** Nothing posts publicly without Vinta's
  explicit approval. `auto` only where Vinta has said so for that project.
- **Never commit `backend/.env`** or any `*.key` / `*.pem`.
- **Never `cloudflared tunnel login` without backing up `cert.pem` first.**
- **Owner auth fails closed** — if `OWNER_API_TOKEN` is unset/blank, every
  authenticated route refuses anonymous access rather than opening up.
- **Dashboard stays local** until Cloudflare Access is on the hostname.
- The gateway strips `x-gateway-secret` before proxying inward — the origin lock
  is never forwarded.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `api.dircomedia.com` → 530 / 1033 | cross-account tunnel | §5 — dedicated tunnel |
| `/health` takes ~8s once, then fast | cold start | expected; use `--max-time 20` |
| `401` on a broadcast route | missing/wrong owner token | send `X-Owner-Token: $OWNER_API_TOKEN` |
| `403` from the gateway | origin lock (working as designed) | reach the dashboard via `:4600` |
| Approved post never goes out | worker down/stuck | `pm2 restart dircomedia-worker`, check `pm2 logs` |
| Duplicate post refused | dedupe window (`BROADCAST_DEDUPE_HOURS`) | expected; vary the copy |
| Nothing posts at all | `BROADCAST_KILL_SWITCH` set | inspect `backend/.env` |
