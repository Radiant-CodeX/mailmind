from pydantic import BaseModel


class EmailInput(BaseModel):
    sender: str
    subject: str
    body: str


class ConflictInput(BaseModel):
    sender: str
    subject: str
    body: str


class ApprovalInput(BaseModel):
    draft_reply: str
    action: str
    email_id: int | None = None