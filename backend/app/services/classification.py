from __future__ import annotations

import json
import logging

from openai import AzureOpenAI

from app.config.settings import settings
from app.models.schemas import ClassificationResult

logger = logging.getLogger(__name__)

# Groq fallback for when Azure OpenAI is not configured.
try:
    from langchain_groq import ChatGroq as _ChatGroq
    _GROQ_AVAILABLE = True
except ImportError:
    _ChatGroq = None
    _GROQ_AVAILABLE = False


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

    def _get_llm_client(self) -> tuple[AzureOpenAI | _ChatGroq | None, str]:
        """Return the appropriate LLM client: Azure OpenAI → Groq → None.

        Returns a tuple of (client, model_name). Groq returns the model name
        directly (e.g. "llama-3.3-70b-versatile"); Azure returns the deployment name.
        """
        if settings.use_mock_graph:
            return None, ""
        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            return AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-01",
                azure_endpoint=settings.azure_openai_endpoint
            ), settings.azure_openai_chat_deployment
        elif settings.groq_api_key and _GROQ_AVAILABLE and _ChatGroq is not None:
            return _ChatGroq(api_key=settings.groq_api_key, model="llama-3.3-70b-versatile"), "llama-3.3-70b-versatile"
        # No LLM credentials in live mode — return None so callers fall back to
        # the rule-based classifier instead of raising a 500.
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
        """Classify the masked email text using an LLM (Azure/Groq) with rule-based fallback."""
        if settings.use_mock_graph:
            logger.info("Mock mode active. Bypassing LLM and using rule-based fallback.")
            return self._fallback_classify(masked_text)

        client, model = self._get_llm_client()
        if not client:
            logger.info("LLM not configured. Using rule-based fallback.")
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
            # Azure OpenAI supports JSON mode; Groq does not — both are handled the same way
            # for OpenAI, response_format ensures valid JSON; for Groq, the prompt alone drives it.
            is_azure = isinstance(client, AzureOpenAI)
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "timeout": 10.0
            }
            if is_azure:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
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
            logger.warning("LLM classification failed: %s. Falling back to rule-based.", e)
            return self._fallback_classify(masked_text)

