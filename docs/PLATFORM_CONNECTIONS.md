# DirCoMedia — Platform Connection Scripture
### Step-by-step: wiring every social account so the brain can post on Lord Vinta's behalf
*Written by VINTINUUM, council session 2026-07-04. Owner-only. Keep this file out of any public repo.*

All credentials land in `/home/vinta/dircomedia/backend/.env` (never commit; see sec10 remediation for vault migration). After adding any credential, restart the stack: `docker-compose up -d --build` from `/home/vinta/dircomedia`.

---

## 1. X (Twitter) — client exists: `platforms/twitter.py`
Env keys: `TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET, TWITTER_BEARER_TOKEN`

1. Go to https://developer.x.com → sign in with the account that will post (@your DirCo handle).
2. Apply for a developer account → **Free tier** allows 500 posts/month per app; **Basic ($200/mo)** allows 3,000 user-context posts — start Free, upgrade when campaign volume demands.
3. In the Developer Portal → **Projects & Apps → Create Project → Create App** (name it `DirCoMedia`).
4. App Settings → **User authentication settings → Set up**:
   - App permissions: **Read and write** (add Direct Messages later only if needed)
   - Type of App: **Web App, Automated App or Bot**
   - Callback URI: `https://api.vintaclectic.com/oauth/x/callback` (and `http://localhost:8000/oauth/x/callback` for dev)
