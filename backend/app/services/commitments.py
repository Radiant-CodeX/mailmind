from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime
from typing import Any, Optional

from app.config.settings import settings
from app.models.schemas import CommitmentItem
from app.services.calendar import CalendarConflictService
from app.services.graph import GraphClient
from app.services.rag import EmbeddingProvider, RAGIndexFactory, mask_pii


class CommitmentService:
    """Service for extracting, confirming, and indexing email commitments."""

    def __init__(self, graph_client: GraphClient) -> None:
        self.graph_client = graph_client
        self.conflict_service = CalendarConflictService(graph_client)
        self.examples = [
            {
                "text": "Hi Jane, please review the budget proposal by Monday next week.",
                "commitments": [
                    {
                        "commitment": "Review the budget proposal",
                        "deadline": "2026-06-08T09:00:00Z",
                        "confidence": 0.95
                    }
                ]
            },
            {
                "text": "Can you make sure to approve the timesheet before 5 PM today? Also, please upload the slide deck.",
                "commitments": [
                    {
                        "commitment": "Approve the timesheet",
                        "deadline": "2026-06-04T17:00:00Z",
                        "confidence": 0.99
                    },
                    {
                        "commitment": "Upload the slide deck",
                        "deadline": None,
                        "confidence": 0.90
                    }
                ]
            },
            {
                "text": "FYI: the client liked the prototype. No actions needed for now.",
                "commitments": []
            }
        ]

    def _get_llm_client(self) -> tuple[Any, str]:
        """Return the appropriate OpenAI or AzureOpenAI client, or None if not configured."""
        if settings.use_mock_graph:
            return None, ""
        try:
            from openai import AzureOpenAI, OpenAI
            if settings.azure_openai_api_key and settings.azure_openai_endpoint:
                return AzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=settings.azure_openai_endpoint
                ), settings.azure_openai_chat_deployment
            elif settings.openai_api_key:
                return OpenAI(api_key=settings.openai_api_key), "gpt-4o"
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        raise RuntimeError(
            "Real Azure OpenAI / OpenAI credentials are not configured in settings, "
            "but USE_MOCK_GRAPH is set to false (Real account mode)."
        )

    def _fallback_extract(self, masked_email_text: str) -> list[CommitmentItem]:
        """Extract candidate commitments using a local rule-based regex fallback."""
        commitments: list[CommitmentItem] = []
        lines = re.split(r"[\.\n]", masked_email_text)
        for idx, line in enumerate(lines):
            text = line.strip()
            if not text:
                continue
            if re.search(r"\b(please|need to|must|review|approve|schedule|confirm)\b", text, re.I):
                deadline = self._find_deadline(text)
                confidence = 0.85 if re.search(r"\b(please|need to|must|review|approve|schedule)\b", text, re.I) else 0.5
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
        """Extract candidate commitments from masked email text using GPT-4o with fallback."""
        from app.services.cache import commitments_cache
        import hashlib

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
        if settings.use_mock_graph:
            return self._fallback_extract(masked_email_text)

        client, model = self._get_llm_client()
        if not client:
            return self._fallback_extract(masked_email_text)

        # Format few-shot examples
        few_shot_str = ""
        for idx, ex in enumerate(self.examples):
            few_shot_str += f"Email: {ex['text']}\nCommitments: {json.dumps(ex['commitments'])}\n\n"

        system_prompt = (
            "You are an AI assistant designed to extract commitments, action items, and deadlines from email texts.\n"
            "Identify what the sender is requesting the recipient to do, or what the sender is committing to do.\n"
            "For each commitment, extract:\n"
            "- 'commitment': A concise description of the task or action item.\n"
            "- 'deadline': The deadline for the task, normalized to ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ) if mentioned, or null if not specified.\n"
            "- 'confidence': A confidence score between 0.0 and 1.0 representing your certainty of the extraction.\n\n"
            "You MUST return the output as a valid JSON array of objects or an object containing a list under a key like 'commitments'.\n"
            "Do not include any Markdown blocks, backticks, or extra text. Only return the JSON content."
        )

        user_prompt = f"Here are some examples:\n{few_shot_str}Now, extract commitments from this email:\nEmail: {masked_email_text}\nThread Summary: {thread_summary}\nCommitments:"

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                timeout=10.0
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")
            
            data = json.loads(content)
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
                    t_url = self.graph_client.create_todo(email_id, commitment.commitment)
                    e_url = self.graph_client.create_calendar_event(email_id, commitment.commitment, commitment.deadline)
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
        email = self.graph_client.fetch_sent_email(email_id)
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

    def _audit(self, email_id: str, commitments: list[CommitmentItem]) -> None:
        """Log commitment approval decisions for operational visibility."""
        for commitment in commitments:
            status = "approved" if commitment.approved else "skipped"
            print(f"[AUDIT] {email_id} {commitment.id} {status} {commitment.commitment}")
