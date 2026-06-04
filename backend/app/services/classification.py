from __future__ import annotations
import json
import logging
import re
from typing import Literal
from openai import OpenAI, AzureOpenAI

from app.models.schemas import ClassificationResult
from app.config.settings import settings

logger = logging.getLogger(__name__)


class ClassificationService:
    """Classifier for email priority and category using GPT-4o with deterministic rule fallback."""

    def __init__(self) -> None:
        self.examples = [
            {
                "text": "URGENT: Database outage in production. Clients are seeing 500 errors. Please investigate ASAP.",
                "category": "support",
                "priority": "CRITICAL",
                "confidence": 0.99
            },
            {
                "text": "Hi team, attached is the revised sales contract for Acme Corp. Please review by Friday.",
                "category": "sales",
                "priority": "HIGH",
                "confidence": 0.90
            },
            {
                "text": "Hi, just a reminder that our weekly sync is tomorrow at 10 AM. Let me know if you can't make it.",
                "category": "internal",
                "priority": "MEDIUM",
                "confidence": 0.80
            },
            {
                "text": "FYI: Here is the monthly newsletter with details of the upcoming team picnic.",
                "category": "internal",
                "priority": "LOW",
                "confidence": 0.95
            },
            {
                "text": "Customer ticket #10243: Login page keeps spinning on Chrome browser. Needs support assistance.",
                "category": "support",
                "priority": "HIGH",
                "confidence": 0.85
            }
        ]

    def _get_llm_client(self) -> tuple[OpenAI | AzureOpenAI | None, str]:
        """Return the appropriate OpenAI or AzureOpenAI client, or None if not configured."""
        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            return AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-01",
                azure_endpoint=settings.azure_openai_endpoint
            ), settings.azure_openai_chat_deployment
        elif settings.openai_api_key:
            return OpenAI(api_key=settings.openai_api_key), "gpt-4o"
        return None, ""

    def _fallback_classify(self, masked_text: str) -> ClassificationResult:
        """Deterministic rule-based fallback classification."""
        lower = masked_text.lower()

        if "urgent" in lower or "asap" in lower or "important" in lower or "outage" in lower:
            priority = "CRITICAL"
        elif "please review" in lower or "action required" in lower or "approve" in lower or "contract" in lower:
            priority = "HIGH"
        elif "update" in lower or "report" in lower or "follow up" in lower or "meeting" in lower:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        if "sales" in lower or "deal" in lower or "proposal" in lower or "contract" in lower:
            category = "sales"
        elif "support" in lower or "customer" in lower or "ticket" in lower or "help" in lower:
            category = "support"
        else:
            category = "internal"

        confidence = 0.9 if priority in ("CRITICAL", "HIGH") else 0.75 if priority == "MEDIUM" else 0.4
        confidence = max(0.0, min(1.0, confidence))

        return ClassificationResult(priority=priority, category=category, confidence=confidence)

    def classify(self, masked_text: str) -> ClassificationResult:
        """Classify the masked email text using GPT-4o with a fallback to rule-based rules."""
        client, model = self._get_llm_client()
        if not client:
            logger.info("LLM client not configured. Using rule-based fallback classification.")
            return self._fallback_classify(masked_text)

        # Build few-shot prompt
        few_shot_str = "\n\n".join([
            f"Email: {ex['text']}\nResult: {{\"priority\": \"{ex['priority']}\", \"category\": \"{ex['category']}\", \"confidence\": {ex['confidence']}}}"
            for ex in self.examples
        ])

        system_prompt = (
            "You are an AI assistant designed to classify incoming emails for an enterprise.\n"
            "You must classify the email text into one of the following priority levels:\n"
            "- CRITICAL\n- HIGH\n- MEDIUM\n- LOW\n\n"
            "And one of the following categories:\n"
            "- sales\n- support\n- internal\n\n"
            "Provide a confidence score between 0.0 and 1.0 representing your classification certainty.\n"
            "You MUST return the output as a valid JSON object with the exact keys: 'priority', 'category', 'confidence'.\n"
            "Do not include any Markdown blocks, backticks, or extra text. Only return the JSON object."
        )

        user_prompt = f"Here are some examples:\n{few_shot_str}\n\nNow, classify the following email:\nEmail: {masked_text}\nResult:"

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
            
            priority = str(data.get("priority", "MEDIUM")).upper()
            if priority not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                priority = "MEDIUM"

            category = str(data.get("category", "internal")).lower()
            if category not in ("sales", "support", "internal"):
                category = "internal"

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            return ClassificationResult(priority=priority, category=category, confidence=confidence)

        except Exception as e:
            logger.warning(f"GPT-4o classification failed: {e}. Falling back to rule-based classification.")
            return self._fallback_classify(masked_text)

