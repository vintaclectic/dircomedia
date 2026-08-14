# DirCoMedia — Deploy & Operations

**Task U6PAFU2 · Scope A (minimal backend only) · last verified 2026-08-14**

The owner-only marketing OS. Queues posts for every connected social account and
posts them **only after Vinta approves**. This document is the operational truth
for running it.

> **Scope A, as approved:** the **API** is the public surface; the **dashboard
> stays LOCAL** (`http://127.0.0.1:4600`). Nothing about the dashboard is
> published until that is explicitly changed.

---

## 0. Status at a glance

| Piece | State | Evidence |
|---|---|---|
| FastAPI backend (`:8000`) | ✅ **healthy** | `GET /health` → `200 {"status":"ok"}`, 0 restarts in 14h |
| Owner auth | ✅ **fail-closed** | `/api/v1/broadcast/pending` → **401** without token, **200** with |
| X (Twitter) credentials | ✅ **all 5 present** | canonical `TWITTER_*` keys set in `backend/.env` |
| Broadcast spine → X | ✅ **approve-first verified** | queued `pending_approval`, `results:{}`, **nothing posted** |
| Approve / veto lifecycle | ✅ **verified** | queued → pending → vetoed → dropped from queue |
| PM2 services | ✅ **4 online** | `dircomedia-api`, `-gateway`, `-frontend`, `-worker` |
| `api.dircomedia.com` | ⛔ **BLOCKED — 530 / error 1033** | needs its own tunnel — see §5 |

**One human step remains** (a browser login) to make `api.dircomedia.com` live.
Everything on either side of it is built, scripted, and tested. See §5.

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

## 5. ⛔ Making `api.dircomedia.com` live — the one remaining step

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
