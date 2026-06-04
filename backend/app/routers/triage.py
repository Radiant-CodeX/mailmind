from fastapi import APIRouter, HTTPException

from app.models import Draft, TriageScore
from app.routers.emails import MOCK_EMAILS
from app.services.llm import analyze_email_with_llm, generate_draft_with_llm
from app.services.pii import pii_sanitizer

router = APIRouter()

def get_email_by_id(email_id: str):
    for email in MOCK_EMAILS:
        if email.id == email_id:
            return email
    return None

@router.get("/triage/{email_id}", response_model=TriageScore)
async def get_triage_score(email_id: str):
    email = get_email_by_id(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    # 1. PII Masking
    masked_body, mask_mapping = pii_sanitizer.mask_text(email.body)
    
    # 2. LLM Call (runs with masked body to avoid sending PII to LLM)
    triage_score = analyze_email_with_llm(email.id, masked_body, email.sender, email.subject)
    
    # 3. PII Restoration on the AI-generated explanation
    triage_score.explanation = pii_sanitizer.restore_text(triage_score.explanation, mask_mapping)
    
    return triage_score

@router.get("/draft/{email_id}", response_model=Draft)
async def get_draft(email_id: str):
    email = get_email_by_id(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
        
    # 1. PII Masking
    masked_body, mask_mapping = pii_sanitizer.mask_text(email.body)
    
    # 2. LLM Draft Generation (runs with masked body)
    draft = generate_draft_with_llm(email.id, masked_body, email.sender, email.subject)
    
    # 3. PII Restoration on draft content & commitments
    draft.draft_content = pii_sanitizer.restore_text(draft.draft_content, mask_mapping)
    draft.commitments_detected = [
        pii_sanitizer.restore_text(comm, mask_mapping) for comm in draft.commitments_detected
    ]
    
    return draft
