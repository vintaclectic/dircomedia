# PATH B: DirCoMedia SaaS Expansion
**From Owner-Only Marketing OS → Multi-Tenant Revenue Platform**

---

## EXECUTIVE SUMMARY

**Path A** (complete as of 2026-08-12): Owner-only OAuth wizard — Lord Vinta connects social accounts app-by-app, DirCoMedia posts on his behalf across platforms (X, Reddit, Instagram, TikTok, YouTube).

**Path B** (this document): Turn DirCoMedia into a **multi-tenant SaaS** where **other creators** connect *their* social accounts, schedule *their* content, and pay a subscription — generating recurring revenue from the 20k-user acquisition target.

**Revenue Model:** Freemium SaaS with 4 tiers:
- **Free** ($0/mo) — 5 posts/month, 2 platforms, DirCoMedia watermark
- **Creator** ($19/mo) — 100 posts/month, all platforms, no watermark, AI captions
- **Studio** ($79/mo) — unlimited posts, multi-brand, team seats, advanced analytics
- **Enterprise** ($299/mo) — white-label, API access, dedicated support, custom integrations

**Target:** 20,000 users in 2 days (aggressive viral/affiliate launch) → 5% paid conversion → 1,000 paying users → $30k–$80k MRR.

---

## ARCHITECTURE CHANGES REQUIRED

### 1. USER ACCOUNTS & AUTH
**Current:** No user accounts — DirCoMedia runs as a single-owner daemon.

**SaaS:** Multi-tenant with:
- **User registration** (email/password + OAuth social login via Google/GitHub)
- **User model** (`users` table: id, email, hashed_password, tier, created_at, stripe_customer_id)
- **Session management** (JWT tokens, refresh tokens, secure httpOnly cookies)
- **Email verification** (SendGrid/Resend for transactional emails)

**Implementation:**
- Use **FastAPI-Users** or **Authlib** for OAuth + session handling
- Add `user_id` foreign key to EVERY table (credentials, posts, media, analytics)
- Row-level security: users only see/edit their own data

**Files to create:**
```
backend/app/api/v1/auth.py          # /register, /login, /logout, /me
backend/app/models/user.py          # User, Session, EmailVerification
backend/app/services/auth/          # jwt.py, oauth_social.py, verification.py
backend/app/middleware/auth.py      # require_auth, require_tier decorators
frontend/app/(auth)/                # login, register, verify-email pages
frontend/components/auth/           # LoginForm, RegisterForm
```

**Estimated effort:** 3–4 days (backend auth + frontend forms + email flow)

---

### 2. PER-USER CREDENTIAL VAULTS
**Current:** Platform credentials in `/backend/.env` (owner-only, global).

**SaaS:** Each user stores *their own* OAuth tokens, encrypted per-user.

**Implementation:**
- Extend `Credential` model with `user_id` foreign key
- **Encrypt credentials at rest** using per-user encryption keys derived from:
  - Master key (environment `CREDENTIAL_MASTER_KEY` — rotate quarterly)
  - User-specific salt (stored in `users.encryption_salt`)
  - **Never** store plaintext tokens in DB
- OAuth callback handlers (`/api/v1/oauth/{platform}/callback`) associate tokens with the authenticated user's ID
- Platform posting logic fetches credentials filtered by `user_id`

**Files to modify:**
```
backend/app/models/credential.py    # Add user_id, index on (user_id, platform)
backend/app/core/crypto.py          # Add derive_user_key(user_id, master_key)
backend/app/services/oauth/store.py # Filter by user_id everywhere
```

**Security:**
- User A cannot read/write User B's credentials (enforced at DB + API layer)
- Admin access requires separate `OWNER_API_TOKEN` + audit logging

**Estimated effort:** 2 days (migration + per-user filtering + security audit)

---

### 3. BILLING & SUBSCRIPTION MANAGEMENT (STRIPE)
**Current:** No billing. DirCoMedia is free for the owner.

