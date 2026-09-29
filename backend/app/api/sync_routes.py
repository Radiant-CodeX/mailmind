"""
Inbox-sync webhook + subscription endpoints.
============================================

  POST /webhooks/gmail              Gmail Pub/Sub push notifications (machine-to-machine)
  POST /api/subscriptions/ensure   Ensure a Gmail watch for the current account
  POST /api/subscriptions/renew    Renew watches expiring soon (ops / cron)

The webhook is unauthenticated (Pub/Sub calls it directly) but verified with a
shared token. We never trust the notification payload's contents — it only
tells us *which* account changed; we re-fetch authoritative state via delta sync.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from app.api.deps import get_default_account
from app.config.settings import settings
from app.db.base import get_session
from app.services.gmail_watch_service import GmailWatchService
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """
    Gmail push-notification receiver (Cloud Pub/Sub push).

    Pub/Sub POSTs an envelope:
      { "message": { "data": base64(json{emailAddress, historyId}), ... },
        "subscription": "projects/.../subscriptions/..." }

    Security: the push subscription's endpoint URL carries ?token=<secret>; we
    reject any request whose token doesn't match GMAIL_PUBSUB_TOKEN. The
    payload is never trusted for content — it only tells us *which*
    account changed; we re-fetch authoritative state via delta sync. Always ack
    fast (204) so Pub/Sub doesn't redeliver.
    """
    expected = settings.gmail_pubsub_token
    if expected and request.query_params.get("token") != expected:
        # Wrong/absent token → pretend success so Pub/Sub stops retrying a caller
        # that will never be authorized, but do no work.
        return Response(status_code=204)

    try:
        envelope = await request.json()
    except Exception:
        return Response(status_code=204)

    message = (envelope or {}).get("message") or {}
    data_b64 = message.get("data")
    if not data_b64:
        return Response(status_code=204)

    import base64
    import json
    try:
        decoded = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    except Exception:
        return Response(status_code=204)

    email_address = decoded.get("emailAddress")
    account_id = GmailWatchService.resolve_account_id(email_address)
    if account_id:
        background_tasks.add_task(_sync_account, account_id)

    return Response(status_code=204)


def _sync_account(account_id: str) -> None:
    """Background: load the account and run a delta sync.

    The account row is loaded with a short-lived session that is released
    *before* the sync runs. delta_sync does network I/O (Gmail) and opens
    its own short sessions for each mirror write, so holding this connection
    across the whole sync would needlessly pin a pool slot for seconds.
    """
    from app.db.models import OAuthAccount

    with get_session() as session:
        if session is None:
            return
        account = session.get(OAuthAccount, account_id)
        if account is None:
            return
        session.expunge(account)  # detach: all columns are already loaded

    SyncService.delta_sync(account, "inbox")


@router.post("/api/subscriptions/ensure")
def ensure_subscription(
    background_tasks: BackgroundTasks,
    account=Depends(get_default_account),
) -> dict:
    """Ensure a Gmail push watch exists for the current default account."""
    background_tasks.add_task(GmailWatchService.ensure_watch, account)
    return {"queued": True, "provider": account.provider}


@router.post("/api/subscriptions/renew")
def renew_subscriptions() -> dict:
    """Renew expiring Gmail watches (~7-day lifetime). Run hourly from a cron."""
    gmail_renewed = GmailWatchService.renew_due()
    return {"renewed": gmail_renewed, "gmail": gmail_renewed}
