import logging

from fastapi import APIRouter
from opentelemetry import trace

from app.models import ApprovalInput, ConflictInput, EmailInput
from services.conflict_service import detect_conflict_and_precedent
from services.triage_service import calculate_priority

router = APIRouter()
tracer = trace.get_tracer(__name__)

emails = [
    {
        "id": 1,
        "sender": "manager@company.com",
        "subject": "Need report by today",
        "body": "Please send the project report by 5 PM today.",
        "status": "Pending",
    },
    {
        "id": 2,
        "sender": "client@company.com",
        "subject": "Urgent meeting",
        "body": "Can we reschedule today's meeting?",
        "status": "Pending",
    },
    {
        "id": 3,
        "sender": "friend@gmail.com",
        "subject": "Weekend plans",
        "body": "Let's meet on Saturday.",
        "status": "Pending",
    },
]


@router.get("/")
def home():
    return {"message": "MailMind Backend Running"}


@router.get("/emails")
def get_emails():
    scored_emails = []

    for email in emails:
        triage_result = calculate_priority(
            EmailInput(
                sender=email["sender"],
                subject=email["subject"],
                body=email["body"],
            )
        )

        scored_emails.append({
            **email,
            **triage_result,
        })

    scored_emails.sort(key=lambda x: x["priority_score"], reverse=True)
    return scored_emails


@router.post("/triage")
def triage_email(email: EmailInput):
    logging.info(f"Triage requested for sender: {email.sender}")

    with tracer.start_as_current_span("five_axis_triage"):
        result = calculate_priority(email)

    logging.info(f"Triage result: {result}")
    return result


@router.post("/conflict-check")
def conflict_check(email: ConflictInput):
    return detect_conflict_and_precedent(email)


@router.post("/approve")
def approve_draft(approval: ApprovalInput):
    if approval.email_id:
        for email in emails:
            if email["id"] == approval.email_id:
                if approval.action.lower() == "approve":
                    email["status"] = "Approved"
                elif approval.action.lower() == "reject":
                    email["status"] = "Rejected"

    if approval.action.lower() == "approve":
        return {
            "status": "Approved",
            "message": "Draft approved by human. Email is ready to send.",
            "draft_reply": approval.draft_reply,
        }

    if approval.action.lower() == "reject":
        return {
            "status": "Rejected",
            "message": "Draft rejected by human.",
        }

    return {
        "status": "Invalid action",
        "message": "Use approve or reject.",
    }