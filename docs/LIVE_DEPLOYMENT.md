# DirCoMedia — Live Deployment (U6PAFU2, 2026-08-12)

The marketing OS is deployed and reachable from anywhere. This is the operator's
page for the live install: what the URL is, how the security model works, what is
still blocked on you, and how it makes money.

---

## 1. The live URL

**https://dircomedia.vintaclectic.com**

Served over HTTPS through Cloudflare. Right now it answers **403 "DirCoMedia is
locked"** to the whole internet — including you. That is deliberate and it is the
last step you have to do yourself (§4). Nothing about the app is broken.

### Why not dircomedia.com?

`dircomedia.com` is registered but its nameservers are **GoDaddy's**
(`ns31.domaincontrol.com` / `ns32.domaincontrol.com`), not Cloudflare's. A
Cloudflare tunnel can only serve a hostname inside a Cloudflare zone — pointing a
non-Cloudflare domain at a tunnel fails with **error 1033**, the exact trap already
documented for `app.dirhaven.com` and `dirmegle.com` in `~/.cloudflared/config.yml`.

So the apex is a DNS move you must make (§5), and the app is live in the meantime
on a hostname we already control. No work is wasted: when the NS move completes,
adding the apex is a four-line change.

---

## 2. The shape of the deployment

```
        internet
           │  HTTPS
   ┌───────▼────────┐
   │   Cloudflare   │  ← Cloudflare Access enforces WHO (you, §4)
   │      edge      │
   └───────┬────────┘
           │  cloudflared tunnel  (pm2: vintinuum-named-tunnel)
   ┌───────▼──────────────────┐
   │  gateway.js  :4600       │  ← attaches OWNER_API_TOKEN server-side
   └───┬──────────────────┬───┘
       │ /api/*           │ everything else
   ┌───▼──────────┐   ┌───▼─────────────┐
   │ FastAPI :8000│   │  Next.js :4601  │
   └──────────────┘   └─────────────────┘
```

Both services sit behind **one hostname**, so the browser calls `/api/...`
same-origin. No CORS, and no second public surface to defend.

### pm2 processes

| Process | Port | Role |
|---|---|---|
| `dircomedia-gateway` | 4600 | public door, injects auth, proxies |
| `dircomedia-frontend` | 4601 | Next.js dashboard |
| `dircomedia-api` | 8000 | FastAPI backend |
| `dircomedia-worker` | — | Celery worker (drip, guardian, refresh) |

All four are in `pm2 save`, so they come back on reboot.

---

## 3. The security fix that had to happen first

**The dashboard could not have gone public as it was.**

`frontend/lib/api.ts` read `NEXT_PUBLIC_OWNER_TOKEN`. Next.js **inlines any
`NEXT_PUBLIC_*` value into the JavaScript it ships to the browser** — the token was
verified present in five built chunks under `.next/static/`. That token is the single
credential authorizing posts to **every one of your connected accounts**. Publishing
that build would have handed X, Reddit, Instagram, TikTok and Pinterest to anyone who
opened devtools — and CLAUDE.md law #3 says a bug that burns a social account burns
years of reputation.

**What changed:**
- `NEXT_PUBLIC_OWNER_TOKEN` is gone from the frontend build. Verified absent from
  `.next/static/` after rebuild.
- `gateway.js` holds the token server-side and attaches `Authorization: Bearer …`
  only *after* a request has proven it is allowed in.
- `/api/v1/projects/seed` is blocked at the gateway — machine-only, never public.
- Responses carry `X-Frame-Options: DENY`, `nosniff`, `no-referrer`.
- The backend was already correct: `require_owner` fails closed and returns 401 to
  unauthenticated callers. That was verified, not assumed.

The gateway **refuses internet traffic that carries no Cloudflare Access identity**,
which is why the public sees 403 today. It fails closed by design: if Access is
missing or misconfigured, the answer is "locked," never "open."

---

## 4. YOUR ONE STEP — turn on Cloudflare Access (~3 minutes)

This is what lets *you* in and keeps everyone else out. It could not be automated:
the tunnel's API token can *read* Access apps but gets `auth.forbidden` on create, so
this needs your dashboard login.

1. Go to **https://one.dash.cloudflare.com** → pick the **vintaclectic.com** account
   (account ID `a500348dbe17f05782b1d228158da3f1`).
