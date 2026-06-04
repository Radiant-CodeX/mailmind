from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TriageScore(BaseModel):
    deadline_proximity: int
    sender_authority: int
    sentiment_urgency: int
    thread_age_decay: int
    action_type: int
    composite_score: float
    explanation: str

class Email(BaseModel):
    id: str
    sender: str
    subject: str
    snippet: str
    body: str
    date: datetime
    is_read: bool
    triage_score: Optional[TriageScore] = None

class Draft(BaseModel):
    email_id: str
    draft_content: str
    commitments_detected: List[str]

class TaskCreate(BaseModel):
    title: str
    due_date: Optional[str] = None
    email_ref: Optional[str] = None

class TaskResponse(BaseModel):
    id: str
    title: str
    status: str
    due_date: str
    email_ref: str

