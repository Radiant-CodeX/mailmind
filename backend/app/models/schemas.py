from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class EmailPayload(BaseModel):
    """Schema for incoming email payloads used by the ingest endpoint."""

    email_id: str
    sender: EmailStr
    subject: str
    body: str
    received_at: datetime


class IngestResponse(BaseModel):
    """Response returned when an email is accepted into the ingest queue."""

    status: str = "queued"
    queued_at: datetime = Field(default_factory=datetime.utcnow)


class ClassificationResult(BaseModel):
    """Classification output containing priority, category, and confidence."""

    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    category: str
    confidence: float


class AxisScore(BaseModel):
    axis: str
    raw_score: float
    explanation: str


class TriageResult(BaseModel):
    axes: List[AxisScore]
    composite_score: float
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    approval_mode: Literal["GATE", "SUGGEST"]


class CalendarEvent(BaseModel):
    """Model representing a calendar event returned by the calendar endpoints."""

    title: str
    start_time: datetime
    end_time: datetime
    organizer: str


class PrecedentItem(BaseModel):
    """Search result item returned by the RAG retrieval endpoint."""

    email_id: str
    subject: str
    snippet: str
    similarity_score: float


class RAGQuery(BaseModel):
    email_text: str


class CommitmentItem(BaseModel):
    """Represents a detected commitment or task extracted from email text."""

    id: str
    commitment: str
    deadline: Optional[datetime]
    confidence: float
    approved: Optional[bool] = None


class CommitmentExtractionRequest(BaseModel):
    """Payload for extracting commitments from masked email body text."""

    masked_email_text: str
    thread_summary: Optional[str] = None


class CommitmentExtractionResponse(BaseModel):
    commitments: List[CommitmentItem]


class CommitmentApprover(BaseModel):
    email_id: str
    commitments: List[CommitmentItem]


class CommitmentConfirmResponse(BaseModel):
    success: bool
    task_urls: List[str]
    event_urls: List[str]

class EmailInput(BaseModel):
    """Input for triage and email processing routes."""
    sender: EmailStr
    subject: str
    body: str

class ApprovalInput(BaseModel):
    """Input for approving or rejecting a draft reply."""
    email_id: int
    action: str                        # "approve" or "reject"
    draft_reply: Optional[str] = None

class ConflictInput(BaseModel):
    """Input for conflict detection and precedent lookup."""
    sender: EmailStr
    subject: str
    body: str
