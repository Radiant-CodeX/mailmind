from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Optional

from app.config.settings import settings
from app.models.schemas import CommitmentItem
from app.services import campus, llm_provider
from app.services.calendar import CalendarConflictService
from app.services.rag import EmbeddingProvider, RAGIndexFactory, mask_pii

logger = logging.getLogger(__name__)


class CommitmentService:
    """Service for extracting, confirming, and indexing email commitments."""

    def __init__(self, mail_client: Any) -> None:
        # Gmail adapter/client: creates Google Tasks + Calendar events on confirm.
        self.mail_client = mail_client
        self.conflict_service = CalendarConflictService(mail_client)
        self.examples = [
            {
                "text": "Infosys campus drive: eligible students must register on the placement portal "
                        "by 03/10/2026 5 PM. The online assessment is on 06/10/2026 at 9:30 AM in the "
                        "Tech Park lab.",
                "commitments": [
                    {"commitment": "Register for the Infosys drive on the placement portal",
                     "deadline": "2026-10-03T17:00:00+05:30", "confidence": 0.97},
                    {"commitment": "Attend the Infosys online assessment at the Tech Park lab",
                     "deadline": "2026-10-06T09:30:00+05:30", "confidence": 0.95},
                ],
            },
            {
                "text": "Please submit your DBMS record notebook by Friday and pay the lab fee at the "
                        "accounts section.",
                "commitments": [
                    {"commitment": "Submit the DBMS record notebook", "deadline": None, "confidence": 0.93},
                    {"commitment": "Pay the lab fee at the accounts section", "deadline": None, "confidence": 0.88},
                ],
            },
            {
                "text": "FYI: the results of the coding contest are now on the club website. No action needed.",
                "commitments": [],
            },
        ]

    def _fallback_extract(self, masked_email_text: str) -> list[CommitmentItem]:
        """Extract candidate commitments using a local rule-based regex fallback."""
        commitments: list[CommitmentItem] = []
        lines = re.split(r"[\.\n]", masked_email_text)
        for idx, line in enumerate(lines):
            text = line.strip()
            if not text:
                continue
            if re.search(r"\b(please|need to|must|review|approve|schedule|confirm|register|submit|"
                         r"pay|download|attend|report|upload|apply)\b", text, re.I):
                deadline = self._find_deadline(text)
                confidence = 0.85 if re.search(r"\b(please|need to|must|review|approve|schedule|"
                                               r"register|submit|pay|attend)\b", text, re.I) else 0.5
                commitments.append(
                    CommitmentItem(
                        id=str(uuid.uuid4()),
                        commitment=text,
                        deadline=deadline,
                        confidence=max(0.0, min(1.0, confidence)),
                    )
                )
        return commitments

    def extract(self, masked_email_text: str, thread_summary: str, email_id: str | None = None) -> list[CommitmentItem]:
        """Extract candidate commitments from masked email text with the caller's model, with fallback."""
        import hashlib

        from app.services.cache import commitments_cache

        # Determine cache key
        if email_id:
            key = f"id:{email_id}"
        else:
            key = f"hash:{hashlib.sha256(masked_email_text.strip().lower().encode('utf-8')).hexdigest()}"

        cached = commitments_cache.get(key)
        if cached is not None:
            return cached

        # Calculate if not cached:
        result = self._extract_uncached(masked_email_text, thread_summary)
        commitments_cache.set(key, result)
        return result

    def _extract_uncached(self, masked_email_text: str, thread_summary: str) -> list[CommitmentItem]:
        if settings.use_mock_mail or not llm_provider.llm_available():
            return self._fallback_extract(masked_email_text)

        few_shot_str = "".join(
            f"Email: {ex['text']}\nCommitments: {json.dumps(ex['commitments'])}\n\n"
            for ex in self.examples
        )
        from app.services.user_settings import load_campus_profile

        profile = load_campus_profile(llm_provider.current_ai_user_id())
        system_prompt = (
            "You extract action items and deadlines from university emails.\n"
            f"{campus.role_context(profile)}\n\n"
            "List everything the READER must do: register, submit, pay, download, upload, attend "
            "(an exam, interview, viva, class, meeting — use its start time as the deadline), or reply.\n"
            "For each item return:\n"
            "- 'commitment': short imperative, including the venue if one is given.\n"
            "- 'deadline': ISO 8601 (YYYY-MM-DDTHH:MM:SS+05:30 when a time is known, else YYYY-MM-DD), "
            "or null. Numeric dates are Indian format DD/MM/YYYY; times are IST unless stated.\n"
            "- 'confidence': 0.0-1.0.\n\n"
            "Return ONLY JSON: an object with a 'commitments' list."
        )

        user_prompt = (
            f"Examples:\n{few_shot_str}Now extract commitments from this email:\n"
            f"Email: {masked_email_text[:3000]}\nThread summary: {thread_summary}\nCommitments:"
        )

        try:
            data = llm_provider.invoke_json(system_prompt, user_prompt, max_tokens=500)
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, list):
                        items = val
                        break
                else:
                    items = [data]

            results = []
            for item in items:
                commitment_text = item.get("commitment", "")
                if not commitment_text:
                    continue
                
                raw_deadline = item.get("deadline")
                deadline_dt = None
                if raw_deadline:
                    try:
                        # Handle Z and ISO formats
                        clean_deadline = str(raw_deadline).replace("Z", "+00:00")
                        deadline_dt = datetime.fromisoformat(clean_deadline)
                    except Exception:
                        deadline_dt = self._find_deadline(str(raw_deadline))
                
                confidence = float(item.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))

                # Confidence gate of >= 0.5
                if confidence >= 0.5:
                    results.append(
                        CommitmentItem(
                            id=str(uuid.uuid4()),
                            commitment=commitment_text,
                            deadline=deadline_dt,
                            confidence=confidence,
                            confirmed=False
                        )
                    )
            return results

        except Exception:
            # Reverts to fallback on any parsing/client error
            return self._fallback_extract(masked_email_text)

    def _find_deadline(self, text: str) -> Optional[datetime]:
        """Parse a simple deadline expression from a line of text."""
        match = re.search(r"(due|by|before|on)\s+([A-Za-z0-9\-:, ]+)", text, re.I)
        if not match:
            return None
        raw = match.group(2).strip()
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def confirm(self, email_id: str, commitments: list[CommitmentItem]) -> dict[str, Any]:
        """Create tracking artifacts for approved commitments, reusing existing cached events/tasks."""
        from app.services.cache import commitments_cache
        key = f"id:{email_id}"
        cached_list = commitments_cache.get(key)

        task_urls: list[str] = []
        event_urls: list[str] = []

        for commitment in commitments:
            if commitment.approved:
                # Check if it was already confirmed in our cache
                already_done = False
                if cached_list:
                    matched = next((item for item in cached_list if item.id == commitment.id), None)
                    if matched and getattr(matched, "confirmed", False):
                        task_urls.append(matched.task_url or "")
                        event_urls.append(matched.event_url or "")
                        already_done = True

                if not already_done:
                    t_url = self.mail_client.create_todo(email_id, commitment.commitment)
                    e_url = self.mail_client.create_calendar_event(email_id, commitment.commitment, commitment.deadline)
                    task_urls.append(t_url)
                    event_urls.append(e_url)

                    # Update the item in our cached list
                    if cached_list:
                        matched = next((item for item in cached_list if item.id == commitment.id), None)
                        if matched:
                            matched.approved = True
                            matched.confirmed = True
                            matched.task_url = t_url
                            matched.event_url = e_url

                    # CMT-06: Schedule T-24h proactive alert
                    from app.services.alert_scheduler import AlertScheduler, alert_queue
                    from app.services.draft_service import DraftService
                    scheduler = AlertScheduler(DraftService(), alert_queue)
                    if commitment.approved and commitment.deadline:
                        dl = commitment.deadline
                        if isinstance(dl, str):
                            try:
                                dl = datetime.fromisoformat(dl.replace("Z", "+00:00"))
                            except ValueError:
                                dl = None
                        if dl:
                            scheduler.schedule_commitment_alert(
                                email_id=email_id,
                                commitment_text=commitment.commitment,
                                deadline=dl,
                                original_email_body=commitment.commitment,
                            )

        # Save updated list back to cache
        if cached_list:
            commitments_cache.set(key, cached_list)

        self._audit(email_id, commitments)
        self._schedule_reindex(email_id)
        return {"success": True, "task_urls": task_urls, "event_urls": event_urls}

    def filter_by_confidence(self, commitments: list[CommitmentItem], threshold: float = settings.commitment_confidence_threshold) -> list[CommitmentItem]:
        """Return only commitments above the configured confidence threshold."""
        return [commitment for commitment in commitments if commitment.confidence >= threshold]

    def _schedule_reindex(self, email_id: str) -> None:
        """Start a background thread to index the sent email after commitments are confirmed."""
        thread = threading.Thread(target=self._incremental_reindex, args=(email_id,), daemon=True)
        thread.start()

    def _incremental_reindex(self, email_id: str) -> None:
        """Fetch sent email content and upsert a new RAG index entry."""
        email = self.mail_client.fetch_sent_email(email_id)
        if not email:
            return
        masked_body = mask_pii(str(email.get("body", "")))
        embedding = EmbeddingProvider().embed(masked_body)
        index = RAGIndexFactory()()
        index.upsert(
            {
                "email_id": email_id,
                "subject": str(email.get("subject", "Sent Email")),
                "masked_body": masked_body,
                "embedding": embedding,
            }
        )
        index.trim(settings.index_max_size)

    def _audit(self, email_id: str, commitments: list) -> None:
        """API-09: Persist audit log to data/audit.log"""
        import json as _json
        from datetime import datetime, timezone
        from pathlib import Path

        log_path = Path("data/audit.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        for c in commitments:
            entry = {
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "email_id": email_id,
                "commitment_id": c.id,
                "action": "approved" if c.approved else "skipped",
                "commitment": c.commitment,
                "confidence": c.confidence,
            }
            with open(log_path, "a") as f:
                f.write(_json.dumps(entry) + "\n")
