from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.config.settings import settings
from app.models.schemas import PrecedentItem

logger = logging.getLogger(__name__)


def mask_pii(text: str) -> str:
    """Redact common personally identifiable information from text."""
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b\+?\d[\d\-\s]{7,}\d\b", "[PHONE]", text)
    text = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD]", text)
    return text


class EmbeddingProvider:
    """Embeds text with the caller's configured embedding model, if any.

    Most free chat providers (OpenRouter, Groq) don't serve embeddings, so the
    default is a free, offline hashed bag-of-words embedding — see
    ``llm_provider.local_embed``. A user who sets an embedding model (e.g.
    Gemini ``text-embedding-004``) gets dense model embeddings instead.
    """

    def embed(self, text: str) -> list[float]:
        from app.services.llm_provider import embed_text, local_embed

        if settings.use_mock_mail:
            return local_embed(text)
        return embed_text(text)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute similarity between two fixed-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorIndex(ABC):
    """Abstract interface for a vector-based retrieval index."""

    @abstractmethod
    def index(self, documents: list[dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def search(self, vector: list[float], top_k: int = 3, threshold: float = 0.0) -> list[PrecedentItem]:
        pass

    @abstractmethod
    def upsert(self, document: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def trim(self, max_size: int) -> None:
        pass


@dataclass
class ChromaDBIndex(VectorIndex):
    """Local fallback index that persists vectors and metadata to disk."""

    storage_path: str = settings.chroma_storage_path
    documents: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.storage_path = os.path.abspath(self.storage_path)
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        path = os.path.join(self.storage_path, "index.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    self.documents = json.load(handle)
            except json.JSONDecodeError as exc:
                # A corrupt index must not take retrieval (and drafting) down;
                # it is a cache of sent mail and rebuilds as mail is re-indexed.
                logger.warning("[RAG] index at %s is corrupt (%s) — starting empty", path, exc)
                self.documents = []

    def _save(self) -> None:
        # Write-then-rename so a crash or a concurrent reader never sees a
        # half-written file (the cause of corrupt index.json files).
        path = os.path.join(self.storage_path, "index.json")
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self.documents, handle, ensure_ascii=False)
        os.replace(tmp, path)

    def index(self, documents: list[dict[str, Any]]) -> None:
        """Index or update multiple documents in the local storage."""
        for doc in documents:
            self.upsert(doc)
        self._save()

    def upsert(self, document: dict[str, Any]) -> None:
        """Insert or update a document, then trim the index to size."""
        existing = next((entry for entry in self.documents if entry["email_id"] == document["email_id"]), None)
        if existing:
            existing.update(document)
        else:
            self.documents.append(document)
        self.trim(settings.index_max_size)
        self._save()

    def search(self, vector: list[float], top_k: int = 3, threshold: float = 0.0) -> list[PrecedentItem]:
        """Search the local index and return nearest precedent items."""
        candidates = []
        for doc in self.documents:
            similarity = cosine_similarity(vector, doc.get("embedding", []))
            if similarity >= threshold:
                candidates.append((similarity, doc))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [
            PrecedentItem(
                email_id=doc["email_id"],
                subject=doc["subject"],
                snippet=doc.get("masked_body", ""),
                similarity_score=similarity,
            )
            for similarity, doc in candidates[:top_k]
        ]

    def trim(self, max_size: int) -> None:
        """Keep only the most recent documents up to max_size."""
        if len(self.documents) <= max_size:
            return
        self.documents = self.documents[-max_size:]
        self._save()


class RAGIndexFactory:
    """Factory for the vector index implementation (local on-disk index)."""

    def __call__(self) -> VectorIndex:
        return ChromaDBIndex()


class RetrievalService:
    """RAG retrieval service that converts email text into vector queries and handles indexing."""

    def __init__(self, index: VectorIndex, embedder: EmbeddingProvider | None = None) -> None:
        self.index = index
        self.embedder = embedder or EmbeddingProvider()

    def retrieve(self, email_text: str) -> list[Any]:
        from app.services.llm_provider import similarity_threshold

        vector = self.embedder.embed(mask_pii(email_text))
        results = self.index.search(vector, top_k=3, threshold=similarity_threshold())

        # RAG-06: Flag precedents that dealt with a serious academic situation
        # (so the UI can say "similar to the attendance warning on 12 Aug").
        ESCALATION_KEYWORDS = [
            "escalat", "debar", "detain", "attendance shortage", "disciplinary",
            "penalty", "fine", "suspension", "malpractice", "not eligible", "arrear",
            "emergency", "complaint",
        ]
        for item in results:
            snippet = (item.snippet if hasattr(item, "snippet") else "").lower()
            if any(kw in snippet for kw in ESCALATION_KEYWORDS):
                # Attach incident flag to the item for frontend display
                if hasattr(item, "__dict__"):
                    item.__dict__["incident_flag"] = True
                    # Try to extract a date from the snippet for "Similar to incident on X"
                    import re as _re
                    date_match = _re.search(
                        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
                        r"|\d{4}-\d{2}-\d{2})\b",
                        item.snippet,
                        _re.I,
                    )
                    item.__dict__["incident_date"] = date_match.group(0) if date_match else None
        return results

    def index_sent_emails(self, mail_client: Any, days: int = 180) -> int:
        """Fetch sent emails from the mail provider, mask PII, embed in batches of 50, and index them."""
        emails = mail_client.fetch_sent_emails(days=days)
        indexed_count = 0
        batch_size = 50
        
        # Process in batches of 50
        for i in range(0, len(emails), batch_size):
            batch = emails[i : i + batch_size]
            documents = []
            for email in batch:
                body = email.get("body", "")
                if isinstance(body, dict):
                    body = body.get("content", "")
                elif not body:
                    body = email.get("bodyPreview", "")
                
                masked_body = mask_pii(str(body))
                embedding = self.embedder.embed(masked_body)
                
                documents.append({
                    "email_id": email.get("id"),
                    "subject": email.get("subject", "No Subject"),
                    "masked_body": masked_body,
                    "embedding": embedding
                })
            
            self.index.index(documents)
            indexed_count += len(documents)
            
        return indexed_count


class PrecedentInjector:
    """Build a prompt from precedent emails and return citation metadata."""

    @staticmethod
    def inject(email_text: str, precedents: Iterable[PrecedentItem]) -> dict[str, Any]:
        items = list(precedents)[:3]
        if not items:
            prompt = email_text
            citations: list[dict[str, Any]] = []
        else:
            context = "\n".join([f"- {item.subject}: {item.snippet}" for item in items])
            prompt = (
                f"Here are 3 similar emails you've sent: {context}\n\n"
                f"Use their tone and structure to draft a response to the following email:\n{email_text}"
            )
            citations = [
                {
                    "email_id": item.email_id,
                    "subject": item.subject,
                    "similarity": item.similarity_score,
                }
                for item in items
            ]
        return {"prompt": prompt, "precedent_citations": citations}