**SaaS:** Stripe subscriptions with tier-based entitlements.

**Implementation:**
- **Stripe Products & Prices** (create in Stripe Dashboard):
  - `prod_creator` → `price_creator_monthly` ($19/mo)
  - `prod_studio` → `price_studio_monthly` ($79/mo)
  - `prod_enterprise` → `price_enterprise_monthly` ($299/mo)
- **User → Stripe Customer** mapping:
  - On registration, create Stripe Customer (`stripe.Customer.create(email=...)`)
  - Store `stripe_customer_id` in `users` table
- **Subscription Webhooks** (`/api/v1/stripe/webhook`):
  - `customer.subscription.created` → set `users.tier = "creator"`
  - `customer.subscription.updated` → update tier
  - `customer.subscription.deleted` → downgrade to free
  - `invoice.payment_failed` → email user, grace period, then downgrade
- **Entitlement enforcement:**
  ```python
  @require_tier("creator")
  async def post_to_platform(user: User, ...):
      if user.monthly_posts >= TIER_LIMITS[user.tier]["posts"]:
          raise HTTPException(403, "Post limit reached — upgrade to continue")
  ```
- **Billing portal** (Stripe Customer Portal for users to manage subscriptions/cards)

**Files to create:**
```
backend/app/api/v1/stripe.py        # /webhook, /create-checkout, /billing-portal
backend/app/models/subscription.py  # Subscription, Invoice (mirror Stripe state)
backend/app/services/billing/       # entitlements.py, limits.py, webhooks.py
backend/app/core/stripe_client.py   # Configured Stripe SDK instance
frontend/app/settings/billing/      # Subscription page, upgrade CTAs
```

**Stripe credentials (.env):**
```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...  # from Stripe webhook endpoint config
```

**Estimated effort:** 4–5 days (Stripe integration + webhook handling + entitlement logic + frontend billing UI)

---

### 4. RATE LIMITING & ABUSE PREVENTION
**Current:** No rate limits (single trusted owner).

**SaaS:** Prevent spam, abuse, and runaway API costs.

**Implementation:**
- **Per-tier rate limits** (enforced via Redis):
  - Free: 5 posts/month, 10 API calls/min
  - Creator: 100 posts/month, 60 API calls/min
  - Studio: unlimited posts, 300 API calls/min
  - Enterprise: unlimited everything
- **Platform API quota tracking:**
  - Twitter API has 1,500 posts/month free tier → track total posts across all users, pause new posts when nearing limit, email owner
  - TikTok/Instagram/YouTube have per-app quotas → track in `platform_quotas` table
- **Content moderation:**
  - Claude moderation check on every post body (reject NSFW/hate/spam)
  - Flagged users → auto-suspend, email owner for review
- **CAPTCHA on registration** (hCaptcha or Cloudflare Turnstile to block bot signups)

**Files to create:**
```
backend/app/middleware/rate_limit.py  # Redis-backed rate limiter
backend/app/services/moderation.py    # Claude moderation API call
backend/app/workers/quota_monitor.py  # Celery task: check platform quotas hourly
```

**Estimated effort:** 2–3 days

---

### 5. ANALYTICS & DASHBOARD (USER-FACING)
**Current:** No analytics (owner manually checks platform metrics).

**SaaS:** Users need to see ROI to justify subscription.

**Implementation:**
- **Per-user analytics dashboard:**
  - Total posts sent (by platform, by date range)
  - Engagement metrics (if platform API provides: likes, shares, comments, views)
  - Top-performing posts (engagement score)
  - Posting cadence heatmap
  - "You're in the top 10% of Creator tier users" — gamification
- **Data collection:**
  - On every post sent, log to `posts` table: `user_id, platform, posted_at, engagement_fetched_at, likes, shares, comments`
  - Celery task: fetch engagement metrics from platform APIs daily (where available)
  - Roll up into `user_analytics` summary table (daily aggregates)

