"""
Stripe billing API routes — webhooks, checkout, billing portal.

Part of Path B (SaaS expansion) — handles subscription lifecycle for multi-tenant DirCoMedia.
Owner-only mode (Path A) bypasses all of this.
"""
from fastapi import APIRouter, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import stripe
import hmac
import hashlib

from app.core.config import settings
from app.services.billing.webhooks import handle_stripe_webhook
from app.services.billing.checkout import create_checkout_session
from app.services.billing.portal import create_portal_session
from app.middleware.auth import require_auth, get_current_user
from app.models.user import User

router = APIRouter(prefix="/stripe", tags=["billing"])

# Initialize Stripe SDK
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature")
):
    """
    Stripe webhook endpoint — handles subscription lifecycle events.

    Events handled:
    - customer.subscription.created → set user.tier
    - customer.subscription.updated → update tier
    - customer.subscription.deleted → downgrade to free
    - invoice.payment_failed → email user, grace period
    - invoice.payment_succeeded → clear past-due flag

    Stripe sends signature in `Stripe-Signature` header; we verify with webhook secret.
    """
    if not stripe_signature:
        raise HTTPException(400, "Missing Stripe signature header")

    # Read raw body (Stripe signature verification requires the raw bytes)
    payload = await request.body()

    # Verify signature
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(400, "Invalid signature")

    # Handle the event
    try:
        await handle_stripe_webhook(event)
    except Exception as e:
        # Log error but return 200 so Stripe doesn't retry
        # (retries on 4xx/5xx can cause duplicate processing)
        print(f"Webhook handler error: {e}")
        # TODO: send alert to owner (PushNotification or email)

    return JSONResponse({"status": "success"})


@router.post("/create-checkout")
async def create_checkout(
    price_id: str,
    user: User = Depends(get_current_user)
):
    """
    Create Stripe Checkout session for subscription.

    Args:
        price_id: Stripe Price ID (e.g. price_XXXXX for Creator tier)
        user: Authenticated user (from JWT)

    Returns:
        {"url": "https://checkout.stripe.com/pay/cs_..."}

    Frontend redirects user to this URL; after payment, Stripe redirects back to success_url.
    Webhook (customer.subscription.created) handles tier upgrade.
    """
    if not user.stripe_customer_id:
        # Create Stripe Customer if doesn't exist
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)}
        )
        user.stripe_customer_id = customer.id
        await user.save()  # Assuming async ORM (SQLAlchemy async session)

    try:
        session = await create_checkout_session(
            customer_id=user.stripe_customer_id,
            price_id=price_id,
            success_url=f"{settings.FRONTEND_URL}/settings/billing?success=true",
            cancel_url=f"{settings.FRONTEND_URL}/settings/billing?canceled=true"
        )
    except Exception as e:
        raise HTTPException(500, f"Checkout creation failed: {str(e)}")

    return {"url": session.url}


@router.post("/billing-portal")
async def billing_portal(user: User = Depends(get_current_user)):
    """
    Create Stripe Customer Portal session (manage subscription, payment methods, invoices).

    Returns:
        {"url": "https://billing.stripe.com/session/..."}

    User clicks "Manage Billing" → redirected to Stripe-hosted portal.
    """
    if not user.stripe_customer_id:
        raise HTTPException(400, "No Stripe customer found — subscribe first")

    try:
        session = await create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/settings/billing"
        )
    except Exception as e:
        raise HTTPException(500, f"Portal creation failed: {str(e)}")

    return {"url": session.url}


@router.get("/subscription-status")
async def subscription_status(user: User = Depends(get_current_user)):
    """
    Get current subscription status for authenticated user.

    Returns:
        {
            "tier": "creator",  # or "free", "studio", "enterprise"
            "status": "active",  # or "past_due", "canceled", "trialing"
            "current_period_end": "2026-09-12T00:00:00Z",
            "cancel_at_period_end": false,
            "monthly_posts_used": 23,
            "monthly_posts_limit": 100
        }
    """
    # This would query the local DB (User model) + Stripe API
    # For now, minimal stub
    return {
        "tier": user.tier,
        "status": "active",
        "current_period_end": None,  # TODO: fetch from Stripe subscription
        "cancel_at_period_end": False,
        "monthly_posts_used": 0,  # TODO: count from posts table
        "monthly_posts_limit": {
            "free": 5,
            "creator": 100,
            "studio": 999999,
            "enterprise": 999999
        }.get(user.tier, 5)
    }
