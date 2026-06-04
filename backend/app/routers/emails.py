from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter

from app.models import Email
from app.services.mock_ai import generate_mock_triage_score

router = APIRouter()

MOCK_EMAILS = [
    Email(
        id="1",
        sender="sarah.connor@cyberdyne.com",
        subject="URGENT: Project Skynet Deployment Deadline",
        snippet="Please confirm if the final presentation is ready by tomorrow.",
        body=(
            "Hi,\n\nWe need to ensure all systems are a go for the deployment. "
            "Please confirm if the final presentation is ready by tomorrow.\n\nThanks,\nSarah"
        ),
        date=datetime.now() - timedelta(minutes=15),
        is_read=False,
        triage_score=generate_mock_triage_score("1")
    ),
    Email(
        id="2",
        sender="newsletter@marketing.com",
        subject="Weekly Tech Insights",
        snippet="Check out the top 10 AI frameworks of 2026...",
        body="Welcome to the weekly tech insights! Here are the top 10 AI frameworks...",
        date=datetime.now() - timedelta(hours=2),
        is_read=True,
        triage_score=generate_mock_triage_score("2")
    ),
    Email(
        id="3",
        sender="john.doe@company.com",
        subject="Follow up on Q3 goals",
        snippet="Did you get a chance to review the Q3 goals document?",
        body=(
            "Hey,\n\nJust wanted to bump this to the top of your inbox. "
            "Did you get a chance to review the Q3 goals document?\n\nBest,\nJohn"
        ),
        date=datetime.now() - timedelta(days=1),
        is_read=False,
        triage_score=generate_mock_triage_score("3")
    )
]

@router.get("/emails", response_model=List[Email])
async def get_emails():
    # Sort emails by composite score descending
    sorted_emails = sorted(
        MOCK_EMAILS,
        key=lambda e: e.triage_score.composite_score if e.triage_score else 0,
        reverse=True
    )
    return sorted_emails

@router.get("/emails/{email_id}", response_model=Email)
async def get_email(email_id: str):
    for email in MOCK_EMAILS:
        if email.id == email_id:
            return email
    return None
