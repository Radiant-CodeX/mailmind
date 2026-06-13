"""
SubscriptionService — Microsoft Graph webhook lifecycle for inbox sync.
=======================================================================

Creates and renews Graph change-notification subscriptions so the mirror is
updated in near-real-time. Degrades gracefully: if no public backend URL is
configured (``BACKEND_PUBLIC_URL``), subscriptions are skipped and freshness is
maintained by on-mount + scheduled delta sync instead.

Only Microsoft accounts use this; Gmail relies on snapshot delta sync.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.config.settings import settings
from app.db.base import get_session, is_persistence_enabled
from app.db.models import GraphSubscription
from app.services.account_service import AccountService

logger = logging.getLogger(__name__)

_RESOURCE = "/me/mailFolders('inbox')/messages"


def _notification_url() -> str | None:
    base = (settings.backend_public_url or "").rstrip("/")
    return f"{base}/webhooks/graph" if base else None


class SubscriptionService:

    @staticmethod
    def ensure_subscription(account) -> dict | None:
        """
        Ensure an active Graph subscription exists for this account's inbox.

        No-op (returns None) for non-Microsoft accounts, when persistence is off,
        or when no public backend URL is configured.
        """
        if account.provider != "microsoft" or not is_persistence_enabled():
            return None
        notif_url = _notification_url()
        if not notif_url:
            logger.info("[sub] BACKEND_PUBLIC_URL unset — skipping webhook for %s", account.id)
            return None

        with get_session() as session:
            if session is None:
                return None
            existing = (
                session.query(GraphSubscription)
                .filter_by(account_id=account.id, resource=_RESOURCE)
                .first()
            )
            # Still valid for a while → nothing to do.
            if existing and existing.expires_at > datetime.now(tz=timezone.utc) + timedelta(hours=12):
                return {"id": existing.id, "status": "active"}

        client_state = secrets.token_urlsafe(24)
        try:
            adapter = AccountService.get_adapter(account)
            created = adapter.create_subscription(notif_url, client_state, resource=_RESOURCE)
        except Exception as e:
            logger.warning("[sub] create failed for %s: %s", account.id, e)
            return None

        provider_sub_id = created.get("id")
        expires = _parse_expiry(created.get("expirationDateTime"))
        if not provider_sub_id:
            return None

        with get_session() as session:
            if session is None:
                return None
            existing = (
                session.query(GraphSubscription)
                .filter_by(account_id=account.id, resource=_RESOURCE)
                .first()
            )
            if existing:
                existing.provider_sub_id = provider_sub_id
                existing.client_state = client_state
                existing.expires_at = expires
            else:
                session.add(GraphSubscription(
                    account_id=account.id,
                    provider_sub_id=provider_sub_id,
                    resource=_RESOURCE,
                    client_state=client_state,
                    expires_at=expires,
                ))
            session.commit()
        logger.info("[sub] subscription ensured for %s (expires %s)", account.id, expires)
        return {"id": provider_sub_id, "status": "created"}

    @staticmethod
    def renew_due(within_hours: int = 12) -> int:
        """Renew all subscriptions expiring soon. Returns count renewed."""
        if not is_persistence_enabled():
            return 0
        from app.db.models import OAuthAccount

        cutoff = datetime.now(tz=timezone.utc) + timedelta(hours=within_hours)
        renewed = 0
        with get_session() as session:
            if session is None:
                return 0
            due = session.query(GraphSubscription).filter(GraphSubscription.expires_at < cutoff).all()
            pairs = [(s, session.get(OAuthAccount, s.account_id)) for s in due]

            for sub, account in pairs:
                if account is None:
                    continue
                try:
                    adapter = AccountService.get_adapter(account)
                    result = adapter.renew_subscription(sub.provider_sub_id)
                    sub.expires_at = _parse_expiry(result.get("expirationDateTime"))
                    renewed += 1
                except Exception as e:
                    logger.warning("[sub] renew failed for %s (%s) — recreating: %s",
                                   account.id, sub.provider_sub_id, e)
                    # Recreate from scratch; also force a resync to cover the gap.
                    session.delete(sub)
                    session.commit()
                    SubscriptionService.ensure_subscription(account)
            session.commit()
        return renewed

    @staticmethod
    def resolve_account_id(provider_sub_id: str, client_state: str) -> str | None:
        """Verify a notification's subscription + clientState → return account_id."""
        if not is_persistence_enabled():
            return None
        with get_session() as session:
            if session is None:
                return None
            sub = (
                session.query(GraphSubscription)
                .filter_by(provider_sub_id=provider_sub_id)
                .first()
            )
            if sub is None or sub.client_state != client_state:
                return None
            return sub.account_id


def _parse_expiry(value) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc) + timedelta(days=2)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(tz=timezone.utc) + timedelta(days=2)
