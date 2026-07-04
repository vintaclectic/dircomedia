# DirCoMedia — Project Instructions (owner-only marketing OS)

DirCoMedia is Lord Vinta's PERSONAL, single-tenant social media marketing OS for all
DirCo projects (agentis, dirco, dirhaven_app, dirhaven_rp, dirmegle, medaled,
vintinuum). It is not a product for others. Its job: when a project needs users and
attention, this machine delivers it — automated, brand-true, and safe for the accounts
it controls.

## Architecture (respect it)
- Backend: FastAPI + SQLAlchemy async + Celery/Redis + PostgreSQL (`backend/`)
- Frontend: Next.js 14 App Router + Tailwind, dark theme (`frontend/`)
- Workers: 3 Celery queues (content, video, distribution) + beat scheduler
- Platform clients: `backend/app/services/distribution/platforms/` (twitter, tiktok, instagram, reddit; youtube pending)
- Brand voice: `backend/brand_configs/{project_slug}.yaml` — voice lives HERE, never hardcoded
- Connection guide: `docs/PLATFORM_CONNECTIONS.md` — step-by-step for every platform

## Standing laws (in addition to global ~/.claude/CLAUDE.md)
1. **WORK JOURNAL LAW** — log every session via `node /home/vinta/vintinuum-api/worklog.js` (see global file).
2. **BROADCAST LAW** — every shipped user-facing update in ANY DirCo project flows through this app to social platforms, `approve-first` by default. This app IS the broadcast spine.
3. **THE ACCOUNTS ARE THE ASSET** — nothing may ever be able to spam-post. Rate caps, dedupe, idempotency keys, and circuit breakers on every posting path are non-negotiable. A bug that burns a social account burns years of reputation.
4. **OWNER-ONLY AUTH** — every posting endpoint requires owner authentication. The brain (api.vintaclectic.com) is the only remote caller. No unauthenticated posting surface, ever.
5. **APPROVE-FIRST DEFAULT** — brain-authored posts queue for Vinta's approval unless a project/platform is explicitly set to auto.
6. **GENEROSITY DOCTRINE (ARIA/Grateful Dead)** — free value : promotion ratio favors value. On Reddit especially: 9 community contributions per 1 promo.
7. **LOCAL-FIRST GENERATION** — prefer local models for post drafts where quality allows (Universal Ingestion Law); Claude tiers per frugal-max's standing ruling.
8. **SECRETS** — `.env` never committed; git repo must have `.gitignore` covering `.env*`, `*.swp`, media dirs BEFORE first commit.

## The book
**`docs/OWNERS_MANUAL.md`** — the complete operator's guide (setup, tokens,
account connection + fixes, daily workflow, broadcast.js, safety systems,
emergency brake, troubleshooting). Read it before touching anything else.

## To run
1. `backend/.env` from `.env.example`, fill keys (see `docs/PLATFORM_CONNECTIONS.md`)
2. `docker-compose up`
3. `POST /api/v1/projects/seed` to seed the 7 projects
4. Frontend at localhost:3000, API at localhost:8000

## Council artifacts (2026-07-04 session)
Council review deliverables (Atlas architecture, sec10 security ruling, helios-10
frontend reimagining, fusion broadcast contract, ARIA voice bibles, Lunex creative
genome, frugal-max cost ruling) are recorded in the Work Journal and inform all
future phases. Check the journal before restructuring anything.
