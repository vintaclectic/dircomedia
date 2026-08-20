"""
Credential vault access layer (YH9AE4D).

Every read and write of platform_credentials goes through here. Callers never
touch ciphertext and never see a raw ORM row with an encrypted column they might
accidentally log. Two rules this module enforces on everybody's behalf:

  1. Encrypt on the way in, decrypt on the way out — no exceptions, no "just
     this once" plaintext path.
  2. A token is only ever returned by get_access_token(), which is the one
     function anyone should have to audit.
"""
from __future__ import annotations

import secrets
import time
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt, decrypt, CredentialCryptoError
from app.models.credential import PlatformCredential, OAuthState

STATE_TTL_SECONDS = 600  # 10 min: long enough to read a consent screen, short
                         # enough that a leaked state is useless by the time it
                         # reaches anyone.


# ── credentials ──────────────────────────────────────────────────────────────

async def upsert_credential(
    db: AsyncSession,
    *,
    platform: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[int] = None,
    account_id: str = "",
    account_name: Optional[str] = None,
    scopes: Optional[str] = None,
) -> PlatformCredential:
    """Store (or replace) the credential for a platform.

    Deliberately keyed on platform alone, not (platform, account_id): reconnecting
    the same platform with a DIFFERENT account should replace the connection, not
    quietly accumulate a second row that nothing posts from. Multi-account is a
    Path B feature with its own UI; until then one platform = one live account.
    """
    row = (await db.execute(
        select(PlatformCredential).where(PlatformCredential.platform == platform)
    )).scalar_one_or_none()

    now = int(time.time())
    if row is None:
        row = PlatformCredential(platform=platform, created_at=now)
        db.add(row)

    row.access_token = encrypt(access_token)
    # An empty refresh_token in a refresh RESPONSE means "keep the old one"
    # (Reddit does this). Only overwrite when we actually got something.
    if refresh_token:
        row.refresh_token = encrypt(refresh_token)
    row.expires_at = expires_at
    row.account_id = account_id or ""
    if account_name:
        row.account_name = account_name
    if scopes:
        row.scopes = scopes
    row.needs_reconnect = False
    row.last_error = None
    row.last_refreshed_at = now
    row.updated_at = now

    await db.commit()
    await db.refresh(row)
    return row


async def get_credential(db: AsyncSession, platform: str) -> Optional[PlatformCredential]:
    return (await db.execute(
        select(PlatformCredential).where(PlatformCredential.platform == platform)
    )).scalar_one_or_none()


async def list_credentials(db: AsyncSession) -> list[PlatformCredential]:
    return list((await db.execute(select(PlatformCredential))).scalars().all())


async def get_access_token(db: AsyncSession, platform: str) -> Optional[str]:
    """The one function that hands out a usable token. Never log its return.

    A row flagged `needs_reconnect` is NOT a usable token and must never be
    handed out (SFM8BJE, 2026-08-20). The vault takes precedence over the .env
    key set, so returning a token we already know is broken actively SHADOWS
    working credentials: DirCoMedia's X connection stored an OAuth 2.0
    *app-only* token, which X rejects on user-context endpoints with
    "403 Unsupported Authentication". That row was already marked
    needs_reconnect with the 403 recorded — and the poster kept using it
    anyway, so all 9 attempted posts failed while the perfectly valid OAuth
    1.0a keys in .env sat unused. Returning None here makes the caller fall
    back to .env, which is the whole point of the fallback existing.
    """
    row = await get_credential(db, platform)
    if not row or row.needs_reconnect:
        return None
    try:
        return decrypt(row.access_token)
    except CredentialCryptoError:
        return None


async def get_refresh_token(db: AsyncSession, platform: str) -> Optional[str]:
    row = await get_credential(db, platform)
    if not row or not row.refresh_token:
        return None
    try:
        return decrypt(row.refresh_token)
    except CredentialCryptoError:
        return None


async def mark_needs_reconnect(db: AsyncSession, platform: str, error: str) -> None:
    """Flag a connection as broken beyond self-repair. `error` is stored for the
    dashboard, so it must never contain a token — callers pass API error text,
    never request bodies."""
    row = await get_credential(db, platform)
    if not row:
        return
    row.needs_reconnect = True
    row.last_error = (error or "")[:500]
    row.updated_at = int(time.time())
    await db.commit()


async def delete_credential(db: AsyncSession, platform: str) -> bool:
    row = await get_credential(db, platform)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True


# ── CSRF state ───────────────────────────────────────────────────────────────

async def issue_state(
    db: AsyncSession, platform: str, redirect_uri: str, code_verifier: Optional[str] = None
) -> str:
    """Mint a single-use state token bound to this platform + redirect_uri."""
    now = int(time.time())
    # Opportunistic sweep — expired states are dead weight and a replay surface.
    await db.execute(delete(OAuthState).where(OAuthState.expires_at < now))

    state = secrets.token_urlsafe(32)
    db.add(OAuthState(
        state=state,
        platform=platform,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        created_at=now,
        expires_at=now + STATE_TTL_SECONDS,
    ))
    await db.commit()
    return state


async def consume_state(db: AsyncSession, state: str, platform: str) -> OAuthState:
    """Validate and burn a state token. Raises ValueError on anything suspicious.

    Four things must hold, and each maps to a real attack:
      - the state exists          → forged/absent state (classic CSRF)
      - it hasn't expired         → a stale link replayed later
      - it's for THIS platform    → a state issued for Reddit redeemed at X
      - it hasn't been used       → guaranteed by deleting it here, so a replay
                                    of a captured callback URL finds nothing
    """
    if not state:
        raise ValueError("Missing OAuth state parameter.")
    row = (await db.execute(
        select(OAuthState).where(OAuthState.state == state)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError("Invalid or already-used OAuth state.")

    # Burn it before any further validation so even a rejected attempt can't be
    # replayed while we decide.
    await db.execute(delete(OAuthState).where(OAuthState.state == state))
    await db.commit()

    if row.expires_at < int(time.time()):
        raise ValueError("OAuth state expired — start the connection again.")
    if row.platform != platform:
        raise ValueError("OAuth state does not match this platform.")
    return row
