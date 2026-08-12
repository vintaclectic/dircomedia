# Stripe Setup Guide — DirCoMedia Path B (SaaS Billing)

**Purpose:** Enable subscription billing for multi-tenant DirCoMedia (20k-user Path B).

**Timeline:** 15 minutes to get test mode working; 1 hour for production.

---

## STEP 1: CREATE STRIPE ACCOUNT (IF NEW)

1. Go to [stripe.com](https://stripe.com) and click **Start now**
2. Sign up with Vinta's email: `vintaclectic@gmail.com`
3. Verify email and complete onboarding
4. Business name: `DirCoMedia` (or `Vinta LLC` if formal entity exists)
5. Skip identity verification for now (required before first live payout, not for testing)

**If you already have a Stripe account:** Log in at [dashboard.stripe.com](https://dashboard.stripe.com) and continue to Step 2.

---

## STEP 2: CREATE PRODUCTS & PRICES

Stripe Products = the subscription tiers. Prices = the recurring billing amounts.

### In Stripe Dashboard:

1. Click **Products** in left sidebar → **Add product**

2. **Product 1: DirCoMedia Creator**
   - Name: `DirCoMedia Creator`
   - Description: `100 posts/month, all platforms, AI captions, analytics`
   - **Pricing:**
     - Model: `Recurring`
     - Price: `$19.00 USD`
     - Billing period: `Monthly`
     - (Optional) Add yearly price: `$190.00 USD` (save $38 = 17% discount)
   - Click **Save product**
   - **Copy the Price ID** (starts with `price_...`, e.g. `price_1A2B3C4D5E6F7G8H`)
   - Paste into `.env` as `STRIPE_PRICE_CREATOR=price_...`

3. **Product 2: DirCoMedia Studio**
   - Name: `DirCoMedia Studio`
   - Description: `Unlimited posts, multi-brand, team seats, priority support`
   - Price: `$79.00 USD` monthly
   - Click **Save product**
   - Copy Price ID → `STRIPE_PRICE_STUDIO=price_...`

4. **Product 3: DirCoMedia Enterprise**
   - Name: `DirCoMedia Enterprise`
   - Description: `White-label, API access, dedicated support, unlimited everything`
   - Price: `$299.00 USD` monthly
   - Click **Save product**
   - Copy Price ID → `STRIPE_PRICE_ENTERPRISE=price_...`

**Result:** You now have 3 products. Next: get API keys.

---

## STEP 3: GET API KEYS

1. In Stripe Dashboard, click **Developers** (top right) → **API keys**

2. You'll see:
   - **Publishable key** (starts with `pk_test_...` for test mode)
   - **Secret key** (starts with `sk_test_...` for test mode) — click **Reveal test key**

3. **Copy both keys** and add to `/home/vinta/dircomedia/backend/.env`:
   ```bash
   STRIPE_SECRET_KEY=sk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   STRIPE_PUBLISHABLE_KEY=pk_test_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```

**IMPORTANT:** These are **test mode** keys. Real charges will NOT process with these. For production (after testing), toggle to **Live mode** (switch in top-right corner) and copy the `sk_live_...` and `pk_live_...` keys instead.

---

## STEP 4: CREATE WEBHOOK ENDPOINT

Webhooks let Stripe notify your backend when subscriptions are created/updated/canceled.

### In Stripe Dashboard:

1. Click **Developers** → **Webhooks** → **Add endpoint**

2. **Endpoint URL:**
   - **For local testing:** Use Stripe CLI (see Step 5)
   - **For deployed backend:** `https://api.dircomedia.app/api/v1/stripe/webhook`
     (Replace with your actual backend domain)

3. **Events to send:** Click **Select events**, then add:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
   - `invoice.payment_succeeded`

4. Click **Add endpoint**

5. **Copy the Signing secret** (starts with `whsec_...`)
   - Add to `.env`: `STRIPE_WEBHOOK_SECRET=whsec_...`

**Why webhooks?** When a user subscribes in Stripe Checkout, Stripe sends a `customer.subscription.created` event to your webhook → your backend upgrades their tier in the database. Without webhooks, you'd have to poll Stripe constantly (slow and inefficient).

---

## STEP 5: TEST LOCALLY WITH STRIPE CLI

Before deploying, test webhooks on your local dev server.

### Install Stripe CLI:

**Mac (Homebrew):**
```bash
brew install stripe/stripe-cli/stripe
```

**Linux (download):**
```bash
wget https://github.com/stripe/stripe-cli/releases/latest/download/stripe_linux_x86_64.tar.gz
tar -xvf stripe_linux_x86_64.tar.gz
sudo mv stripe /usr/local/bin/
```

**Windows (Scoop):**
```bash
scoop install stripe
```

### Login to Stripe CLI:

```bash
stripe login
```

This opens a browser → approve the CLI access.

### Forward webhooks to local server:

```bash
# Start your backend on port 8011
cd /home/vinta/dircomedia/backend
uvicorn app.main:app --reload --port 8011

# In another terminal, forward Stripe webhooks to localhost:
stripe listen --forward-to localhost:8011/api/v1/stripe/webhook
```

**Output:**
```
> Ready! Your webhook signing secret is whsec_XXXXXX (^C to quit)
```

Copy that `whsec_...` value → add to `.env` as `STRIPE_WEBHOOK_SECRET=whsec_...`

### Trigger a test event:

```bash
stripe trigger customer.subscription.created
```

Check your backend logs — you should see the webhook event printed.

---

## STEP 6: TEST CHECKOUT FLOW

Now test the full subscription signup flow.

### In your backend shell (with `.env` loaded):

```bash
cd /home/vinta/dircomedia/backend
source .env  # Load env vars
python3 -c "
import stripe
stripe.api_key = '$STRIPE_SECRET_KEY'

# Create a test customer
customer = stripe.Customer.create(email='test@example.com')
print(f'Customer ID: {customer.id}')

# Create a checkout session
session = stripe.checkout.Session.create(
    customer=customer.id,
    mode='subscription',
    line_items=[{
        'price': '$STRIPE_PRICE_CREATOR',  # Replace with actual Price ID
        'quantity': 1,
    }],
    success_url='http://localhost:3000/billing?success=true',
    cancel_url='http://localhost:3000/billing?canceled=true',
)
print(f'Checkout URL: {session.url}')
"
```

Open the printed URL in a browser. You'll see the Stripe Checkout page.

### Use Stripe test cards:

- **Success:** `4242 4242 4242 4242` (any future expiry, any CVC)
- **Payment fails:** `4000 0000 0000 0002`
- **3D Secure required:** `4000 0025 0000 3155`

Complete the checkout → Stripe sends `customer.subscription.created` webhook → your backend should upgrade the test user to Creator tier.

**Verify:** Check your backend logs for the webhook event handler output.

---

## STEP 7: WIRE INTO DIRCOMEDIA BACKEND

The Stripe integration files are already created (as of 2026-08-12):

```
backend/app/api/v1/stripe.py                     # API routes (webhook, checkout, portal)
backend/app/services/billing/webhooks.py         # Webhook event handlers
backend/app/services/billing/checkout.py         # Checkout session creation
backend/app/services/billing/portal.py           # Customer portal (manage billing)
backend/app/services/billing/entitlements.py     # Tier limits & feature checks
```

### Wire the routes into FastAPI:

Edit `/home/vinta/dircomedia/backend/app/main.py`:

```python
from app.api.v1 import stripe as stripe_routes

# Add to your API router includes:
app.include_router(stripe_routes.router, prefix="/api/v1")
```

### Add config variables:

Edit `/home/vinta/dircomedia/backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Stripe (Path B)
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_CREATOR: str
    STRIPE_PRICE_STUDIO: str
    STRIPE_PRICE_ENTERPRISE: str
    FRONTEND_URL: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
```

### Install Stripe SDK:

```bash
cd /home/vinta/dircomedia/backend
pip install stripe
# or if using Poetry:
poetry add stripe
```

---

## STEP 8: ADD USER MODEL FIELDS (PATH B — MULTI-TENANT)

**Note:** This is only needed for Path B (SaaS with user accounts). Path A (owner-only) doesn't need a User model.

When you build Path B, add these fields to your `User` model:

```python
from sqlalchemy import Column, String, DateTime, Enum

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    # ... other auth fields ...
    
    # Stripe fields
    stripe_customer_id = Column(String, unique=True, nullable=True)  # cus_XXXXX
    tier = Column(String, default="free")  # "free", "creator", "studio", "enterprise"
    subscription_status = Column(String, nullable=True)  # "active", "past_due", "canceled", "trialing"
    current_period_end = Column(DateTime, nullable=True)  # When subscription renews
    cancel_at_period_end = Column(Boolean, default=False)  # True if user canceled (still active until period ends)
```

Migration:
```bash
alembic revision --autogenerate -m "add stripe fields to users"
alembic upgrade head
```

---

## STEP 9: PRODUCTION MODE (LIVE PAYMENTS)

**Only do this when ready to accept real money.**

1. **Complete Stripe identity verification:**
   - Dashboard → **Settings** → **Business settings** → **Verify identity**
   - Upload ID, business info, bank account for payouts

2. **Toggle to Live mode:**
   - Top-right corner of Stripe Dashboard: switch **Test mode** → **Live mode**

3. **Get live API keys:**
   - **Developers** → **API keys** → copy `sk_live_...` and `pk_live_...`
   - Update `.env` with live keys (keep test keys in `.env.example`)

4. **Recreate products in Live mode:**
   - Products created in Test mode don't transfer to Live mode
   - Repeat Step 2 (create products) in Live mode → copy new live `price_...` IDs

5. **Create live webhook:**
   - Repeat Step 4 (webhook endpoint) in Live mode
   - URL: `https://api.dircomedia.app/api/v1/stripe/webhook` (your production backend)
   - Copy new live `whsec_...` secret

6. **Update `.env` on production server:**
   ```bash
   STRIPE_SECRET_KEY=sk_live_XXXXX
   STRIPE_PUBLISHABLE_KEY=pk_live_XXXXX
   STRIPE_WEBHOOK_SECRET=whsec_XXXXX
   STRIPE_PRICE_CREATOR=price_XXXXX  # Live mode Price IDs
   STRIPE_PRICE_STUDIO=price_XXXXX
   STRIPE_PRICE_ENTERPRISE=price_XXXXX
   ```

7. **Test with a real card:**
   - Use your own card to subscribe
   - Verify webhook fires
   - Immediately cancel the subscription (Customer Portal)

---

## STEP 10: MONITORING & ALERTS

Once live, monitor:

1. **Stripe Dashboard → Payments:**
   - Watch for failed payments (card declines, expired cards)
   - Stripe auto-retries; after final retry fails, subscription becomes "past_due"

2. **Webhook delivery:**
   - Dashboard → **Developers** → **Webhooks** → click your endpoint
   - See recent deliveries, failures, retry attempts
   - If webhook fails (5xx error from your backend), Stripe retries for 3 days

3. **Disputes & chargebacks:**
   - Dashboard → **Disputes**
   - Respond within 7 days (upload proof of service)

4. **Alerts:**
   - Set up **PagerDuty** or **Sentry** to alert on webhook failures
   - Send daily MRR (Monthly Recurring Revenue) report to owner

---

## STRIPE CLI CHEAT SHEET

```bash
# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8011/api/v1/stripe/webhook

# Trigger test events
stripe trigger customer.subscription.created
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.deleted

# View recent events
stripe events list

# Get details of an event
stripe events retrieve evt_XXXXX

# Create a test customer
stripe customers create --email test@example.com

# Create a test subscription
stripe subscriptions create \
  --customer cus_XXXXX \
  --items '[{"price": "price_XXXXX"}]'

# Cancel a subscription
stripe subscriptions cancel sub_XXXXX
```

---

## TROUBLESHOOTING

### Webhook not receiving events:

1. **Check webhook URL is publicly accessible:**
   ```bash
   curl -X POST https://api.dircomedia.app/api/v1/stripe/webhook \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```
   Should return 200 (even if signature validation fails).

2. **Check Stripe webhook logs:**
   - Dashboard → **Developers** → **Webhooks** → click endpoint → **Recent deliveries**
   - Shows request/response, error messages

3. **Verify signing secret is correct:**
   - Copy from Stripe Dashboard → paste into `.env`
   - Restart backend after changing `.env`

### Payment succeeds but tier not upgraded:

1. **Check webhook handler ran:**
   - Look for `handle_subscription_created` log in backend
2. **Check user lookup:**
   - `get_user_by_stripe_id()` must find the user
   - Ensure `stripe_customer_id` was saved when creating Stripe Customer
3. **Check database update:**
   - `user.tier = "creator"` and `await user.save()` must execute

### "Invalid signature" error:

- **Cause:** Wrong `STRIPE_WEBHOOK_SECRET` in `.env`
- **Fix:** Copy signing secret from Stripe Dashboard webhook page (starts with `whsec_...`)

---

## NEXT: PATH B SAAS EXPANSION

Stripe integration is **Step 3** of Path B (see `PATH_B_SAAS_EXPANSION.md`).

**Path B roadmap:**
1. ✅ User auth & registration (FastAPI-Users, JWT, email verify)
2. ✅ Per-user credential vaults (OAuth tokens scoped to user)
3. ✅ **Stripe billing** (this doc)
4. Rate limiting & moderation (Redis, Claude API)
5. Analytics dashboard (user-facing metrics)
6. Multi-brand (Studio+ tier)
7. Frontend overhaul (marketing site + authenticated app)
8. Deploy to production (Railway + Vercel)

**Estimated remaining time:** 20–30 days (solo) or 10 days (council strike team in parallel).

---

**Questions?** Check Stripe docs: [stripe.com/docs/billing/subscriptions/overview](https://stripe.com/docs/billing/subscriptions/overview)

---

*Written by seat-2 (council autonomous loop) — 2026-08-12*  
*Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>*
