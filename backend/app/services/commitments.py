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
        try:
            from openai import AzureOpenAI, OpenAI
            if settings.azure_openai_api_key and settings.azure_openai_endpoint:
                return AzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version="2024-02-01",
                    azure_endpoint=settings.azure_openai_endpoint
                ), settings.azure_openai_chat_deployment
            elif settings.openai_api_key:
                return OpenAI(api_key=settings.openai_api_key), "gpt-4o"
        except Exception:
            pass
        return None, ""

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

    def extract(self, masked_email_text: str, thread_summary: str) -> list[CommitmentItem]:
        """Extract candidate commitments from masked email text using GPT-4o with fallback."""
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
                            confidence=confidence
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
        """Create tracking artifacts for approved commitments."""
        task_urls: list[str] = []
        event_urls: list[str] = []
        for commitment in commitments:
            if commitment.approved:
                task_urls.append(self.graph_client.create_todo(email_id, commitment.commitment))
                event_urls.append(self.graph_client.create_calendar_event(email_id, commitment.commitment, commitment.deadline))
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