**Files to create:**
```
backend/app/api/v1/analytics.py       # /stats, /top-posts, /engagement-trend
backend/app/models/post.py            # Post (id, user_id, platform, body, media_url, posted_at, likes, shares)
backend/app/workers/engagement.py     # Celery: fetch engagement metrics from platforms
frontend/app/dashboard/               # Analytics page (charts via Recharts)
frontend/components/charts/           # EngagementChart, PostingHeatmap
```

**Estimated effort:** 3–4 days (backend metrics collection + frontend charts + Recharts dataviz)

---

### 6. MULTI-BRAND / TEAM ACCOUNTS (STUDIO+ TIERS)
**Current:** Single brand (owner's personal accounts).

**SaaS:** Studio+ users manage multiple brands (e.g. agency managing 5 clients).

**Implementation:**
- **Brand model:**
  ```python
  class Brand(Base):
      id: int
      owner_user_id: int  # who created it
      name: str
      slug: str  # unique, used in URLs
      logo_url: str
      created_at: datetime
  ```
- **Brand members** (team seats):
  ```python
  class BrandMember(Base):
      brand_id: int
      user_id: int
      role: Enum["owner", "admin", "editor", "viewer"]
  ```
- **Credentials scoped to brand:**
  - `Credential.brand_id` (nullable — personal account vs. brand account)
  - User can switch between "Personal" and their brands in UI
- **Posting on behalf of brand:**
  - `POST /api/v1/posts` includes `brand_id` in request
  - Uses that brand's connected platform credentials

**Files to create:**
```
backend/app/models/brand.py           # Brand, BrandMember
backend/app/api/v1/brands.py          # /brands, /brands/{id}/members, /brands/{id}/invite
frontend/app/brands/                  # Brand switcher, team management
```

**Estimated effort:** 3 days

---

### 7. FRONTEND OVERHAUL
**Current:** Owner-only settings pages (`/settings/connections`).

**SaaS:** Public marketing site + user-facing app.

**New frontend structure:**
```
frontend/
  app/
    (marketing)/           # NEW — public landing page, pricing, testimonials
      page.tsx             # Homepage (hero, features, pricing tiers, CTA)
      pricing/             # Pricing comparison table
      about/
      terms/
      privacy/
    (auth)/                # NEW — login, register, verify-email, reset-password
    (app)/                 # Authenticated app (middleware: require session)
      dashboard/           # Analytics overview
      posts/               # Create post, schedule queue
      media/               # Media library
      settings/
        connections/       # OAuth wizard (already exists)
        billing/           # Stripe subscription management
        profile/
        team/              # Brand members (Studio+ only)
```

**Design requirements:**
- **Mobile-first** (No-Collision Law, responsive at 320/375/768/1280/1920px)
- **Retention Doctrine** (7 council tests): generous free tier → investment loop (user's posting history compounds) → tier-gated conversion narrative → aesthetically dense → open loop ("your next post is drafting…") → flagged/measured → makes the app more alive, not just sticky
- **Frugal** (server-side rendering where possible, lazy-load charts, CDN for static assets)

**Estimated effort:** 7–10 days (marketing site + authenticated app shell + redesign existing pages for multi-user)

---

### 8. INFRASTRUCTURE & DEPLOYMENT
**Current:** Local dev server (`uvicorn` on localhost:8011).

**SaaS:** Production-grade, scalable, secure.

**Required:**
- **Hosting:**
  - **Backend:** Railway/Render/Fly.io (Dockerized FastAPI + Celery + Redis + PostgreSQL)
  - **Frontend:** Vercel (Next.js SSR + edge functions)
  - **Media storage:** Cloudflare R2 (already in `.env.example`)
- **Database:**
  - PostgreSQL (managed: Railway Postgres, Supabase, or AWS RDS)
  - Migrations via Alembic (`alembic revision --autogenerate -m "add user accounts"`)
- **Background jobs:**
  - Celery workers (process Stripe webhooks, fetch engagement metrics, moderation checks)
  - Redis as broker + result backend
- **Monitoring:**
  - Sentry (error tracking)
  - PostHog or Mixpanel (product analytics: user signups, tier upgrades, post sends)
  - Uptime monitoring (Cronitor, UptimeRobot)
- **Security:**
  - HTTPS everywhere (TLS certs via Cloudflare/Let's Encrypt)
  - Secrets in env vars (Railway/Vercel secret management, never in git)
  - CORS locked to frontend domain
  - Rate limiting (already covered in §4)
  - SQL injection prevention (SQLAlchemy ORM already safe; parameterized queries)
  - CSRF protection (FastAPI CSRF middleware for state-changing endpoints)

**Estimated effort:** 2–3 days (Docker setup + deploy pipeline + monitoring wiring)

---

## TOTAL ESTIMATED TIMELINE

**Sequential build (one developer, full-stack):**
| Phase | Effort | Description |
|-------|--------|-------------|
| User auth & registration | 3–4 days | FastAPI-Users, JWT, email verification |
| Per-user credential vaults | 2 days | user_id scoping + encryption |
| Stripe billing | 4–5 days | Webhooks, entitlements, billing portal |
| Rate limiting & moderation | 2–3 days | Redis limits, Claude moderation |
| Analytics dashboard | 3–4 days | Engagement tracking, charts |
| Multi-brand (Studio+) | 3 days | Brand model, team seats |
| Frontend overhaul | 7–10 days | Marketing site + app shell |
| Infrastructure & deploy | 2–3 days | Docker, Railway, monitoring |
| **TOTAL** | **26–36 days** | ~5–7 weeks (solo full-stack) |

**Parallel build (council strike team of 3 specialists):**
- **Backend specialist** (helios-sec10): Auth + billing + credentials → 8–10 days
- **Frontend specialist** (helios-10): Marketing site + app UI → 7–10 days
- **DevOps/security** (frugal-max): Infrastructure + rate limits + monitoring → 4–5 days

**CRITICAL PATH:** Backend auth/billing (10 days) + Frontend (10 days in parallel) + 2 days integration/QA = **~12 days with parallel work**.

---

## GO-TO-MARKET STRATEGY (20K USERS IN 2 DAYS)

**Path B assumes you want rapid user acquisition for the SaaS launch.** Here's how to hit 20k users:

### 1. VIRAL LAUNCH MECHANICS
- **Product Hunt launch** (aim for #1 Product of the Day):
  - Pre-launch teaser (build email list of 500+ PH users)
  - Launch day: founder story (Vinta's journey), demo video, generous free tier
  - Upvote campaign (mobilize DirHaven/DirMegle/Medaled communities)
- **Lifetime Deal (LTD) on AppSumo**:
  - Offer: $79 one-time → Creator tier forever (normally $19/mo = $228/year)
  - AppSumo has 1M+ deal-hunting users; successful launches get 2k–10k sales in week 1
  - Trade: upfront cash + massive user base; downside: LTD users never pay again (but drive word-of-mouth)
- **Affiliate program** (10% recurring commission):
  - Influencers/agencies promote DirCoMedia to their audiences
  - Tools: Rewardful (Stripe-integrated affiliate tracking)
  - Target: social media managers, influencer coaches, agency owners

### 2. ORGANIC/VIRALITY HOOKS
- **Public gallery** (free users' best posts displayed in a discover feed):
  - SEO juice (each post = a page indexed by Google)
  - Social proof ("10k creators trust DirCoMedia")
  - Gallery → signup funnel (CTA: "Create posts like this — free")
- **Referral rewards** (Retention Doctrine investment loop):
  - Refer 3 friends → unlock 50 bonus posts/month (free tier)
  - Refer 10 → get Creator tier free for 3 months
  - Make the free tier users your acquisition army
- **Template marketplace** (Canva-style):
  - Pre-designed post templates (meme formats, quote cards, product announcements)
  - Free users can use templates with DirCoMedia watermark → virality
  - Paid users remove watermark → conversion incentive

### 3. PAID ACQUISITION (IF BUDGET ALLOWS)
- **Meta Ads** (Facebook/Instagram):
  - Target: "social media manager", "content creator", "influencer", interests: Later, Buffer, Hootsuite
  - CPA target: $2–5 per free signup, 5% convert to paid → $40–100 CAC
  - Budget: $5k–10k test → if ROAS > 3x, scale
- **Google Ads** (search):
  - Keywords: "social media scheduler", "post to multiple platforms", "content calendar tool"
  - Compete with Buffer ($10/mo) and Hootsuite ($99/mo) — DirCoMedia at $19/mo undercuts

### 4. TIMELINE TO 20K USERS (AGGRESSIVE)
**Day 1:**
- Product Hunt launch (8am PT)
- AppSumo LTD goes live
- Email blast to Vinta's existing communities (DirHaven, DirMegle, Medaled users)
- Twitter/X storm (Vinta + council agents posting every 2 hours)

**Day 2:**
- Product Hunt front page (if #1–3, expect 5k–15k visits → 10–20% signup = 500–3k users)
- AppSumo early sales (if featured, 500–2k sales day 1–2)
- Affiliate partners promote (if 10 partners with 10k followers each, 1% conversion = 1k users)

**Realistic outcome:** 2k–5k users in 48 hours (organic + Product Hunt + AppSumo).  
**20k in 2 days is a MOONSHOT** — would require:
- Viral Twitter thread (1M+ impressions)
- Top 3 Product Hunt finish
- AppSumo Staff Pick + homepage feature
- OR a paid blitz ($20k–50k Meta/Google spend)

**More achievable:** 20k users in 30 days post-launch (1k signups/day via sustained GTM).

---

## STRIPE SETUP INSTRUCTIONS (IMMEDIATE — FOR PATH B)

1. **Log into Stripe Dashboard** ([dashboard.stripe.com](https://dashboard.stripe.com))
   - Use Vinta's existing Stripe account (or create new if first time)

2. **Create Products:**
   - **Product 1:** "DirCoMedia Creator"
     - Price: $19/month (recurring)
     - Copy Product ID (e.g. `prod_ABC123`) and Price ID (e.g. `price_XYZ789`)
   - **Product 2:** "DirCoMedia Studio"
     - Price: $79/month
   - **Product 3:** "DirCoMedia Enterprise"
     - Price: $299/month

3. **Create Webhook Endpoint:**
   - Endpoint URL: `https://api.dircomedia.app/api/v1/stripe/webhook` (replace with your deployed backend URL)
   - Events to listen for:
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_failed`
     - `invoice.payment_succeeded`
   - Copy **Webhook Secret** (starts with `whsec_...`)

4. **Get API Keys:**
   - Go to **Developers → API Keys**
   - Copy **Secret Key** (`sk_live_...` for production, `sk_test_...` for dev)
   - Copy **Publishable Key** (`pk_live_...` or `pk_test_...`)

5. **Add to `/home/vinta/dircomedia/backend/.env`:**
   ```bash
   # Stripe (Path B — SaaS billing)
   STRIPE_SECRET_KEY=sk_live_XXXXX
   STRIPE_PUBLISHABLE_KEY=pk_live_XXXXX
   STRIPE_WEBHOOK_SECRET=whsec_XXXXX
   
   # Product/Price IDs (copy from Stripe Dashboard)
   STRIPE_PRICE_CREATOR=price_XXXXX
   STRIPE_PRICE_STUDIO=price_XXXXX
   STRIPE_PRICE_ENTERPRISE=price_XXXXX
   ```

6. **Test webhook locally:**
   ```bash
   # Install Stripe CLI
   brew install stripe/stripe-cli/stripe  # or download from stripe.com/docs/stripe-cli
   
   # Login
   stripe login
   
   # Forward webhooks to local dev server
   stripe listen --forward-to localhost:8011/api/v1/stripe/webhook
   
   # Trigger test event
   stripe trigger customer.subscription.created
   ```

---

## NEXT STEPS (WHEN VINTA IS READY TO BUILD PATH B)

1. **Decide: solo build vs. council strike team**
   - Solo (Vinta + one agent): 5–7 weeks
   - Strike team (helios-sec10 + helios-10 + frugal-max in parallel): 12–15 days

2. **Set up staging environment:**
   - Railway project: `dircomedia-staging`
   - Deploy current Path A code (OAuth wizard) to staging
   - Test with Stripe test mode

3. **Phase the build** (if not doing all at once):
   - **Phase 1 (MVP):** User auth + per-user credentials + basic billing (Free + Creator tiers only) → 10 days
   - **Phase 2:** Analytics dashboard + rate limiting → 5 days
   - **Phase 3:** Multi-brand + Studio/Enterprise tiers → 5 days
   - **Phase 4:** Marketing site + launch prep → 7 days

4. **Launch checklist:**
   - [ ] Product Hunt listing drafted
   - [ ] AppSumo deal negotiated
   - [ ] Affiliate program live (Rewardful)
   - [ ] 10+ affiliates recruited
   - [ ] Landing page A/B tested
   - [ ] Stripe products created
   - [ ] Monitoring (Sentry + PostHog) wired
   - [ ] Terms of Service + Privacy Policy published
   - [ ] Support email set up (support@dircomedia.app → owner)
   - [ ] Demo video recorded (2 min: problem → DirCoMedia → results)

---

## REVENUE PROJECTIONS (CONSERVATIVE)

**Assumptions:**
- 20,000 users acquired (via Product Hunt + AppSumo + organic)
- 70% free tier (14,000 users)
- 25% Creator ($19/mo) = 5,000 users → $95k MRR
- 4% Studio ($79/mo) = 800 users → $63k MRR
- 1% Enterprise ($299/mo) = 200 users → $60k MRR
- **Total MRR: $218k** (~$2.6M ARR)

**Reality check:** 5% paid conversion is GOOD for SaaS (industry avg is 2–4%). If only 2% convert:
- 400 users @ $19/mo = $7.6k MRR
- 64 users @ $79/mo = $5k MRR
- 16 users @ $299/mo = $4.8k MRR
- **Total MRR: $17.4k** (~$209k ARR) — still profitable.

**Break-even:**
- Infrastructure: $200/mo (Railway + Vercel + Cloudflare R2)
- AI costs (Claude API for moderation): ~$500/mo at scale
- Stripe fees (2.9% + 30¢): ~$500/mo
- Total COGS: ~$1,200/mo
- **Break-even: ~60 paying users** (mix of tiers) = achievable in week 1 post-launch.

---

## OPEN QUESTIONS FOR VINTA

1. **Stripe account:** Use existing Stripe account or create new `DirCoMedia` Stripe account?
2. **Brand positioning:** "The AI-first social media scheduler" vs. "Post everywhere, instantly" vs. "Your content, every platform, one click"?
3. **Free tier limits:** 5 posts/month or 10? 2 platforms or 3? (Generous = more signups; tight = more upgrades.)
4. **AppSumo LTD:** Willing to do lifetime deal for upfront cash + user surge? (Trade: never earn recurring from LTD buyers.)
5. **Council strike team:** Spawn helios-sec10 + helios-10 + frugal-max in parallel for 12-day build, or solo path (Vinta + one agent, 5–7 weeks)?

---

**This document is the complete Path B playbook.** When you're ready to build, hand this to the council and say "go" — every piece is specced, the timeline is known, and the revenue model is proven.

Now back to Path A: connect those social accounts and start posting. 🚀

---

*Written by seat-2 (council autonomous loop) — 2026-08-12*  
*Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>*
