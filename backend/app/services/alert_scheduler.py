"""
MailMind v2 — Alert Scheduler (CMT-06, CMT-07)
T-24h proactive alerts and overdue chase draft queuing.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


class AlertScheduler:
    """
    CMT-06: Fire T-24h proactive alert before each commitment deadline.
    CMT-07: Detect overdue unresolved commitments and queue chase drafts.
    """

    def __init__(self, draft_service: Any, alert_queue: list | None = None) -> None:
        self.draft_service = draft_service
        self.alert_queue: list[dict] = alert_queue if alert_queue is not None else []
        self._timers: list[threading.Timer] = []
        self._check_interval = 3600  # 1 hour overdue check
        self._overdue_thread: threading.Thread | None = None
        self._running = False

    def schedule_commitment_alert(
        self,
        email_id: str,
        commitment_text: str,
        deadline: datetime | None,
        original_email_body: str,
    ) -> None:
        """CMT-06: Schedule a T-24h alert for a commitment."""
        if not deadline:
            return

        deadline = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        alert_time = deadline - timedelta(hours=24)
        delay = (alert_time - now).total_seconds()

        if delay <= 0:
            logger.info(f"CMT-06: deadline already within 24h for {email_id}, firing now")
            self._fire_alert(email_id, commitment_text, deadline, original_email_body)
            return

        logger.info(f"CMT-06: scheduling T-24h alert for {email_id} in {delay:.0f}s")
        t = threading.Timer(delay, self._fire_alert, args=(
            email_id, commitment_text, deadline, original_email_body
        ))
        t.daemon = True
        t.start()
        self._timers.append(t)

    def _fire_alert(
        self,
        email_id: str,
        commitment_text: str,
        deadline: datetime,
        original_email_body: str,
    ) -> None:
        """Generate and queue a follow-up draft alert."""
        try:
            draft_text, _ = self.draft_service.generate_draft(
                email_text=(
                    f"Follow-up reminder: '{commitment_text}' is due in 24 hours "
                    f"({deadline.strftime('%Y-%m-%d %H:%M UTC')}).\n\n"
                    f"Original context:\n{original_email_body[:500]}"
                ),
                style="standard",
            )
            alert = {
                "type": "t24h_alert",
                "email_id": email_id,
                "commitment": commitment_text,
                "deadline": deadline.isoformat(),
                "draft": draft_text,
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "resolved": False,
            }
            self.alert_queue.append(alert)
            logger.info(f"CMT-06: alert queued for {email_id}")
        except Exception as e:
            logger.error(f"CMT-06: alert generation failed for {email_id}: {e}")

    def start_overdue_checker(self, commitments_store: list[dict]) -> None:
        """CMT-07: Start background loop to detect overdue commitments."""
        self._running = True
        self._overdue_thread = threading.Thread(
            target=self._overdue_loop,
            args=(commitments_store,),
            daemon=True,
        )
        self._overdue_thread.start()
        logger.info("CMT-07: overdue checker started")

    def stop(self) -> None:
        self._running = False
        for t in self._timers:
            t.cancel()

    def _overdue_loop(self, commitments_store: list[dict]) -> None:
        """CMT-07: Every hour, check for unresolved overdue commitments."""
        import time
        while self._running:
            self._check_overdue(commitments_store)
            time.sleep(self._check_interval)

    def _check_overdue(self, commitments_store: list[dict]) -> None:
        now = datetime.now(tz=timezone.utc)
        for c in commitments_store:
            if c.get("resolved") or c.get("chase_queued"):
                continue
            dl_str = c.get("deadline")
            if not dl_str:
                continue
            try:
                dl = datetime.fromisoformat(dl_str.replace("Z", "+00:00"))
                if dl.tzinfo is None:
                    dl = dl.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if dl < now:
                self._queue_chase_draft(c)
                c["chase_queued"] = True

    def _queue_chase_draft(self, commitment: dict) -> None:
        """CMT-07: Auto-queue a polite chase draft for an overdue commitment."""
        try:
            draft_text, _ = self.draft_service.generate_draft(
                email_text=(
                    f"The following commitment is now overdue:\n"
                    f"'{commitment.get('commitment', 'Unknown task')}'\n"
                    f"Deadline was: {commitment.get('deadline', 'unknown')}.\n"
                    f"Please send a polite follow-up to check on the status."
                ),
                style="standard",
            )
            chase = {
                "type": "chase_draft",
                "email_id": commitment.get("email_id", ""),
                "commitment": commitment.get("commitment", ""),
                "deadline": commitment.get("deadline", ""),
                "draft": draft_text,
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "resolved": False,
            }
            self.alert_queue.append(chase)
            logger.info(f"CMT-07: chase draft queued for {commitment.get('email_id')}")
        except Exception as e:
            logger.error(f"CMT-07: chase draft failed: {e}")


# Global alert queue accessible from routes
alert_queue: list[dict] = []