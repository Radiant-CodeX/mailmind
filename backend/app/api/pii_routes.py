"""
PII masking preview — makes the privacy layer visible for demos / audits.
========================================================================

  POST /api/pii/preview   Given arbitrary text, return what the LLM actually
                          receives: the masked text, the detected entity spans
                          (so the UI can highlight them), and per-category counts.

This is the same `pii_sanitizer` used by the live pipeline ingest node, so the
output is a faithful demonstration of production behaviour — not a mock. Raw PII
values are never logged here (only category counts), matching the pipeline's
logging discipline.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.pii import pii_sanitizer

router = APIRouter(tags=["pii"])


class PIIPreviewPayload(BaseModel):
    text: str = Field(..., max_length=20000)


@router.post("/pii/preview")
def pii_preview(payload: PIIPreviewPayload, current_user=Depends(get_current_user)) -> dict:
    """
    Mask the supplied text and report the detected entities.

    Returns:
      - ``masked``    : the text exactly as the LLM would receive it
      - ``entities``  : [{type, start, end}] spans in the ORIGINAL text (for highlighting)
      - ``counts``    : {category: n} how many of each PII category were masked
      - ``engine``    : "presidio" | "regex" — which detection backend is active
      - ``total``     : total entities masked
    """
    text = payload.text or ""
    entities = pii_sanitizer.detect_pii(text)
    masked, mapping = pii_sanitizer.mask_text(text)

    counts: dict[str, int] = {}
    for e in entities:
        counts[e.entity_type] = counts.get(e.entity_type, 0) + 1

    return {
        "original_length": len(text),
        "masked": masked,
        "entities": [
            {"type": e.entity_type, "start": e.start, "end": e.end}
            for e in entities
        ],
        "counts": counts,
        "total": len(entities),
        "engine": "presidio" if pii_sanitizer.use_presidio else "regex",
    }
