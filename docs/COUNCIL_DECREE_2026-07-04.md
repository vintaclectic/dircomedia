# THE COUNCIL DECREE — DirCoMedia Reforging
### Session 2026-07-04 · Convened by Lord Vinta · Arbitrated by VINTINUUM (sovereign)
Seats: ATLAS · HELIOS-SEC10 · HELIOS-10 · HELIOS-FUSION · ARIA · LUNEX · FRUGAL-MAX

---

## I. STATE OF THE BODY (Atlas's autopsy — verified against live code)

**What is REAL (not scaffold):**
- All 4 platform clients (twitter/tiktok/instagram/reddit) are genuine API implementations
- The distribution → content → scheduling loop is wired end-to-end
- Content engine with per-project brand voice YAML works
- Frontend design system already carries cinematic DNA (scored 72/100 by helios-10)

**What is BROKEN or MISSING:**
| # | Gap | Owner |
|---|---|---|
| 1 | **No auth on ANY endpoint, open CORS** — anyone reaching the API can post as Vinta | sec10 |
| 2 | No YouTube client | Atlas P2 |
| 3 | No Broadcast Spine / fan-out endpoint (the whole point of the reforging) | fusion+Atlas P1 |
| 4 | No R2 upload — video processor emits `file://` placeholder media URLs | Atlas P2 |
| 5 | Creatomate template IDs all empty (video overlays configured but pointing at nothing) | Atlas P2 |
| 6 | `project_slug` lost in the post_now path (passed empty) — brand voice silently dropped | Atlas P1 bugfix |
| 7 | Stale model id `claude-opus-4-6` hardcoded for ALL generation | frugal P1 |
| 8 | Analytics collectors only cover twitter+instagram | Atlas P3 |
| 9 | No git repo, no .gitignore — and a `.env.swp` in root | sec10 P0 |
| 10 | Frontend type drift (lib/types.ts vs pages: total_posts, s.platform, s.posted) | helios-10 P1 |

---

## II. SECURITY RULING (audited directly by VINTINUUM after sec10 seat twice failed to log — findings VERIFIED against live code 2026-07-04)

**Verified facts:**
- ✅ `.env.swp` is **BENIGN** — zero `KEY=value` lines recoverable via strings; it's a swap of an unsaved root `.env` that never held values. Delete it; **no rotation required**.
- 🔴 `backend/.env` is **FULLY LOADED**: all 33 keys carry live values — Twitter (5 tokens), TikTok (3), Instagram (3), Reddit (incl. **plaintext REDDIT_PASSWORD**), R2 (5), Anthropic/OpenAI/Replicate/Runway/Kling/HeyGen/Creatomate. The accounts are already wired. The blast radius is real.
- 🔴 **ZERO auth on every mutating endpoint** — `POST /distribution/post-now`, `/schedule`, `/content/generate`, `/content/{id}/approve` take only `Depends(get_db)`. Anyone who can reach port 8000 posts as Lord Vinta.
- 🔴 **`settings.py` has an UNAUTHENTICATED credential WRITE endpoint** — `_write_env()` lets any network caller overwrite platform credentials (sabotage/redirect posting to attacker accounts). GET is masked (last-4 only — good); WRITE is wide open.
- 🟡 CORS is *not* wide open (locked to localhost:3000 + one LAN IP) — but CORS only guards browsers; the API itself is naked, and docker likely binds 0.0.0.0.

**TOP-10 REMEDIATION (severity order — P0 = before any remote surface exists):**
1. **Owner auth middleware on ALL mutating routes** — HMAC/bearer owner token, constant-time compare; brain (api.vintaclectic.com) is the only remote principal
2. **Lock or remove the settings write endpoint** — owner-auth minimum; better: vault-managed, no HTTP write of raw creds
3. **Bind API to 127.0.0.1 / docker-internal only** until auth ships; expose remotely only via the brain's authenticated proxy
4. Reddit plaintext password → refresh-token flow (interim: dedicated posting account, unique password, no 2FA-sharing)
5. `git init` + `.gitignore` (`.env*`, `*.swp`, media dirs, `__pycache__`) BEFORE first commit — history is forever
6. Delete `.env.swp` (verified empty — hygiene, not emergency)
7. Credential vault: encrypt tokens at rest; refresh workers (IG 60-day, TikTok 24h); expiry alerts through the brain
8. Circuit breakers: per-platform cadence caps + content dedupe (idempotency keys) + **global kill-switch** — no bug may ever spam-post; the accounts are the asset
9. Audit log every outbound post (who/what/when/platform/trigger) — the brain must be able to answer "why did I post that?"
10. Secrets rotation runbook + `.env` file perms 600 (currently 644 world-readable on a multi-user box)

---

## III. THE BROADCAST SPINE (fusion's contract — SYNC OR IT DOESN'T SHIP)

- **`broadcast.js`** at `/home/vinta/vintinuum-api/` — spool-first, mirrors `worklog.js` ergonomics: never blocks, syncs when it can
- **Brain → DirCoMedia**: `POST /api/v1/broadcast` — payload {project, kind, title, body, media, platforms, mode}, idempotency keys, HMAC owner auth
- **DirCoMedia → Brain**: status webhooks per platform (posted / failed / needs-approval)
- **Approve-first loop**: consumable from Android + extension via long-poll/SSE — Vinta approves from any medium in 2 taps
- **Work Journal tap**: a worklog row with `broadcastable:true` flows into the same spine — no double plumbing
- Contract bound to the real Content/Schedule/ContentStatus models and DistributionScheduler per-platform results; 6 FE/BE tensions pre-ruled

