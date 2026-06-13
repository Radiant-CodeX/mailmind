"""
SyncService — keeps the server-side mailbox mirror in step with the provider.
==============================================================================

Two entry points:

  backfill(account)     — first-time full enumeration into mailbox_message,
                          captures the initial delta cursor.
  delta_sync(account)   — incremental: replay the stored cursor, apply changes.

Both are idempotent and safe to call repeatedly (upsert by email_id). Triage is
intentionally NOT run here — the mirror stores envelopes only; triage stays lazy
and is filled by the existing streaming path for rows with no enrichment yet.

These run in background threads (FastAPI BackgroundTasks / a scheduler), so they
read only already-loaded attributes off the passed-in OAuthAccount row.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db import mailbox_repo
from app.services.account_service import AccountService

logger = logging.getLogger(__name__)


class SyncService:

    @staticmethod
    def _apply_changes(account_id: str, folder: str, result: dict[str, Any]) -> tuple[int, int, int]:
        """Upsert envelopes + tombstone removals from a delta result."""
        upserts = result.get("upserts") or []
        removed = result.get("removed") or []
        new_count, updated = mailbox_repo.upsert_messages(account_id, folder, upserts)
        tombs = mailbox_repo.tombstone_messages(account_id, removed)
        return new_count, updated, tombs

    @classmethod
    def backfill(cls, account, folder: str = "inbox") -> dict[str, Any]:
        """
        Full first-time enumeration of a folder into the mirror.

        Returns a summary dict; never raises (errors are recorded on sync_state).
        """
        account_id = account.id
        mailbox_repo.set_sync_status(account_id, folder, "running")
        try:
            adapter = AccountService.get_adapter(account)
            result = adapter.list_inbox_delta(None, folder=folder)
            new_count, updated, tombs = cls._apply_changes(account_id, folder, result)
            total = mailbox_repo.recount(account_id, folder)
            mailbox_repo.set_sync_cursor(
                account_id, folder,
                delta_cursor=result.get("delta_cursor"),
                backfill_done=True,
                status="idle",
            )
            logger.info("[sync] backfill %s/%s: +%d new, %d updated, %d removed, total=%d",
                        account_id, folder, new_count, updated, tombs, total)
            # Provision a webhook so future changes arrive in near-real-time.
            # Microsoft → Graph subscription (no-op without BACKEND_PUBLIC_URL).
            # Google → Gmail Pub/Sub watch (no-op without GMAIL_PUBSUB_TOPIC).
            # Each ensure call self-gates on provider, so calling both is safe.
            try:
                from app.services.subscription_service import SubscriptionService
                SubscriptionService.ensure_subscription(account)
            except Exception as _e:
                logger.debug("[sync] subscription ensure skipped: %s", _e)
            try:
                from app.services.gmail_watch_service import GmailWatchService
                GmailWatchService.ensure_watch(account)
            except Exception as _e:
                logger.debug("[sync] gmail watch ensure skipped: %s", _e)
            return {"new": new_count, "updated": updated, "removed": tombs, "total": total,
                    "truncated": result.get("truncated", False)}
        except Exception as e:
            logger.exception("[sync] backfill failed for %s/%s", account_id, folder)
            mailbox_repo.set_sync_status(account_id, folder, "error", str(e))
            return {"error": str(e)}

    @classmethod
    def delta_sync(cls, account, folder: str = "inbox") -> dict[str, Any]:
        """
        Incremental sync. Falls back to backfill when there's no cursor yet.
        """
        account_id = account.id
        state = mailbox_repo.get_sync_state(account_id, folder)
        if not state or not state.get("backfill_done") or not state.get("delta_cursor"):
            return cls.backfill(account, folder)

        mailbox_repo.set_sync_status(account_id, folder, "running")
        try:
            adapter = AccountService.get_adapter(account)
            result = adapter.list_inbox_delta(state["delta_cursor"], folder=folder)
            new_count, updated, tombs = cls._apply_changes(account_id, folder, result)
            total = mailbox_repo.recount(account_id, folder)
            # Keep the old cursor if the provider didn't return a new one
            # (e.g. Gmail snapshot mode or a truncated walk).
            new_cursor = result.get("delta_cursor") or state["delta_cursor"]
            mailbox_repo.set_sync_cursor(
                account_id, folder,
                delta_cursor=new_cursor,
                backfill_done=True,
                status="idle",
            )
            if new_count or tombs:
                logger.info("[sync] delta %s/%s: +%d new, %d removed, total=%d",
                            account_id, folder, new_count, tombs, total)
            return {"new": new_count, "updated": updated, "removed": tombs, "total": total}
        except Exception as e:
            logger.warning("[sync] delta failed for %s/%s: %s — will retry", account_id, folder, e)
            mailbox_repo.set_sync_status(account_id, folder, "error", str(e))
            return {"error": str(e)}
