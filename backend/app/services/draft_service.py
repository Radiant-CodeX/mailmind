"""
MailMind v2 — Tone DNA-enabled Draft Service (DNA-04)
Generates email response drafts using OpenAI/Azure OpenAI with style presets and Tone DNA profiling.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config.settings import settings
from app.services.rag import RAGIndexFactory, RetrievalService, mask_pii
from app.services.tone_dna import ToneDNAService

logger = logging.getLogger(__name__)


class DraftService:
    def __init__(self) -> None:
        pass  # ToneDNA is built on demand so it uses the correct user + provider

    def _get_llm_client(self):
        """
        Return a LangChain AzureChatOpenAI client so that every draft generation
        call is automatically traced in LangSmith (same client used by the agent nodes).
        Returns None when credentials are missing — caller handles gracefully.
        """
        if settings.azure_openai_api_key and settings.azure_openai_base_endpoint:
            try:
                from langchain_openai import AzureChatOpenAI
                return AzureChatOpenAI(
                    azure_endpoint=settings.azure_openai_base_endpoint,
                    azure_deployment=settings.azure_openai_chat_deployment,
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    temperature=0.7,
                )
            except Exception as e:
                logger.warning("LangChain AzureChatOpenAI init failed: %s", e)
        return None

    def _get_clean_name(self, sender: str | None) -> str:
        if not sender:
            return "Sender"
        clean = sender.split("@")[0]
        clean = "".join(c for c in clean if c.isalpha() or c == " ")
        return clean.strip().title() or "Sender"

    def _get_user_display_name(self, email: str | None) -> str:
        """Derive a first-name display from an email address (e.g. tarun.sharma@co.com → Tarun)."""
        if not email:
            return ""
        local = email.split("@")[0]          # tarun.sharma  or  tarun_sharma
        # Replace dots/underscores/hyphens with spaces, take the first word, title-case it.
        first = local.replace(".", " ").replace("_", " ").replace("-", " ").split()[0]
        return first.strip().title()

    def generate_draft(
        self,
        email_text: str,
        style: str,
        sender: str | None = None,
        subject: str | None = None,
        current_user_email: str | None = None,
        account_id: str | None = None,
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

        client = self._get_llm_client()
        if not client:
            raise RuntimeError("Azure OpenAI credentials not configured. Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.")

        # Derive the sender's display name and the current user's display name.
        sender_name = self._get_clean_name(sender) if sender else "there"
        user_name = self._get_user_display_name(current_user_email)

        # DNA-04: inject Tone DNA prefix — keyed by account_id for per-account isolation
        tone_prefix = ""
        if account_id:
            try:
                from app.services.mail_provider import get_mail_client
                tone_dna = ToneDNAService(get_mail_client(), account_id)
                tone_prefix = tone_dna.get_system_prefix(context=email_text)
            except Exception as _e:
                logger.debug("[DraftService] Tone DNA unavailable: %s", _e)

        rag_context = ""
        if precedents:
            rag_context = "Precedents from your sent history:\n" + "\n".join(
                f"- {getattr(p,'subject','')}: {getattr(p,'snippet',getattr(p,'masked_body',''))[:120]}"
                for p in precedents
            )

        style_map = {
            "formal": (
                f"Write a highly professional formal email. "
                f"Open with 'Dear {sender_name},' and sign off with 'Sincerely,' followed by your name."
            ),
            "indepth": (
                f"Write a comprehensive email addressing {sender_name} with numbered action items, "
                f"next steps, and an invitation to collaborate. Sign off with 'Best regards,' and your name."
            ),
            "standard": (
                f"Write a concise, helpful, friendly reply to {sender_name} addressing the key points. "
                f"Sign off with 'Best regards,' and your name."
            ),
        }

        # Tell the LLM exactly who is writing this reply so the sign-off is personalised.
        identity_line = (
            f"You are {user_name} ({current_user_email}). "
            if user_name and current_user_email
            else ""
        )

        system_prompt = (
            f"{tone_prefix}"
            f"{identity_line}"
            f"Task: Generate a draft reply on behalf of yourself.\n"
            f"Style: {style_map[style]}\n\n"
            f"{rag_context}\n\n"
            f"IMPORTANT: Do NOT use placeholder names like 'John', 'Alice', '[Your Name]', or '[Name]'. "
            f"Use the actual sender name '{sender_name}' and sign off as '{user_name or 'MailMind User'}'. "
            f"Output ONLY the draft email content — no meta-commentary."
        )
        user_content = (
            f"Subject: {subject or 'No Subject'}\n"
            f"From: {sender or 'unknown@example.com'}\n"
            f"To: {current_user_email or 'me'}\n\n"
            f"{email_text}"
        )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            response = client.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            return (response.content or "").strip(), citations
        except Exception as e:
            logger.error("Draft generation failed: %s", e)
            raise

    def generate_compose(
        self,
        prompt: str,
        recipient: str | None = None,
        subject: str | None = None,
        current_user_email: str | None = None,
        account_id: str | None = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Compose a brand-new email (not a reply) from a natural-language instruction,
        written in the user's authentic voice (Tone DNA) and grounded in their sent
        history (RAG precedents).
        """
        index = RAGIndexFactory()()
        masked = mask_pii(prompt)
        try:
            precedents = RetrievalService(index).retrieve(masked)
        except Exception as e:
            logger.warning("RAG retrieval failed (compose): %s", e)
            precedents = []

        citations = [
            {
                "email_id": getattr(item, "email_id", ""),
                "subject": getattr(item, "subject", ""),
                "similarity": getattr(item, "similarity_score", 0.0),
            }
            for item in precedents
        ]

        client = self._get_llm_client()
        if not client:
            raise RuntimeError("Azure OpenAI credentials not configured. Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT.")

        recipient_name = self._get_clean_name(recipient) if recipient else "there"
        user_name = self._get_user_display_name(current_user_email)

        tone_prefix = ""
        if account_id:
            try:
                from app.services.mail_provider import get_mail_client
                tone_dna = ToneDNAService(get_mail_client(), account_id)
                tone_prefix = tone_dna.get_system_prefix(context=prompt)
            except Exception as _e:
                logger.debug("[DraftService] Tone DNA unavailable (compose): %s", _e)

        rag_context = ""
        if precedents:
            rag_context = "Precedents from your sent history (match your voice to these):\n" + "\n".join(
                f"- {getattr(p,'subject','')}: {getattr(p,'snippet',getattr(p,'masked_body',''))[:120]}"
                for p in precedents
            )

        identity_line = (
            f"You are {user_name} ({current_user_email}). "
            if user_name and current_user_email
            else ""
        )

        system_prompt = (
            f"{tone_prefix}"
            f"{identity_line}"
            f"Task: Compose a brand-new email (NOT a reply) based on the user's instruction below.\n"
            f"Write in your own authentic voice. Address it to {recipient_name}.\n\n"
            f"{rag_context}\n\n"
            f"IMPORTANT: Do NOT use placeholder names like 'John', '[Your Name]', or '[Name]'. "
            f"Sign off as '{user_name or 'MailMind User'}'. "
            f"Output ONLY the email body content — no subject line, no meta-commentary."
        )
        user_content = (
            f"Recipient: {recipient or 'unknown'}\n"
            f"Subject: {subject or '(none yet)'}\n\n"
            f"Instruction: {prompt}"
        )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            response = client.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            return (response.content or "").strip(), citations
        except Exception as e:
            logger.error("Compose generation failed: %s", e)
            raise
