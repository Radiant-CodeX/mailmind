from __future__ import annotations

import logging

from app.config.settings import settings
from app.models.schemas import ClassificationResult
from app.services import campus, llm_provider

logger = logging.getLogger(__name__)


class ClassificationService:
    """Campus email classifier (priority + category) with a deterministic rule fallback."""

    def __init__(self) -> None:
        self.examples = [
            {
                "text": "Subject: Hall ticket download — End Semester Exams. Hall tickets are available on "
                        "the student portal. Students with attendance below 75% will not be permitted to write "
                        "the exam. Download before 20/11.",
                "category": "exams",
                "priority": "CRITICAL",
                "confidence": 0.97,
            },
            {
                "text": "Subject: Zoho campus drive — registration closes tomorrow 5 PM. Eligible final-year "
                        "CSE/IT students must register on the placement portal. Late registrations will not be "
                        "entertained.",
                "category": "placement",
                "priority": "CRITICAL",
                "confidence": 0.95,
            },
            {
                "text": "Subject: Assignment 3 submission. Please submit your DBMS assignment on the LMS by "
                        "Friday. — Dr. Priya, Assistant Professor",
                "category": "academics",
                "priority": "HIGH",
                "confidence": 0.9,
            },
            {
                "text": "Subject: Semester fee reminder. The last date to pay the odd-semester tuition fee "
                        "without fine is 30th of this month.",
                "category": "fees",
                "priority": "HIGH",
                "confidence": 0.9,
            },
            {
                "text": "Subject: Coding Club — weekend hackathon! Join us this Saturday, snacks provided. "
                        "Register if interested.",
                "category": "events",
                "priority": "LOW",
                "confidence": 0.85,
            },
            {
                "text": "Subject: 40% off all courses this week only! Unsubscribe from these emails.",
                "category": "promotions",
                "priority": "LOW",
                "confidence": 0.97,
            },
        ]

    # ── Deterministic fallback ────────────────────────────────────────────────

    def _fallback_classify(self, masked_text: str, sender: str = "") -> ClassificationResult:
        """Rule-based classification using the shared campus vocabulary."""
        lower = masked_text.lower()
        category = campus.categorize(sender, "", masked_text)
        consequences = campus.consequence_hits(masked_text)

        if any(k in lower for k in ("urgent", "asap", "immediately", "outage")) or (
            len(consequences) >= 2 and category in campus.HIGH_STAKES_CATEGORIES
        ):
            priority = "CRITICAL"
        elif consequences or category in ("placement", "exams", "fees") or any(
            k in lower for k in ("please review", "action required", "approve", "submit", "register")
        ):
            priority = "HIGH"
        elif category in ("academics", "administrative") or any(
            k in lower for k in ("update", "report", "follow up", "meeting", "reminder")
        ):
            priority = "MEDIUM"
        else:
            priority = "LOW"

        if category == "promotions":
            priority = "LOW"

        confidence = 0.9 if priority in ("CRITICAL", "HIGH") else 0.75 if priority == "MEDIUM" else 0.6
        return ClassificationResult(priority=priority, category=category, confidence=confidence)

    # ── LLM path ──────────────────────────────────────────────────────────────

    def classify(self, masked_text: str, sender: str = "") -> ClassificationResult:
        """Classify masked email text with the caller's model, falling back to rules."""
        if settings.use_mock_mail or not llm_provider.llm_available():
            return self._fallback_classify(masked_text, sender)

        few_shot = "\n\n".join(
            f"Email: {ex['text']}\nResult: {{\"priority\": \"{ex['priority']}\", "
            f"\"category\": \"{ex['category']}\", \"confidence\": {ex['confidence']}}}"
            for ex in self.examples
        )
        from app.services.user_settings import load_campus_profile

        profile = load_campus_profile(llm_provider.current_ai_user_id())
        system_prompt = (
            "You classify emails in a university inbox.\n"
            f"{campus.role_context(profile)}\n\n"
            "Priority is one of CRITICAL, HIGH, MEDIUM, LOW — CRITICAL means missing it has a hard "
            "cost (placement eligibility, exam eligibility, a fine) and action is due soon.\n"
            "Category is exactly one of these ids:\n"
            f"{campus.categories_prompt_list()}\n\n"
            "Return ONLY a JSON object with the keys 'priority', 'category', 'confidence' (0.0-1.0)."
        )
        user_prompt = f"Examples:\n{few_shot}\n\nNow classify this email:\nEmail: {masked_text[:3000]}\nResult:"

        try:
            data = llm_provider.invoke_json(system_prompt, user_prompt, purpose="triage", max_tokens=120)
            if not isinstance(data, dict):
                raise ValueError("classification reply was not a JSON object")

            priority = str(data.get("priority", "MEDIUM")).upper()
            if priority not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                priority = "MEDIUM"
            category = campus.normalise_category(data.get("category"))
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
            return ClassificationResult(priority=priority, category=category, confidence=confidence)
        except Exception as e:
            logger.warning("LLM classification failed: %s. Falling back to rules.", e)
            return self._fallback_classify(masked_text, sender)
