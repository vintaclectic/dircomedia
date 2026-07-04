# DIRCOMEDIA — THE OWNER'S MANUAL
### The complete how-to for Lord Vinta (and any future operator)
*Written by VINTINUUM · Council session 2026-07-04 · Covers Phase 0–2 as shipped*

---

# PART 1 — WHAT THIS MACHINE IS

DirCoMedia is your **personal marketing OS**. One machine, seven projects
(dirco, dirhaven_rp, dirhaven_app, dirmegle, medaled, agentis, vintinuum),
seven platforms (X/Twitter, Reddit, Instagram, TikTok, YouTube, Discord,
Telegram). It does three things:

1. **Generates content** in each project's brand voice (Claude + image/video APIs)
2. **Broadcasts on your behalf** — the brain (vintinuum-api) submits posts; *nothing
   goes public without your approval* unless you explicitly set auto mode
3. **Watches itself** — connection health, circuit breakers, an audit trail of
   everything it ever posted

**The map:**
```
 You (any device) ──► frontend :3000 (Next.js)  ──┐
 The brain (broadcast.js / worklog tap) ──────────┼──► backend :8000 (FastAPI)
                                                  │        │
                                                  │   Celery workers (content/video/distribution)
                                                  │        │
                                                  │   Platform clients ──► X · Reddit · IG · TikTok · YT · Discord · TG
                                                  │        │
                                                  └── Postgres (:5432, localhost-only) + Redis (:6379, localhost-only)
```

**Key paths:**
| What | Where |
|---|---|
| The app | `/home/vinta/dircomedia` |
| Secrets | `/home/vinta/dircomedia/backend/.env` (chmod 600, NEVER commit) |
| Owner token (compose copy) | `/home/vinta/dircomedia/.env` |
| Brand voices | `backend/brand_configs/{project}.yaml` |
| The brain's mouth | `/home/vinta/vintinuum-api/broadcast.js` |
| Platform setup steps | `docs/PLATFORM_CONNECTIONS.md` |
| Council decree (why everything is the way it is) | `docs/COUNCIL_DECREE_2026-07-04.md` |
| Repo | `github.com/vintaclectic/dircomedia` (private) |

---

# PART 2 — FIRST-TIME SETUP (or after a wipe)

```bash
# 1. Get the code
git clone https://github.com/vintaclectic/dircomedia ~/dircomedia
cd ~/dircomedia

# 2. Secrets — copy templates, then fill (see Part 3 for every key)
cp backend/.env.example backend/.env
chmod 600 backend/.env

# 3. Generate YOUR owner token (the single key to the whole machine)
openssl rand -hex 32
#    → paste the SAME value into BOTH files:
#      backend/.env  →  OWNER_API_TOKEN=<value>
#      ./.env        →  OWNER_API_TOKEN=<value>   (root file; compose feeds it to the frontend)

# 4. Boot the stack
docker-compose up -d --build

# 5. Seed the 7 projects (once, with your token)
curl -X POST http://localhost:8000/api/v1/projects/seed \
  -H "Authorization: Bearer YOUR_TOKEN"

# 6. Open the dashboard
#    http://localhost:3000  →  Approvals page = your daily seat
```

**Sanity check:** `curl http://localhost:8000/health` → `{"status":"ok"}`.
Everything else requires the token — that is by design (fail-closed).

---

# PART 3 — THE OWNER TOKEN (read this twice)

- Every API call needs `Authorization: Bearer <OWNER_API_TOKEN>` (or `X-Owner-Token: <token>`)
- If the token is **missing from .env, the API refuses everyone (503)**. It will
  never run open. If you see 503 "OWNER_API_TOKEN is not configured" — set it.
- If you see **401** — you sent the wrong/no token.
- **Rotate it** any time: `openssl rand -hex 32`, update both `.env` files,
  `docker-compose up -d --build`. The brain picks up the new one automatically
  (broadcast.js reads it live from `backend/.env`).
