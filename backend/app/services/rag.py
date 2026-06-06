from __future__ import annotations
import json
import math
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.config.settings import settings
from app.models.schemas import PrecedentItem


def mask_pii(text: str) -> str:
    """Redact common personally identifiable information from text."""
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b\+?\d[\d\-\s]{7,}\d\b", "[PHONE]", text)
    text = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD]", text)
    return text


class EmbeddingProvider:
    """Embedder using OpenAI's text-embedding-ada-002, with deterministic fallback."""

    def _get_llm_client(self) -> tuple[Any, str]:
        """Return the appropriate OpenAI or AzureOpenAI client, or None if not configured."""
        if settings.use_mock_graph:
            return None, ""
        try:
            from openai import OpenAI, AzureOpenAI
            if settings.azure_openai_api_key and settings.azure_openai_endpoint:
                return AzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version="2024-02-01",
                    azure_endpoint=settings.azure_openai_endpoint
                ), settings.azure_openai_embedding_deployment
            elif settings.openai_api_key:
                return OpenAI(api_key=settings.openai_api_key), "text-embedding-ada-002"
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
        raise RuntimeError(
            "Real Azure OpenAI / OpenAI credentials are not configured in settings, "
            "but USE_MOCK_GRAPH is set to false (Real account mode)."
        )

    def embed(self, text: str) -> list[float]:
        if settings.use_mock_graph:
            normalized = text.lower().strip()
            vector = [0.0] * 64
            for idx, char in enumerate(normalized[:64]):
                vector[idx] = (ord(char) % 32) / 31.0
            return vector

        client, model = self._get_llm_client()
        if client:
            try:
                response = client.embeddings.create(
                    input=[text.replace("\n", " ")],
                    model=model,
                    timeout=5.0
                )
                return response.data[0].embedding
            except Exception:
                pass

        normalized = text.lower().strip()
        vector = [0.0] * 64
        for idx, char in enumerate(normalized[:64]):
            vector[idx] = (ord(char) % 32) / 31.0
        return vector


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
            with open(path, "r", encoding="utf-8") as handle:
                self.documents = json.load(handle)

    def _save(self) -> None:
        path = os.path.join(self.storage_path, "index.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.documents, handle, ensure_ascii=False, indent=2)

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


@dataclass
class AzureAISearchIndex(VectorIndex):
    """Proxy index that currently delegates to the local ChromaDB fallback."""

    storage_path: str = settings.chroma_storage_path
    local_index: ChromaDBIndex = field(default_factory=ChromaDBIndex)

    def index(self, documents: list[dict[str, Any]]) -> None:
        self.local_index.index(documents)

    def search(self, vector: list[float], top_k: int = 3, threshold: float = 0.0) -> list[PrecedentItem]:
        return self.local_index.search(vector, top_k=top_k, threshold=threshold)

    def upsert(self, document: dict[str, Any]) -> None:
        self.local_index.upsert(document)

    def trim(self, max_size: int) -> None:
        self.local_index.trim(max_size)


class RAGIndexFactory:
    """Factory for choosing which embedding index implementation to use."""

    def __call__(self) -> VectorIndex:
        if settings.use_chroma:
            return ChromaDBIndex()
        return AzureAISearchIndex()


class RetrievalService:
    """RAG retrieval service that converts email text into vector queries and handles indexing."""

    def __init__(self, index: VectorIndex, embedder: EmbeddingProvider | None = None) -> None:
        self.index = index
        self.embedder = embedder or EmbeddingProvider()

    def retrieve(self, email_text: str) -> list[dict[str, Any]]:
        vector = self.embedder.embed(mask_pii(email_text))
        return self.index.search(vector, top_k=3, threshold=settings.rag_similarity_threshold)

    def index_sent_emails(self, graph_client: Any, days: int = 180) -> int:
        """Fetch sent emails from Graph, mask PII, generate embeddings in batches of 50, and index them."""
        emails = graph_client.fetch_sent_emails(days=days)
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
