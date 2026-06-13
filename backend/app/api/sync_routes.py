"""
Inbox-sync webhook + subscription endpoints.
============================================

  POST /webhooks/graph         Microsoft Graph change notifications (machine-to-machine)
  POST /api/subscriptions/ensure   Ensure a webhook subscription for the current account
  POST /api/subscriptions/renew     Renew subscriptions expiring soon (ops / cron)

The webhook is intentionally unauthenticated (Graph calls it directly), but every
notification is verified against the stored ``clientState`` secret before we act.
We never trust the notification payload's contents — it only tells us *which*
account changed; we re-fetch authoritative state via delta sync.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from app.api.deps import get_default_account
from app.config.settings import settings
from app.db.base import get_session
from app.services.gmail_watch_service import GmailWatchService
from app.services.subscription_service import SubscriptionService
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])


@router.post("/webhooks/graph")
async def graph_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """
    Microsoft Graph change-notification receiver.

    1. Validation handshake: Graph appends ?validationToken=... on subscription
       creation — echo it back as text/plain within a few seconds.
    2. Notifications: verify clientState, resolve the account, and enqueue a
       background delta sync. Always ack fast (202) so Graph doesn't retry.
    """
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        return Response(content=validation_token, media_type="text/plain", status_code=200)

    try:
        body = await request.json()
    except Exception:
        return Response(status_code=202)

    notifications = body.get("value") or []
    seen_accounts: set[str] = set()
    for note in notifications:
        sub_id = note.get("subscriptionId")
        client_state = note.get("clientState")
        if not sub_id or not client_state:
            continue
        account_id = SubscriptionService.resolve_account_id(sub_id, client_state)
        if not account_id or account_id in seen_accounts:
            continue
        seen_accounts.add(account_id)
        background_tasks.add_task(_sync_account, account_id)

    return Response(status_code=202)


@router.post("/webhooks/gmail")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """
    Gmail push-notification receiver (Cloud Pub/Sub push).

    Pub/Sub POSTs an envelope:
      { "message": { "data": base64(json{emailAddress, historyId}), ... },
        "subscription": "projects/.../subscriptions/..." }

    Security: the push subscription's endpoint URL carries ?token=<secret>; we
    reject any request whose token doesn't match GMAIL_PUBSUB_TOKEN. As with
    Graph, the payload is never trusted for content — it only tells us *which*
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
    """Background: load the account and run a delta sync (own DB session)."""
    from app.db.models import OAuthAccount

    with get_session() as session:
        if session is None:
            return
        account = session.get(OAuthAccount, account_id)
        if account is None:
            return
        SyncService.delta_sync(account, "inbox")


@router.post("/api/subscriptions/ensure")
def ensure_subscription(
    background_tasks: BackgroundTasks,
    account=Depends(get_default_account),
) -> dict:
    """Ensure a push subscription exists for the current default account.

    Each ensure call self-gates on provider, so queuing both is safe regardless
    of whether this account is Microsoft or Google.
    """
    background_tasks.add_task(SubscriptionService.ensure_subscription, account)
    background_tasks.add_task(GmailWatchService.ensure_watch, account)
    return {"queued": True, "provider": account.provider}


@router.post("/api/subscriptions/renew")
def renew_subscriptions() -> dict:
    """Renew expiring push subscriptions across both providers (cron/scheduler).

    Graph subscriptions expire in ~3 days; Gmail watches in ~7. One hourly cron
    covers both.
    """
    graph_renewed = SubscriptionService.renew_due()
    gmail_renewed = GmailWatchService.renew_due()
    return {"renewed": graph_renewed + gmail_renewed,
            "graph": graph_renewed, "gmail": gmail_renewed}
