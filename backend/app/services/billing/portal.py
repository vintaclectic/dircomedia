"""
Stripe Customer Portal session creation — self-service billing management.
"""
import stripe


async def create_portal_session(
    customer_id: str,
    return_url: str
) -> stripe.billing_portal.Session:
    """
    Create Stripe Customer Portal session.

    The Customer Portal is a Stripe-hosted page where users can:
    - Update payment methods
    - View invoices
    - Cancel subscription
    - Download receipts

    Args:
        customer_id: Stripe Customer ID (cus_XXXXX)
        return_url: URL to redirect back to after user finishes

    Returns:
        Stripe BillingPortal Session object

    Example:
        session = await create_portal_session(
            customer_id="cus_ABC123",
            return_url="https://app.dircomedia.app/settings/billing"
        )
        # Redirect user to session.url
    """
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url
    )
    return session
