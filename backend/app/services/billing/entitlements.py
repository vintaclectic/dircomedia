"""
Tier entitlements & rate limiting — enforce subscription limits.

Usage:
    from app.services.billing.entitlements import check_post_limit, TIER_LIMITS

    @router.post("/posts")
    async def create_post(user: User = Depends(get_current_user)):
        await check_post_limit(user)  # Raises HTTPException if limit exceeded
        # ... create post
"""
from fastapi import HTTPException
from app.models.user import User
from datetime import datetime, timedelta
# from app.db.session import async_session  # TODO: replace with your DB session
# from app.models.post import Post  # TODO: implement Post model


# Tier limits (free, creator, studio, enterprise)
TIER_LIMITS = {
    "free": {
        "posts_per_month": 5,
        "platforms": 2,
        "team_seats": 1,
        "brands": 1,
        "api_calls_per_minute": 10,
        "features": ["basic_scheduling"],
    },
    "creator": {
        "posts_per_month": 100,
        "platforms": 999,  # All platforms
        "team_seats": 1,
        "brands": 1,
        "api_calls_per_minute": 60,
        "features": ["basic_scheduling", "ai_captions", "analytics", "no_watermark"],
    },
    "studio": {
        "posts_per_month": 999999,  # Unlimited
        "platforms": 999,
        "team_seats": 10,
        "brands": 5,
        "api_calls_per_minute": 300,
        "features": ["basic_scheduling", "ai_captions", "analytics", "no_watermark", "multi_brand", "team", "priority_support"],
    },
    "enterprise": {
        "posts_per_month": 999999,
        "platforms": 999,
        "team_seats": 999,
        "brands": 999,
        "api_calls_per_minute": 999999,
        "features": ["basic_scheduling", "ai_captions", "analytics", "no_watermark", "multi_brand", "team", "priority_support", "white_label", "api_access", "dedicated_support"],
    },
}


async def check_post_limit(user: User):
    """
    Check if user has exceeded monthly post limit for their tier.

    Args:
        user: Authenticated user

    Raises:
        HTTPException(403) if limit exceeded
    """
    tier = user.tier or "free"
    limit = TIER_LIMITS[tier]["posts_per_month"]

    # Count posts this month
    # TODO: Replace with actual DB query
    # Example:
    # month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # async with async_session() as session:
    #     result = await session.execute(
    #         select(func.count(Post.id)).where(
    #             Post.user_id == user.id,
    #             Post.created_at >= month_start
    #         )
    #     )
    #     posts_this_month = result.scalar()

    # Stub for now
    posts_this_month = 0

    if posts_this_month >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Monthly post limit reached ({limit} posts for {tier} tier). Upgrade to continue."
        )


async def check_platform_access(user: User, platform: str):
    """
    Check if user's tier allows access to this platform.

    Free tier is limited to 2 platforms (user chooses which 2).
    All paid tiers have access to all platforms.

    Args:
        user: Authenticated user
        platform: Platform name (e.g. "twitter", "instagram")

    Raises:
        HTTPException(403) if platform not allowed
    """
    tier = user.tier or "free"
    if tier == "free":
        # TODO: Check user's selected platforms (stored in user.enabled_platforms JSON field)
        # For now, allow all
        pass


async def check_feature_access(user: User, feature: str):
    """
    Check if user's tier includes a feature.

    Args:
        user: Authenticated user
        feature: Feature name (e.g. "ai_captions", "analytics", "white_label")

    Raises:
        HTTPException(403) if feature not in tier
    """
    tier = user.tier or "free"
    allowed_features = TIER_LIMITS[tier]["features"]

    if feature not in allowed_features:
        raise HTTPException(
            status_code=403,
            detail=f"Feature '{feature}' requires {tier_with_feature(feature)} tier or higher."
        )


def tier_with_feature(feature: str) -> str:
    """
    Find lowest tier that includes a feature.

    Args:
        feature: Feature name

    Returns:
        Tier name (e.g. "creator")
    """
    for tier_name in ["free", "creator", "studio", "enterprise"]:
        if feature in TIER_LIMITS[tier_name]["features"]:
            return tier_name
    return "enterprise"


def get_tier_limits(tier: str) -> dict:
    """
    Get limits for a tier.

    Args:
        tier: Tier name

    Returns:
        Limits dict
    """
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])
