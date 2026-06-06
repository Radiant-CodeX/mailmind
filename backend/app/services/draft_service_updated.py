"""
Drop-in replacement for backend/app/services/draft_service.py
Adds Tone DNA prefix (DNA-04) to every GPT-4o draft call.
"""
from __future__ import annotations

import logging
from typing import Any

from openai import AzureOpenAI, OpenAI

from app.config.settings import settings
from app.services.graph import GraphClient
from app.services.rag import RAGIndexFactory, RetrievalService, mask_pii
from app.services.tone_dna import ToneDNAService

logger = logging.getLogger(__name__)


class DraftService:
    def __init__(self) -> None:
        self._tone_dna = ToneDNAService(GraphClient())

    def _get_llm_client(self) -> tuple[OpenAI | AzureOpenAI | None, str]:
        if settings.use_mock_graph:
            return None, ""
        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            return AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-01",
                azure_endpoint=settings.azure_openai_endpoint,
            ), settings.azure_openai_chat_deployment
        elif settings.openai_api_key:
            return OpenAI(api_key=settings.openai_api_key), "gpt-4o"
        return None, ""

    def _get_clean_name(self, sender: str | None) -> str:
        if not sender:
            return "Sender"
        clean = sender.split("@")[0]
        clean = "".join(c for c in clean if c.isalpha() or c == " ")
        return clean.strip().title() or "Sender"

    def _generate_mock_draft(self, email_text: str, style: str, sender: str | None, subject: str | None) -> str:
        name = self._get_clean_name(sender)
        subj = subject or "your email"
        if style == "formal":
            return (
                f"Dear {name},\n\nThank you for your message regarding '{subj}'. "
                f"We have received your communication and are reviewing it thoroughly.\n\n"
                f"We will follow up with a detailed update shortly.\n\nSincerely,\nMailMind Co-Pilot Team"
            )
        elif style == "indepth":
            return (
                f"Hi {name},\n\nThank you for reaching out regarding '{subj}'.\n\n"
                f"1. Review & Context:\n   - Analysing requirements and dependencies.\n"
                f"2. Action Items:\n   - Validate requirements.\n   - Schedule alignment meeting.\n"
                f"3. Next Steps:\n   - Formal proposal within 24-48 hours.\n\nBest regards,\nMailMind Co-Pilot"
            )
        return (
            f"Hi {name},\n\nThank you for reaching out regarding '{subj}'.\n"
            f"I am looking into the details and will get back to you shortly.\n\nBest regards,\nMailMind Co-Pilot"
        )

    def generate_draft(
        self,
        email_text: str,
        style: str,
        sender: str | None = None,
        subject: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        style = style.lower()
        if style not in ("standard", "formal", "indepth"):
            style = "standard"

        index = RAGIndexFactory()()
        masked = mask_pii(email_text)
        try:
            precedents = RetrievalService(index).retrieve(masked)
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)
            precedents = []

        citations = [
            {
                "email_id": getattr(item, "email_id", ""),
                "subject": getattr(item, "subject", ""),
                "similarity": getattr(item, "similarity_score", 0.0),
            }
            for item in precedents
        ]

        client, model = self._get_llm_client()
        if not client:
            return self._generate_mock_draft(email_text, style, sender, subject), citations

        # DNA-04: inject Tone DNA prefix
        tone_prefix = self._tone_dna.get_system_prefix(context=email_text)

        rag_context = ""
        if precedents:
            rag_context = "Precedents from your sent history:\n" + "\n".join(
                f"- {getattr(p,'subject','')}: {getattr(p,'snippet',getattr(p,'masked_body',''))[:120]}"
                for p in precedents
            )

        style_map = {
            "formal": (
                "Write a highly professional formal email. Use 'Dear {name}', avoid contractions, "
                "sign off formally."
            ),
            "indepth": (
                "Write a comprehensive email with numbered action items, next steps, and invite collaboration."
            ),
            "standard": "Write a concise, helpful, friendly reply addressing the key points.",
        }

        system_prompt = (
            f"{tone_prefix}"
            f"Task: Generate a draft reply.\nStyle: {style_map[style]}\n\n{rag_context}\n\n"
            f"Output ONLY the draft email content."
        )
        user_content = (
            f"Subject: {subject or 'No Subject'}\nSender: {sender or 'unknown@example.com'}\n\n{email_text}"
        )

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.7,
            )
            return (response.choices[0].message.content or "").strip(), citations
        except Exception as e:
            logger.error("Draft generation failed: %s", e)
            return self._generate_mock_draft(email_text, style, sender, subject), citations