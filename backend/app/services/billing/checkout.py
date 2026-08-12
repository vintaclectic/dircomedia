"""
Stripe Checkout session creation — subscription signup flow.
"""
import stripe
from typing import Optional


async def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    trial_days: Optional[int] = None
) -> stripe.checkout.Session:
    """
    Create Stripe Checkout session for subscription signup.

    Args:
        customer_id: Stripe Customer ID (cus_XXXXX)
        price_id: Stripe Price ID (price_XXXXX)
        success_url: Redirect URL on successful payment
        cancel_url: Redirect URL if user cancels
        trial_days: Optional trial period (e.g. 14 for 14-day free trial)

    Returns:
        Stripe Checkout Session object

    Example:
        session = await create_checkout_session(
            customer_id="cus_ABC123",
            price_id="price_creator_monthly",
            success_url="https://app.dircomedia.app/billing?success=true",
            cancel_url="https://app.dircomedia.app/billing?canceled=true",
            trial_days=14  # Optional 14-day trial
        )
        # Redirect user to session.url
    """
    session_params = {
        "customer": customer_id,
        "mode": "subscription",
        "line_items": [
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "allow_promotion_codes": True,  # Let users apply promo codes at checkout
        "billing_address_collection": "auto",
        "subscription_data": {
            "metadata": {
                "source": "dircomedia_checkout"
            }
        }
    }

    # Add trial if specified
    if trial_days:
        session_params["subscription_data"]["trial_period_days"] = trial_days

    session = stripe.checkout.Session.create(**session_params)
    return session
