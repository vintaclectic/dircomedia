"""
Stripe webhook event handlers — subscription lifecycle.

Handles:
- customer.subscription.created → upgrade user tier
- customer.subscription.updated → sync tier changes
- customer.subscription.deleted → downgrade to free
- invoice.payment_failed → alert user, grace period
- invoice.payment_succeeded → clear past-due flag
"""
from typing import Dict, Any
import stripe
from app.models.user import User
from app.core.email import send_email  # TODO: implement email service
# from app.db.session import async_session  # TODO: replace with your async DB session

# Tier mapping: Stripe Price ID → tier name
PRICE_TO_TIER = {
    # These will be populated from settings.STRIPE_PRICE_CREATOR, etc.
    # For now, hardcoded examples:
    "price_creator_monthly": "creator",
    "price_studio_monthly": "studio",
    "price_enterprise_monthly": "enterprise",
}


async def handle_stripe_webhook(event: stripe.Event):
    """
    Route Stripe webhook events to appropriate handlers.

    Args:
        event: Stripe Event object (already verified signature in API route)
    """
    event_type = event["type"]
    data = event["data"]["object"]  # The subscription, invoice, or customer object

    handlers = {
        "customer.subscription.created": handle_subscription_created,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.payment_failed": handle_payment_failed,
        "invoice.payment_succeeded": handle_payment_succeeded,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(data)
    else:
        print(f"Unhandled webhook event: {event_type}")


async def handle_subscription_created(subscription: Dict[str, Any]):
    """
    New subscription created → upgrade user tier.

    Args:
        subscription: Stripe Subscription object
    """
    customer_id = subscription["customer"]
    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = PRICE_TO_TIER.get(price_id, "free")

    # Find user by stripe_customer_id
    user = await get_user_by_stripe_id(customer_id)
    if not user:
        print(f"Webhook error: no user found for Stripe customer {customer_id}")
        return

    # Upgrade tier
    user.tier = tier
    user.subscription_status = subscription["status"]
    user.current_period_end = subscription["current_period_end"]
    await user.save()

    print(f"User {user.id} upgraded to {tier} (subscription {subscription['id']})")
    # TODO: send welcome email with tier benefits


async def handle_subscription_updated(subscription: Dict[str, Any]):
    """
    Subscription updated (tier change, renewal, etc.) → sync user tier.

    Args:
        subscription: Stripe Subscription object
    """
    customer_id = subscription["customer"]
    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = PRICE_TO_TIER.get(price_id, "free")

    user = await get_user_by_stripe_id(customer_id)
    if not user:
        return

    # Sync tier and status
    user.tier = tier
    user.subscription_status = subscription["status"]
    user.current_period_end = subscription["current_period_end"]
    user.cancel_at_period_end = subscription["cancel_at_period_end"]
    await user.save()

    print(f"User {user.id} subscription updated: {tier}, status={subscription['status']}")


async def handle_subscription_deleted(subscription: Dict[str, Any]):
    """
    Subscription canceled/ended → downgrade to free tier.

    Args:
        subscription: Stripe Subscription object
    """
    customer_id = subscription["customer"]

    user = await get_user_by_stripe_id(customer_id)
    if not user:
        return

    # Downgrade to free
    user.tier = "free"
    user.subscription_status = "canceled"
    user.current_period_end = None
    await user.save()

    print(f"User {user.id} downgraded to free (subscription ended)")
    # TODO: send "we're sorry to see you go" email with win-back offer


async def handle_payment_failed(invoice: Dict[str, Any]):
    """
    Payment failed → email user, set grace period.

    Stripe retries failed payments automatically (smart retries).
    After final retry fails, subscription status becomes "past_due" or "canceled".

    Args:
        invoice: Stripe Invoice object
    """
    customer_id = invoice["customer"]

    user = await get_user_by_stripe_id(customer_id)
    if not user:
        return

    # Mark as past due
    user.subscription_status = "past_due"
    await user.save()

    # Email user
    # await send_email(
    #     to=user.email,
    #     subject="Payment failed — update your card",
    #     body=f"Your payment of ${invoice['amount_due']/100} failed. Update your payment method: {settings.FRONTEND_URL}/settings/billing"
    # )

    print(f"Payment failed for user {user.id} (invoice {invoice['id']})")


async def handle_payment_succeeded(invoice: Dict[str, Any]):
    """
    Payment succeeded → clear past-due flag, confirm renewal.

    Args:
        invoice: Stripe Invoice object
    """
    customer_id = invoice["customer"]

    user = await get_user_by_stripe_id(customer_id)
    if not user:
        return

    # Clear past-due status
    if user.subscription_status == "past_due":
        user.subscription_status = "active"
        await user.save()
        print(f"User {user.id} payment recovered (invoice {invoice['id']})")


async def get_user_by_stripe_id(stripe_customer_id: str) -> User | None:
    """
    Find user by Stripe customer ID.

    Args:
        stripe_customer_id: Stripe Customer ID (cus_XXXXX)

    Returns:
        User object or None
    """
    # TODO: Replace with your async DB query
    # Example with SQLAlchemy async:
    # async with async_session() as session:
    #     result = await session.execute(
    #         select(User).where(User.stripe_customer_id == stripe_customer_id)
    #     )
    #     return result.scalars().first()

    # Stub for now
    print(f"TODO: query User where stripe_customer_id = {stripe_customer_id}")
    return None
