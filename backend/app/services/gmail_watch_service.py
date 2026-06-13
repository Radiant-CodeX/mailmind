"""
GmailWatchService — Gmail push-notification lifecycle for inbox sync.
====================================================================

The Gmail analogue of SubscriptionService. Gmail doesn't push directly to an
arbitrary URL like Microsoft Graph; instead it publishes change notifications to
a Cloud Pub/Sub *topic*, and a Pub/Sub push subscription forwards them to our
``/webhooks/gmail`` endpoint.

Per-account, we call ``users.watch`` to start notifications (max ~7 days, so it
is renewed like a Graph subscription). Watch records are stored in the shared
``graph_subscription`` table with ``resource="gmail:watch:inbox"``.

Degrades gracefully: if no Pub/Sub topic is configured (``GMAIL_PUBSUB_TOPIC``),
watch is skipped and freshness comes from on-mount + scheduled delta sync — the
exact same fallback Graph uses without ``BACKEND_PUBLIC_URL``.

One-time Google Cloud setup the operator must do (out of band):
  1. Create a Pub/Sub topic, e.g. projects/PROJECT/topics/gmail-push
  2. Grant gmail-api-push@system.gserviceaccount.com the Pub/Sub Publisher role
     on that topic.
  3. Create a push subscription on the topic with the endpoint
     https://<backend>/webhooks/gmail?token=<GMAIL_PUBSUB_TOKEN>
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.config.settings import settings
from app.db.base import get_session, is_persistence_enabled
from app.db.models import GraphSubscription
from app.services.account_service import AccountService

logger = logging.getLogger(__name__)

_RESOURCE = "gmail:watch:inbox"


class GmailWatchService:

    @staticmethod
    def ensure_watch(account) -> dict | None:
        """
        Ensure an active Gmail push watch exists for this account's inbox.

        No-op (returns None) for non-Google accounts, when persistence is off,
        or when no Pub/Sub topic is configured.
        """
        if account.provider != "google" or not is_persistence_enabled():
            return None
        topic = settings.gmail_pubsub_topic
        if not topic:
            logger.info("[gwatch] GMAIL_PUBSUB_TOPIC unset — skipping watch for %s", account.id)
            return None

        with get_session() as session:
            if session is None:
                return None
            existing = (
                session.query(GraphSubscription)
                .filter_by(account_id=account.id, resource=_RESOURCE)
                .first()
            )
            # Gmail watch lasts ~7 days; renew with a comfortable margin.
            if existing and existing.expires_at > datetime.now(tz=timezone.utc) + timedelta(hours=24):
                return {"id": existing.id, "status": "active"}

        try:
            adapter = AccountService.get_adapter(account)
            result = adapter.watch_inbox(topic)
        except Exception as e:
            logger.warning("[gwatch] watch failed for %s: %s", account.id, e)
            return None

        expires = _parse_watch_expiry(result.get("expiration"))

        with get_session() as session:
            if session is None:
                return None
            existing = (
                session.query(GraphSubscription)
                .filter_by(account_id=account.id, resource=_RESOURCE)
                .first()
            )
            if existing:
                existing.provider_sub_id = topic
                existing.client_state = settings.gmail_pubsub_token or "none"
                existing.expires_at = expires
            else:
                session.add(GraphSubscription(
                    account_id=account.id,
                    provider_sub_id=topic,
                    resource=_RESOURCE,
                    client_state=settings.gmail_pubsub_token or "none",
                    expires_at=expires,
                ))
            session.commit()
        logger.info("[gwatch] watch ensured for %s (expires %s)", account.id, expires)
        return {"id": topic, "status": "created", "history_id": result.get("historyId")}

    @staticmethod
    def renew_due(within_hours: int = 24) -> int:
        """Renew Gmail watches expiring soon. Returns count renewed.

        Re-calling users.watch is idempotent and simply extends the window, so
        renewal is just ensure_watch again.
        """
        if not is_persistence_enabled():
            return 0
        from app.db.models import OAuthAccount

        cutoff = datetime.now(tz=timezone.utc) + timedelta(hours=within_hours)
        renewed = 0
        with get_session() as session:
            if session is None:
                return 0
            due = (
                session.query(GraphSubscription)
                .filter(GraphSubscription.resource == _RESOURCE,
                        GraphSubscription.expires_at < cutoff)
                .all()
            )
            accounts = [session.get(OAuthAccount, s.account_id) for s in due]

        for account in accounts:
            if account is None:
                continue
            if GmailWatchService.ensure_watch(account):
                renewed += 1
        return renewed

    @staticmethod
    def resolve_account_id(email_address: str) -> str | None:
        """Map a Gmail push 'emailAddress' to our account_id (scoped to google)."""
        if not is_persistence_enabled() or not email_address:
            return None
        from app.db.models import OAuthAccount

        with get_session() as session:
            if session is None:
                return None
            account = (
                session.query(OAuthAccount)
                .filter_by(provider="google", account_email=email_address)
                .first()
            )
            return account.id if account else None


def _parse_watch_expiry(value) -> datetime:
    """Gmail returns 'expiration' as a string of epoch milliseconds."""
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc) + timedelta(days=7)