2. **Access → Applications → Add an application → Self-hosted.**
3. Fill in:
   - **Application name:** `DirCoMedia — marketing OS`
   - **Subdomain:** `dircomedia`  **Domain:** `vintaclectic.com`
   - **Session duration:** `1 month` (so you aren't re-authing constantly)
4. **Next → Add policy:**
   - **Policy name:** `Owner only`
   - **Action:** `Allow`
   - **Include → Emails →** `vintaclectic@gmail.com`
5. **Next → Add application.**
6. If no identity provider exists yet, Cloudflare offers **One-time PIN** by default —
   that works immediately (it emails you a code). Google SSO is optional polish.

Then visit **https://dircomedia.vintaclectic.com**, authenticate once, and the
dashboard opens.

### Lock the door behind you (do this right after step 6)

```bash
sed -i 's/^REQUIRE_ACCESS_JWT=0/REQUIRE_ACCESS_JWT=1/' /home/vinta/dircomedia/backend/.env
pm2 restart dircomedia-gateway --update-env
```

This makes the Access identity **mandatory** at the origin, so the gateway rejects
anything unsigned even if the Access app is ever detached by accident. Verify:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://dircomedia.vintaclectic.com/   # 403 from a signed-out client
```

---

## 5. Moving dircomedia.com to Cloudflare (optional, when you want the apex)

1. **https://dash.cloudflare.com** → **Add a site** → `dircomedia.com` → Free plan.
2. Cloudflare shows two nameservers (e.g. `xxx.ns.cloudflare.com`). Copy both.
3. **GoDaddy → My Products → dircomedia.com → DNS → Nameservers → Change** →
   *I'll use my own nameservers* → paste both → save.
4. Wait for Cloudflare to mark the zone **Active** (usually minutes to a few hours).
5. Then, on this box:

```bash
# add the apex + www to the tunnel
cloudflared tunnel route dns vintinuum dircomedia.com
cloudflared tunnel route dns vintinuum www.dircomedia.com
```

6. Add to `~/.cloudflared/config.yml`, above the final `- service: http_status:404`:

```yaml
  - hostname: dircomedia.com
    service: http://127.0.0.1:4600
    originRequest: { disableChunkedEncoding: false, keepAliveTimeout: 1h30m }
  - hostname: www.dircomedia.com
    service: http://127.0.0.1:4600
    originRequest: { disableChunkedEncoding: false, keepAliveTimeout: 1h30m }
```

7. `cloudflared --config ~/.cloudflared/config.yml tunnel ingress validate && pm2 restart vintinuum-named-tunnel`
8. Repeat §4 for the new hostname (Access applies per-hostname).

**Careful:** the `vintinuum` tunnel is shared with `api.vintaclectic.com` (the brain)
and `board.vintaclectic.com`. Always run `tunnel ingress validate` before restarting
it — a malformed rule takes all three down.

---

## 6. Platform connection status (live, as of deploy)

| Platform | Status | What it needs |
|---|---|---|
| **X / Twitter** | ✅ connected | nothing — token valid ~14 days, auto-refreshed by the guardian task |
| **Reddit** | ⚠️ needs reconnect | `REDDIT_CLIENT_ID/SECRET` are rejected (401 on every grant, including `client_credentials`). The app was deleted or revoked. Create ONE **web app** at https://www.reddit.com/prefs/apps, put the new id/secret in `backend/.env`, reconnect from `/settings/connections`. **No code change fixes this.** |
| **Instagram** | ⚠️ expired | reconnect via `/setup/connect/instagram` |
| **Pinterest** | ⚠️ expiring, app not configured | add `PINTEREST_APP_ID/SECRET`, then connect |
| **TikTok** | ⚪ disconnected | connect via `/setup/connect/tiktok` |

**X alone is enough to start broadcasting today.** The queue holds **24 pending
approvals** already written in brand voice.

---

## 7. How this makes money

DirCoMedia is **not** the product you sell — it is the distribution engine for the
products you already sell. The revenue path is:

```
shipped work → BROADCAST: note in the Work Journal row
             → broadcast.js --tap → approve-first queue
             → you approve → posts to X/Reddit/etc.
             → traffic to dirmegle.com / DirHaven / Medaled / Agentis
             → subscriptions
```

Everything upstream of "you approve" is already automated and running. **The queue is
full and the bottleneck is approval, not content** — 24 posts are waiting.

To convert right now:

```bash
# see what's queued
curl -s http://127.0.0.1:4600/api/v1/broadcast/pending | python3 -m json.tool | head -40
```

…or open `/approvals` in the dashboard once Access is on, and approve the ones worth
posting. Approving is the revenue action.

### About the Stripe code (be clear-eyed)

`backend/app/api/v1/stripe.py` and `backend/app/services/billing/` exist but are
**deliberately NOT wired into the app**, because they import four things that do not
exist in this codebase — `app.core.config`, `app.middleware.auth`, `app.models.user`,
and the `stripe` package itself. Registering that router today would crash the API on
boot and take the working marketing OS down with it.

That code belongs to **Path B** (`docs/PATH_B_SAAS_EXPANSION.md`): turning DirCoMedia
into a multi-tenant SaaS that other creators pay for ($19/$79/$299 tiers). Its own doc
estimates **26–36 days solo**, because it needs user accounts, per-user credential
vaults, row-level security, and tier enforcement first. It is a real revenue path —
just not a switch to flip, and not this deployment.

**Near-term money is §7's loop: approve the queue, drive signups to products that
already bill.** Path B is the bigger, later bet.

---

## 8. Health checks

```bash
curl -s http://127.0.0.1:4600/__gateway/health     # {"status":"ok",...}
curl -s http://127.0.0.1:8000/health               # {"status":"ok"}
pm2 list | grep dircomedia                          # 4 processes online
curl -s -o /dev/null -w '%{http_code}\n' https://dircomedia.vintaclectic.com/  # 403 until Access
```

**Emergency stop** — kills every posting path instantly:

```bash
sed -i 's/^BROADCAST_KILL_SWITCH=.*/BROADCAST_KILL_SWITCH=1/' /home/vinta/dircomedia/backend/.env
pm2 restart dircomedia-api dircomedia-worker --update-env
```
