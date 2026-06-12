"""
AccountService — manages the lifecycle of OAuthAccount rows.

Responsibilities:
  - list_accounts(user)            → all connected accounts for a user
  - get_adapter(account)           → decrypted tokens → ProviderAdapter
  - set_default(user, account_id)  → flip is_default flag (one at a time)
  - disconnect(account)            → soft-delete by clearing tokens
  - update_metadata(account, ...)  → nickname, color, sync_enabled

Callers (routes) should never decrypt tokens directly — always go through
get_adapter() so the encryption layer remains internal to this service.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AccountService:

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def list_accounts(db, user_id: str) -> list[dict[str, Any]]:
        """Return serialisable metadata for all accounts owned by user_id."""
        from app.db.models import OAuthAccount
        accounts = (
            db.query(OAuthAccount)
            .filter_by(user_id=user_id)
            .order_by(OAuthAccount.created_at)
            .all()
        )
        return [AccountService._serialize(a) for a in accounts]

    @staticmethod
    def get_account(db, user_id: str, account_id: str):
        """Return OAuthAccount row or None (ownership-checked)."""
        from app.db.models import OAuthAccount
        return db.query(OAuthAccount).filter_by(id=account_id, user_id=user_id).first()

    # ── Adapter ───────────────────────────────────────────────────────────────

    @staticmethod
    def get_adapter(account):
        """
        Decrypt tokens from an OAuthAccount row and return a ProviderAdapter.

        Never returns None — raises ValueError if the account has no tokens and
        is not in an environment where mocks are enabled.
        """
        from app.services.provider_adapter import build_adapter
        from app.services.token_encryption import decrypt_token

        access_token = decrypt_token(account.access_token_encrypted or "")
        refresh_token = decrypt_token(account.refresh_token_encrypted or "")

        return build_adapter(
            provider=account.provider,
            access_token=access_token,
            refresh_token=refresh_token or None,
        )

    # ── Mutations ─────────────────────────────────────────────────────────────

    @staticmethod
    def set_default(db, user_id: str, account_id: str) -> None:
        """
        Make `account_id` the default for this user.
        Clears is_default on all other accounts first.
        """
        from app.db.models import OAuthAccount
        # Clear all
        db.query(OAuthAccount).filter_by(user_id=user_id).update({"is_default": False})
        # Set new default
        target = db.query(OAuthAccount).filter_by(id=account_id, user_id=user_id).first()
        if not target:
            raise ValueError(f"Account {account_id} not found for user {user_id}")
        target.is_default = True
        db.flush()

    @staticmethod
    def update_metadata(
        db,
        account,
        *,
        nickname: str | None = None,
        color: str | None = None,
        sync_enabled: bool | None = None,
    ) -> None:
        """Update display metadata (nickname, color, sync_enabled) on an account."""
        if nickname is not None:
            account.nickname = nickname.strip() or None
        if color is not None:
            account.color = color.strip() or None
        if sync_enabled is not None:
            account.sync_enabled = bool(sync_enabled)
        db.flush()

    @staticmethod
    def disconnect(db, account) -> None:
        """
        Soft-disconnect: wipe tokens but keep the row for audit history.
        Hard-delete is left as a future admin operation.
        """
        account.access_token_encrypted = None
        account.refresh_token_encrypted = None
        account.token_expires_at = None
        account.sync_enabled = False
        db.flush()

    # ── Serialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _serialize(account) -> dict[str, Any]:
        return {
            "id": account.id,
            "provider": account.provider,
            "email": account.account_email,
            "photo_url": account.picture_url,
            "nickname": account.nickname,
            "color": account.color,
            "is_default": account.is_default,
            "sync_enabled": account.sync_enabled,
            "has_token": bool(account.access_token_encrypted),
            "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
            "created_at": account.created_at.isoformat(),
        }