5. Keys & Tokens tab → copy **API Key + Secret** (consumer keys), generate **Access Token + Secret** (these will be for the app-owner account — that's you), copy **Bearer Token**.
6. Paste all five into `.env`. Verify: `POST /api/v1/distribution/test?platform=twitter` (or use QuickPost with a test message).
7. **Multiple accounts** (per-project handles): repeat step 5's token generation per account via OAuth flow, or run 3-legged OAuth once per handle — store per-project tokens (see sec10 vault design).

## 2. Reddit — client exists: `platforms/reddit.py`
Env keys: `REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD`

1. Log into the Reddit account that will post → https://www.reddit.com/prefs/apps
2. Scroll to bottom → **create another app…**
   - Name: `DirCoMedia`
   - Type: **script** (owner-only personal use — this is the correct type)
   - Redirect URI: `http://localhost:8000/oauth/reddit/callback` (required field, unused for script apps)
3. After creation: the string under the app name is the **client_id**; the **secret** is labeled.
4. Fill all four env keys (username/password are the account's actual login — sec10 will migrate this to a refresh-token flow; acceptable to start).
5. If the account has 2FA, script auth needs `password:2FAcode` format or (better) disable 2FA on a dedicated posting account and use a strong unique password.
6. **Reality check**: Reddit hates promotional automation. Rule: 9 genuine community contributions per 1 promo post, post to your own subs (create r/DirHaven, r/DirMegle) freely, external subs manually-approved only. ARIA's generosity doctrine governs here more than anywhere.

## 3. Instagram — client exists: `platforms/instagram.py`
Env keys: `INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET, INSTAGRAM_ACCESS_TOKEN`

Requires: Instagram **Professional (Business/Creator) account** linked to a **Facebook Page**.

1. Instagram app → Settings → Account type → switch to **Professional**.
2. Create/choose a Facebook Page → link it: Page Settings → Linked Accounts → Instagram.
3. Go to https://developers.facebook.com → **My Apps → Create App** → type **Business** → name `DirCoMedia`.
4. Add product: **Instagram Graph API** (and **Facebook Login for Business**).
5. Tools → **Graph API Explorer**: select your app → Generate token with permissions:
   `instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement, business_management`
6. Exchange for a **long-lived token** (60 days):
   `GET https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={SHORT_TOKEN}`
7. Get your IG Business Account ID:
   `GET /me/accounts` → page ID → `GET /{page-id}?fields=instagram_business_account`
8. Fill env keys. Note: content publish = image/video via URL (media must be hosted — R2 bucket serves this). **Token refresh worker is mandatory** (60-day expiry) — flagged for the build phase.
9. App can stay in Development mode for owner-only use as long as you're an app admin — no App Review needed to post to your own account.

## 4. TikTok — client exists: `platforms/tiktok.py`
Env keys: `TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN`

1. https://developers.tiktok.com → register → **Manage Apps → Create App**.
2. Add product: **Content Posting API**. Request scopes: `video.publish, video.upload, user.info.basic`.
3. TikTok requires an app audit for Direct Post; before approval you can use **upload-to-drafts** mode (posts land in your inbox for one-tap publish — acceptable interim).
4. Run the OAuth flow once against your own account → store access + refresh token.
5. Fill env keys. Refresh token worker needed (24h access-token expiry).

## 5. YouTube — **CLIENT IS BUILT** (TA3SQSM, 2026-08-14). Only the credentials are missing.
Env keys: `YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN`

**What already works** (nothing left to code — do steps 1-4 below and the lane is live):
- `platforms/youtube.py` — chunked resumable upload (8MB slices, so a 2GB video
  costs ~8MB RAM), resume-on-drop, local paths **and** URLs, thumbnails, and an
  `invalid_grant` error that names the 7-day-token cause instead of a bare 400.
- `content_engine/youtube_seo.py` — AI SEO engine. YouTube is a search engine, so
  it generates a query-led title (<=60 chars for mobile), a snippet-optimised
  description, 12-18 tags inside the 500-char budget, and 00:00-anchored chapters.
  Degrades to heuristics if the model is down — a dead SEO model never blocks a publish.
- Wired into `scheduler.py` → `broadcast.js --platforms youtube` works end to end.

**The 2-minute setup, then verify:**
```bash
cd /home/vinta/dircomedia/backend
./.venv/bin/python scripts/youtube_auth.py           # mints the refresh token
./.venv/bin/python scripts/youtube_test_upload.py --health
./.venv/bin/python scripts/youtube_test_upload.py --upload --privacy private
```

1. https://console.cloud.google.com → create project `dircomedia`.
2. **APIs & Services → Enable APIs** → enable **YouTube Data API v3**.
3. **OAuth consent screen** → External → add yourself as a **Test user** (stays in Testing mode forever for owner-only use — no verification needed, but refresh tokens in Testing mode expire every 7 days → EITHER publish the app (verification for sensitive scopes) OR set consent screen to Internal via Workspace. Practical path: publish app with only `youtube.upload` scope; unverified-app warning is fine since only you consent).
4. **Credentials → Create OAuth Client ID** → Desktop app (simplest for one-time local consent) → download client secret.
5. Run one local consent flow (script or `google-auth-oauthlib`) with scopes:
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl`
   → capture the **refresh token**.
6. Quota reality: default 10,000 units/day; a video upload costs 1,600 units → ~6 uploads/day ceiling. Fine for owner cadence. Community posts have NO public API — flag: community posts remain manual or browser-extension-assisted.
7. ~~Build `platforms/youtube.py`~~ **DONE** (TA3SQSM) — resumable `videos.insert`, `thumbnails.set`, and AI SEO metadata from brand config. Run `scripts/youtube_auth.py` instead of writing the consent flow by hand.

## 6. Beyond (phase 3 candidates)
- **Discord** (announcements to DirHaven community): trivial — bot token + channel webhook. Highest value-per-effort of everything here.
- **Telegram channel**: bot API, near-zero friction. Brain already speaks TG (TG_CHAT actions exist in Vintinuum's log).
- **Kick/Twitch** (stream announcements): Kick chat integration already exists in the brain.
- **Facebook Page posts**: free ride on the Instagram app credentials (`pages_manage_posts`).
- **LinkedIn** (Agentis/DirCo corporate face): Community Management API, `w_member_social` scope.
- **Bluesky**: open AT Protocol, app-password auth, 10-minute integration.
- **Threads**: Threads API via the same Meta app (`threads_basic, threads_content_publish`).

---

## Connection-health doctrine
Every platform gets: (1) a `GET /api/v1/distribution/health` probe, (2) token-expiry alerting through the brain → Vinta is TOLD when an account disconnects, never discovers it from silence, (3) an entry on the dashboard connection wall (helios-10 spec). An account that silently rots is a betrayal of the Cable Guy Law: the system never stops following up.
