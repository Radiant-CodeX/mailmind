from fastapi import APIRouter

from app.models import EmailInput
from services.azure_openai_service import azure_draft, azure_summary
from services.triage_service import calculate_priority

router = APIRouter()


@router.post("/summary")
def summarize_email(email: EmailInput):
    priority = calculate_priority(email)

    try:
        ai_text = azure_summary(email, priority)

        return {
            "summary": ai_text,
            "action_required": "AI-generated action available",
            "urgency": priority["priority_label"],
            "recommended_response_time": "Based on priority",
            "priority_score": priority["priority_score"],
            "source": "Azure OpenAI GPT-4o",
        }

    except Exception as error:
        return {
            "summary": f"{email.sender} sent an email regarding '{email.subject}'.",
            "action_required": f"Respond to {email.subject}",
            "urgency": priority["priority_label"],
            "recommended_response_time": "Within the day",
            "priority_score": priority["priority_score"],
            "source": "Fallback mock response",
            "error": str(error),
        }


@router.post("/draft")
def generate_draft(email: EmailInput):
    try:
        draft = azure_draft(email)

        return {
            "draft_reply": draft,
            "status": "AI draft generated using Azure OpenAI. Waiting for human approval.",
            "source": "Azure OpenAI GPT-4o",
        }

    except Exception as error:
        draft = f"""
Hello,

Thank you for your email regarding "{email.subject}".

I have received your message and will review it shortly.

I will get back to you with an update soon.

Regards,
Rithish Barath
"""

        return {
            "draft_reply": draft,
            "status": "Fallback draft generated. Waiting for human approval.",
            "source": "Fallback mock response",
            "error": str(error),
        }