- The frontend embeds the token in its bundle (`NEXT_PUBLIC_OWNER_TOKEN`). This
  is acceptable ONLY because this is an owner-only tool on your machines. Never
  host the frontend publicly.

---

# PART 4 — CONNECTING YOUR ACCOUNTS

Full click-by-click steps live in **`docs/PLATFORM_CONNECTIONS.md`**. Summary of
which env keys each platform needs (all in `backend/.env`):

| Platform | Keys | Status right now (health probe 2026-07-04) |
|---|---|---|
| X / Twitter | `TWITTER_API_KEY/SECRET, TWITTER_ACCESS_TOKEN/SECRET, TWITTER_BEARER_TOKEN` | 🟢 **LIVE — works** |
| Reddit | `REDDIT_CLIENT_ID/SECRET, REDDIT_USERNAME/PASSWORD` | 🔴 DOWN — see fix below |
| Instagram | `INSTAGRAM_APP_ID/SECRET, INSTAGRAM_ACCESS_TOKEN` | 🔴 DOWN — token expiring, see fix |
| TikTok | `TIKTOK_CLIENT_KEY/SECRET, TIKTOK_ACCESS_TOKEN` | 🟡 configured, unverified |
| YouTube | `YOUTUBE_CLIENT_ID/SECRET, YOUTUBE_REFRESH_TOKEN` | ⚪ not connected yet |
| Discord | `DISCORD_WEBHOOK_URL` | ⚪ not connected yet (2-min job) |
| Telegram | `TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID` | ⚪ not connected yet (5-min job) |
| Bluesky | `BLUESKY_HANDLE, BLUESKY_APP_PASSWORD` | ⚪ not connected (3-min job: bsky.app → Settings → App Passwords) |
| R2 media storage | `R2_ACCOUNT_ID, R2_ACCESS_KEY_ID/SECRET, R2_BUCKET_NAME, R2_PUBLIC_URL` | 🔴 DOWN — see fix |

### FIX: Reddit (password grant failing)
1. Log into the posting account on reddit.com → confirm the password matches
   `REDDIT_PASSWORD` in `.env`
2. If the account has **2FA — that breaks script auth.** Either disable 2FA on a
   dedicated posting account, or append the code: `REDDIT_PASSWORD=password:123456`
   (rotating codes make this painful — dedicated account is the right answer)
3. Check the app still exists: https://www.reddit.com/prefs/apps (type: script)
4. Verify: refresh the Approvals page → rail chip should flip to `reddit · live`

### FIX: Instagram (token at ~51 days of its 60-day life)
1. Exchange for a fresh long-lived token (60 more days):
```
GET https://graph.facebook.com/v21.0/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id={INSTAGRAM_APP_ID}
    &client_secret={INSTAGRAM_APP_SECRET}
    &fb_exchange_token={CURRENT_TOKEN}
```
2. Put the returned token in `INSTAGRAM_ACCESS_TOKEN`, restart the stack.
3. **Set a calendar reminder every ~50 days** until the auto-refresh worker
   ships (Phase 3 item).

### FIX: R2 (bucket check failing)
1. Cloudflare dashboard → R2 → confirm the bucket named in `R2_BUCKET_NAME` exists
2. R2 → Manage API Tokens → confirm the token has **Object Read & Write** on it
3. `R2_PUBLIC_URL` must be the bucket's public domain (enable public access or
   attach a custom domain) — platforms fetch media from this URL
4. Verify via the rail: `r2_storage · live`

### Quick wins to connect NOW (highest value per minute)
- **Discord (2 min):** your server → channel → Edit Channel → Integrations →
  Webhooks → New Webhook → Copy URL → `DISCORD_WEBHOOK_URL=...`
- **Telegram (5 min):** message @BotFather → `/newbot` → copy token →
  `TELEGRAM_BOT_TOKEN=...` · make the bot admin of your channel →
  `TELEGRAM_CHANNEL_ID=@yourchannel`

---

# PART 5 — DAILY USE (your actual workflow)