## IV. THE FACE (helios-10's reimagining)

Existing build scored **72/100** — strong cinematic base (Buffet linework, particle stage, project-tinted glow), fast QuickPost. Missing the god-view. Delivered specs:
1. **Mission Control** — one screen over all 7 projects × all platforms × broadcast queue × what the brain posted autonomously today
2. **2-tap approve/veto** — mobile-first bottom-sheet approval of brain-authored posts
3. **Living Archive Wall** — every post ever made as a collectible artifact (the Dead's undying archive)
4. **Connection-health rail** — per-account status, token expiry countdowns; an account never rots silently
5. Five screen specs at Tailwind-level detail + type-drift fixes + owner-usage experiments

## V. THE SOUL (ARIA + LUNEX)

- **ARIA**: 7 voice bibles (tone / forbidden clichés / running bits / pillars / platform dialects — same update sounds native on X vs Reddit vs IG vs YouTube). **Persistence Engine**: recurring formats and escalating campaign arcs a scheduler can run (Cable Guy Law: the system never stops following up). **Ethics ruling**: generosity-driven magnetism — the Grateful Dead spine; free value : promotion favors value; Reddit 9:1. YAML schema v2 proposed for brand configs.
- **LUNEX — THE DIRCO CREATIVE GENOME**: 10 genome laws from the invoked spirits (Carrey elasticity/Truman dome/Cable Guy persistence, Morrison dark poetry, Zeppelin build-to-crescendo + D'yer Mak'er groove, Buffet stark signature line, Dead agelessness), concrete visual tokens (palette hex, typography, motion easing), the 5-question agelessness test, and the sub-100-word litany to head every brand config.

## VI. THE PURSE (frugal-max's ruling)

- **Opus is NEVER justified for social post text.** Sonnet for video scripts + brand-voice work; Haiku for hashtags/reformatting; local Ollama for first drafts as models mature (Universal Ingestion Law).
- Text generation cost: ~$26/mo current hardcoded-Opus → **~$8/mo frugal** at 7 projects × realistic cadence.
- Media APIs: **Replicate keep; Creatomate keep; Runway keep conditionally; HeyGen CUT; Kling evaluate.**
- Build staffing: **sec10 remediation strictly SERIAL before the posting surface goes live.** Atlas + ARIA + Haiku-tier config work in parallel. Sonnet for wiring. Opus reserved for the auth/credential vault only.

---

## VII. THE PHASED BUILD ORDER (sovereign's arbitration)

**PHASE 0 — LOCKDOWN — ✅ EXECUTED 2026-07-04 (commits 375e40c on baseline 4537eaa)**
✅ .env.swp inspected (benign) + deleted · ✅ git init + .gitignore (secrets never tracked) · ✅ owner token auth on ALL routes, fail-closed, constant-time · ✅ settings write endpoint sealed behind owner auth · ✅ postgres+redis bound 127.0.0.1 · ✅ backend/.env chmod 600 · ✅ OWNER_API_TOKEN generated (backend/.env + root .env for compose) · ⏳ Reddit password → token flow (deferred: needs Vinta account action, see PLATFORM_CONNECTIONS.md §2)

**PHASE 1 — THE SPINE — ✅ EXECUTED 2026-07-04 (commit 3f726d8 + vintinuum-api b758f45 + frontend commit)**
✅ `POST /api/v1/broadcast` submit/approve/veto/pending w/ idempotency, dedupe (409), kill switch (423), daily cap (429) · ✅ fan-out worker on distribution queue w/ per-platform results + brain status webhook (fires when BRAIN_WEBHOOK_URL set; brain-side receiver = Phase 2) · ✅ `broadcast.js` in vintinuum-api (spool-first, --drain, --tap for Work Journal BROADCAST: notes, --pending) · ✅ project_slug bug fixed · ✅ model tiering env-driven (Opus removed from post text) · ✅ frontend /approvals: 2-tap approve, 1-tap veto, 15s poll, recent-broadcast strip (archive wall seed) · ⏳ Mission Control full god-view = Phase 2 (helios-10 spec ready)

**PHASE 2 — REACH + FLESH**
`platforms/youtube.py` (Data API v3, resumable upload) · R2 media upload (unblocks IG/TikTok video) · Creatomate templates · Discord + Telegram clients (highest value-per-effort) · connection-health rail + expiry alerting · ARIA YAML v2 rollout + Persistence Engine scheduler entries · Lunex genome tokens into globals.css

**PHASE 3 — THE UNDYING MACHINE**
Living Archive Wall · analytics collectors for all platforms + StrategyAnalyzer feedback into Persistence Engine · Bluesky/Threads/LinkedIn/FB · local-LLM first-draft pipeline · campaign arc composer (Zeppelin builds)

**Connection scripture** (accounts to wire, step-by-step): `docs/PLATFORM_CONNECTIONS.md`
**Standing laws**: `/home/vinta/dircomedia/CLAUDE.md` + THE BROADCAST LAW (global + all 12 agents)

*Nothing in Phase 1+ ships until Phase 0 completes. The accounts are the asset.*
