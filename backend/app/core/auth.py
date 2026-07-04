"""
Owner authentication — DirCoMedia is a single-tenant, owner-only system.

Every API route (except /health) requires the owner token. The token lives in
OWNER_API_TOKEN (backend/.env). Callers present it as either:

    Authorization: Bearer <token>
    X-Owner-Token: <token>

The brain (vintinuum-api / api.vintaclectic.com) is the only expected remote
principal; the Next.js frontend sends the same token from
NEXT_PUBLIC_OWNER_TOKEN.

FAIL-CLOSED: if OWNER_API_TOKEN is unset/blank, all authenticated routes
return 503 rather than allowing anonymous access. Comparison is constant-time.

Council decree 2026-07-04, Phase 0 — the accounts are the asset.
"""
import hmac

from fastapi import Header, HTTPException
from typing import Optional

from app.config import settings


def _extract_token(authorization: Optional[str], x_owner_token: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_owner_token:
        return x_owner_token.strip()
    return ""


async def require_owner(
    authorization: Optional[str] = Header(default=None),
    x_owner_token: Optional[str] = Header(default=None),
) -> None:
    expected = (settings.owner_api_token or "").strip()
    if not expected:
        # Fail closed — never run an unauthenticated posting surface.
        raise HTTPException(
            status_code=503,
            detail="OWNER_API_TOKEN is not configured; refusing anonymous access.",
        )
    presented = _extract_token(authorization, x_owner_token)
    if not presented or not hmac.compare_digest(presented, expected):
        raise HTTPException(status_code=401, detail="Owner authentication required.")