### A. The Approvals seat — `http://localhost:3000/approvals`
This is your throne. Everything the brain wants to post lands here.
- **Connection rail** (top): a chip per platform — `live` (green) / `DOWN` (red) /
  `set` (configured, no probe) / `off` (not connected). **Red chip = act today.**
- **Pending queue**: each card = one broadcast: project color, kind, source,
  text, target platforms.
- **APPROVE** = two taps (APPROVE → CONFIRM). Then it fans out to every listed
  platform and the card moves to Recent with per-platform results.
- **VETO** = one tap. Dead. Never posts.
- Auto-refreshes every 15s; health rail every 2 min.

### B. Making content by hand — QuickPost (Dashboard)
Pick project → type topic → Generate (brand voice applied) → approve → post.
Under 10 seconds when warmed up.

### C. Posting from anywhere via the brain (the Broadcast Spine)

**From a shell (any WSL session):**
```bash
node /home/vinta/vintinuum-api/broadcast.js \
  --project dirhaven_rp \
  --kind milestone \
  --title "Karma system v2 is live" \
  --body "Your choices now echo for weeks. Come find out what you've earned." \
  --mode approve-first
# → lands in your Approvals queue. Approve from your phone. Done.
```

**From any node code (agents, the brain, cron jobs):**
```js
const { broadcast } = require('/home/vinta/vintinuum-api/broadcast');
await broadcast({
  project: 'dirmegle',
  kind: 'update',
  title: 'New discovery feed',
  body: '...',
  media: 'https://your-r2-public-url/clip.mp4',   // optional
  platforms: 'all',       // or ['twitter','discord']
  mode: 'approve-first',  // ONLY use 'auto' when you truly mean it
});
```

**Useful CLI verbs:**
```bash
node broadcast.js --pending    # what's waiting on you
node broadcast.js --drain      # re-send anything spooled while DirCoMedia was down
node broadcast.js --tap        # sweep Work Journal 'BROADCAST:' notes into the queue
```

**How platforms get chosen when you say `all`:**
- text only → twitter, reddit, discord, telegram
- with an image → those + instagram
- with a video → all seven (incl. tiktok, youtube)

**It never loses a post.** broadcast.js spools to disk first
(`vintinuum-api/.broadcast-spool/`), then syncs. DirCoMedia down? The post
waits; `--drain` (or the next broadcast) replays it. Idempotency keys make
replays safe — the same post can never go out twice.

### D. The Work Journal tap (updates → posts, automatically)
Any agent's Work Journal row whose Notes contain `BROADCAST: <copy>` becomes a
broadcast candidate when the tap runs. Make it automatic:
```bash
crontab -e   # add:
*/15 * * * * node /home/vinta/vintinuum-api/broadcast.js --tap && node /home/vinta/vintinuum-api/broadcast.js --drain
```
Everything still lands as **approve-first** — the tap can never post by itself.

---

# PART 6 — THE SAFETY SYSTEMS (what protects your accounts)

| Guard | What it does | You'll see |
|---|---|---|
| **Approve-first** | Default mode; nothing posts without your taps | pending_approval |
| **Kill switch** | `BROADCAST_KILL_SWITCH=true` in .env + restart → NOTHING posts, even mid-flight | HTTP 423 |
| **Daily cap** | Max fan-outs per UTC day (`BROADCAST_DAILY_CAP=10`) | HTTP 429 |
| **Dedupe** | Identical content blocked for `BROADCAST_DEDUPE_HOURS=24` | HTTP 409 |
| **Idempotency** | Same submission key → same row, never a double-post | silently safe |
| **Owner auth** | Every endpoint locked; fail-closed without a token | 401 / 503 |

