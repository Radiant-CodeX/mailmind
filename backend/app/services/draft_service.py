from __future__ import annotations
import logging
from typing import Any, Iterable
from openai import OpenAI, AzureOpenAI

from app.config.settings import settings
from app.models.schemas import PrecedentItem
from app.services.rag import RetrievalService, RAGIndexFactory, mask_pii

logger = logging.getLogger(__name__)


class DraftService:
    """Service to generate email drafts in three styles: standard, formal, or indepth."""

    def _get_llm_client(self) -> tuple[OpenAI | AzureOpenAI | None, str]:
        """Return the appropriate OpenAI or AzureOpenAI client, or None if not configured."""
        if settings.use_mock_graph:
            return None, ""
        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            return AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-01",
                azure_endpoint=settings.azure_openai_endpoint
            ), settings.azure_openai_chat_deployment
        elif settings.openai_api_key:
            return OpenAI(api_key=settings.openai_api_key), "gpt-4o"
        return None, ""

    def _get_clean_name(self, sender: str | None) -> str:
        if not sender:
            return "Sender"
        clean = sender.split("@")[0]
        # remove punctuation/digits and capitalize
        clean = "".join([c for c in clean if c.isalpha() or c == " "])
        return clean.strip().title() or "Sender"

    def _generate_mock_draft(self, email_text: str, style: str, sender: str | None, subject: str | None) -> str:
        name = self._get_clean_name(sender)
        subj = subject or "your email"

        if style == "formal":
            return (
                f"Dear {name},\n\n"
                f"I hope this email finds you well.\n\n"
                f"Thank you for your message regarding '{subj}'. I wanted to confirm that we have received "
                f"your communication and it is currently being reviewed by our team. We are evaluating the "
                f"details to ensure we address all aspects of your inquiry thoroughly.\n\n"
                f"We appreciate your patience and will follow up with you with a detailed update shortly. Should you "
                f"have any additional context to share in the meantime, please feel free to send it.\n\n"
                f"Sincerely,\n"
                f"MailMind Co-Pilot Team"
            )
        elif style == "indepth":
            return (
                f"Hi {name},\n\n"
                f"Thank you for reaching out regarding '{subj}'. Below is an in-depth review "
                f"of the items discussed, along with proposed next steps and action items:\n\n"
                f"1. Detailed Review & Context:\n"
                f"   - We have noted the issues/requirements outlined in your email and are analyzing "
                f"     the operational dependencies to draft a viable solution.\n"
                f"2. Core Action Items:\n"
                f"   - Validate all requirements against existing integration parameters.\n"
                f"   - Coordinate a brief alignment review meeting to finalize deliverables.\n"
                f"3. Next Steps:\n"
                f"   - I am currently gathering the required statistics and documentation. I expect "
                f"     to have a formal proposal ready for your review within the next 24-48 business hours.\n\n"
                f"If you have any urgent changes or questions, please let me know.\n\n"
                f"Best regards,\n"
                f"MailMind Co-Pilot"
            )
        else:  # standard
            return (
                f"Hi {name},\n\n"
                f"Thank you for reaching out regarding '{subj}'.\n\n"
                f"I have received your email and am looking into the details. I will get back to you "
                f"shortly with a resolution.\n\n"
                f"Best regards,\n"
                f"MailMind Co-Pilot"
            )

    def generate_draft(
        self,
        email_text: str,
        style: str,
        sender: str | None = None,
        subject: str | None = None
    ) -> tuple[str, list[dict[str, Any]]]:
        """Generate draft response based on selected style: standard, formal, or indepth."""
        style = style.lower()
        if style not in ("standard", "formal", "indepth"):
            style = "standard"

        # 1. Retrieve precedents for RAG and citation context
        index = RAGIndexFactory()()
        masked = mask_pii(email_text)
        retrieval_service = RetrievalService(index)
        
        try:
            precedents = retrieval_service.retrieve(masked)
        except Exception as e:
            logger.warning("RAG retrieval failed during drafting: %s", e)
            precedents = []

        citations = [
            {
                "email_id": item.get("email_id") if isinstance(item, dict) else getattr(item, "email_id", ""),
                "subject": item.get("subject") if isinstance(item, dict) else getattr(item, "subject", ""),
                "similarity": item.get("similarity_score") if isinstance(item, dict) else getattr(item, "similarity_score", 0.0),
            }
            for item in precedents
        ]

        # 2. Get LLM client. If None or mock mode is active, generate fallback mock template
        client, model = self._get_llm_client()
        if not client:
            draft = self._generate_mock_draft(email_text, style, sender, subject)
            return draft, citations

        # 3. Formulate RAG context
        context_str = ""
        if precedents:
            context_str = "Precedents of previously sent responses:\n" + "\n".join([
                f"- Precedent subject: {item.subject if hasattr(item, 'subject') else item.get('subject', '')}\n"
                f"  Precedent body: {item.snippet if hasattr(item, 'snippet') else item.get('masked_body', '')}"
                for item in precedents
            ])

        # Define instructions based on style
        if style == "formal":
            style_instruction = (
                "Write a highly professional and formal business email response. Use formal salutations (e.g. Dear [Name], "
                "or Dear customer/partner if the name is not known), professional language, and a polite, formal sign-off. "
                "Do not use casual contractions (e.g. use 'do not' instead of 'don't')."
            )
        elif style == "indepth":
            style_instruction = (
                "Write an in-depth, comprehensive email response. Address all aspects of the received email, "
                "break down your points clearly, list concrete action items and next steps with bullet points "
                "or numbers, and invite further collaboration or questions."
            )
        else:  # standard
            style_instruction = (
                "Write a standard, helpful, and friendly email response. Be concise, direct, and address "
                "the key points in the received email briefly."
            )

        system_prompt = (
            f"You are MailMind Co-Pilot, an AI assistant built to help knowledge workers draft email responses.\n\n"
            f"Task: Generate a draft reply to the user's incoming email.\n"
            f"Style constraint: {style_instruction}\n\n"
            f"Context:\n"
            f"{context_str}\n\n"
            f"Rules:\n"
            f"- Use the precedents' tone and styling as a reference if available, but respect the style constraint.\n"
            f"- Output ONLY the draft email content. Do not include any meta comments, notes, or explanation blocks."
        )

        user_content = f"Incoming email subject: {subject or 'No Subject'}\nSender: {sender or 'unknown@example.com'}\n\nIncoming email text:\n{email_text}"

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.7,
            )
            draft = response.choices[0].message.content or ""
            return draft.strip(), citations
        except Exception as e:
            logger.error("Failed to generate AI draft response using LLM client: %s", e)
            # Fall back to high-quality mock response
            draft = self._generate_mock_draft(email_text, style, sender, subject)
            return draft, citations
