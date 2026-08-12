"""
platform_credentials — the OAuth token vault (YH9AE4D, council build 2026-08-12).

One row per connected account. access_token/refresh_token columns hold Fernet
ciphertext, never plaintext (see app/core/crypto.py). expires_at is a UTC Unix
timestamp; NULL means the token does not expire (OAuth 1.0a, app passwords).

`needs_reconnect` is set by the refresh worker when a refresh attempt fails
permanently. It's the difference between "expired, I'll fix it myself in six
hours" and "expired, Vinta has to click Reconnect" — the dashboard shows the
second one in red and stops pretending it's fine.

UNIQUE(platform, account_id) leaves the door open for multi-account per platform
later (Path B) without a migration; today account_id is the platform's own user
id and there is exactly one row per platform.
"""
from sqlalchemy import String, Integer, Boolean, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformCredential(Base):
    __tablename__ = "platform_credentials"
    __table_args__ = (
        UniqueConstraint("platform", "account_id", name="uq_platform_account"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 'twitter' | 'reddit' | 'instagram' | 'tiktok' | 'pinterest'
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Platform-side user id. "" (not NULL) so the UNIQUE constraint actually
    # bites — SQLite treats every NULL as distinct, which would silently allow
    # duplicate rows per platform.
    account_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    # Human-readable handle for the dashboard ("@dircomedia"). Not a secret.
    account_name: Mapped[str] = mapped_column(String(128), nullable=True)

    access_token: Mapped[str] = mapped_column(Text, nullable=False)      # Fernet ciphertext
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)      # Fernet ciphertext
    scopes: Mapped[str] = mapped_column(Text, nullable=True)             # space-separated

    expires_at: Mapped[int] = mapped_column(Integer, nullable=True)      # unix seconds, UTC

    needs_reconnect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    last_refreshed_at: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[int] = mapped_column(
        Integer, server_default=func.strftime("%s", "now"), nullable=True
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, server_default=func.strftime("%s", "now"), nullable=True
    )


class OAuthState(Base):
    """Single-use CSRF state tokens for the authorize→callback round trip.

    Persisted rather than held in memory for two reasons that both bite in
    practice: (1) uvicorn --reload restarts mid-flow would invalidate every
    in-flight authorization, and (2) an in-memory dict is per-process, so the
    moment there's more than one worker the callback lands on a process that
    never issued the state. A row is the only thing both halves of the flow can
    agree on.

    Rows are consumed (deleted) on first use and swept when expired — a replayed
    state finds nothing and is rejected, which is exactly the property CSRF
    protection needs.
    """
    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    code_verifier: Mapped[str] = mapped_column(Text, nullable=True)   # PKCE (X, TikTok)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