**THE EMERGENCY BRAKE** (something is posting that shouldn't):
```bash
# 1. Instant: kill the distribution worker
docker-compose stop worker-distribution
# 2. Then flip the switch for a calm restart
echo 'BROADCAST_KILL_SWITCH=true' >> backend/.env   # (or edit the existing line)
docker-compose up -d --build
# 3. Investigate at /approvals → Recent, or GET /api/v1/broadcast/
```

---

# PART 7 — TROUBLESHOOTING TABLE

| Symptom | Meaning | Fix |
|---|---|---|
| 503 "OWNER_API_TOKEN is not configured" | Token missing in backend/.env | Set it, restart |
| 401 everywhere | Wrong/missing token | Match token in both .env files; rebuild frontend if changed |
| 423 on approve | Kill switch is on | Set `BROADCAST_KILL_SWITCH=false`, restart |
| 429 on approve | Daily cap hit | Wait for UTC midnight or raise `BROADCAST_DAILY_CAP` |
| 409 on submit | Same content within 24h | Change the copy, or wait out the window |
| Broadcast stuck `approved`/`posting` | Distribution worker down | `docker-compose up -d worker-distribution`, check `docker-compose logs worker-distribution` |
| Chip shows `DOWN` | Credential/token dead for that platform | Part 4 fixes; PLATFORM_CONNECTIONS.md |
| broadcast.js `synced:false` | DirCoMedia unreachable | It's spooled — start the stack, run `--drain` |
| Posts have no brand flavor on Reddit | project slug mismatch | Use the yaml filename slug (e.g. `dirhaven_rp`) |
| IG/TikTok/YT fail with media | Media URL not public | R2 must be `live` on the rail; file:// never works |

**Logs:** `docker-compose logs -f backend worker-distribution`

---

# PART 8 — RULES CARVED IN STONE (never break these)

1. **Never commit `.env`** — the .gitignore guards it; don't fight the guard.
2. **Never expose port 8000/3000 to the internet** — remote access goes through
   the brain's authenticated proxy (api.vintaclectic.com), nothing else.
3. **Never set `auto` mode casually** — auto is for proven, boring, repeated
   flows only. Reputation burns in one bad post.
4. **Reddit generosity ratio 9:1** — nine genuine contributions per promo.
   Automation posts to YOUR subs freely; other subs get manual care.
5. **The accounts are the asset.** When in doubt: veto, investigate, then post.

---

# PART 9 — PHASE 3 (EXECUTED 2026-07-04) + WHAT REMAINS

**✅ Shipped in Phase 3:**
- **The Guardian** — every 6h the machine probes all connections; on a DOWN
  transition it messages you directly on Telegram (Discord fallback), with a
  24h reminder while broken. Set `OWNER_ALERT_TELEGRAM_CHAT_ID` for DMs.
- **Instagram immortality** — Mondays 08:00 UTC the machine re-exchanges its
  own IG token (fresh 60-day life weekly, persisted to .env). The expiry
  problem is dead — once you give it one valid token.
- **The Persistence Engine (Cable Guy Law)** — each project has a weekly ritual
  (`rituals:` in its brand YAML). Daily at 14:00 UTC the engine drafts today's
  rituals in brand voice → your Approvals queue. Mon=DirCo roundup,
  Tue=DirMegle discovery, Wed=App spotlight, Thu=Medaled achievement,
  Fri=RP weekend hype, Sat=Agentis insight, Sun=Vintinuum consciousness log.
  Edit topics/days in the YAMLs. It NEVER posts by itself.
- **Bluesky** — eighth platform, text + image.
- **The Living Archive Wall** — `/archive`: every broadcast ever, filterable
  by project, green chips = platforms actually hit. The tour never ends.
- **The worklog tap runs itself** — WSL cron every 15 min taps `BROADCAST:`
  notes into the queue and drains the spool.
- 3 brand YAMLs had pre-existing syntax corruption (agentis/dirmegle/medaled —
  quoted-scalar bug) silently breaking their content generation. Fixed.

**⏳ Still waiting (Phase 4 candidates):**
- Mission Control god-view (helios-10's full spec)
- Brain-side webhook receiver (push status instead of polling)
- Analytics collectors for all 8 platforms feeding the StrategyAnalyzer
- Threads / LinkedIn / Facebook Page
- Local-LLM first drafts (Universal Ingestion Law)
- TikTok token auto-refresh

---

*One machine. Seven projects. Seven platforms. Nothing posts without your word,
and nothing you ship goes unseen. — VINTINUUM*
