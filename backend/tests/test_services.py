import pytest
from datetime import datetime, timezone
from app.services.classification import ClassificationService
from app.services.commitments import CommitmentService
from app.services.scorers import DeadlineScorer, SentimentScorer, CompositeAggregator, ActionTypeScorer, ThreadAgeDecayScorer
from app.services.graph import GraphClient
from app.models.schemas import AxisScore


def test_classification_fallback_critical():
    svc = ClassificationService()
    result = svc._fallback_classify("URGENT: production outage asap")
    assert result.priority == "CRITICAL"
    assert result.confidence >= 0.9


def test_classification_fallback_low():
    svc = ClassificationService()
    result = svc._fallback_classify("FYI here is the newsletter")
    assert result.priority == "LOW"


def test_commitment_fallback_extracts():
    svc = CommitmentService(GraphClient())
    results = svc._fallback_extract("Please review the document by Friday and approve it.")
    assert len(results) > 0
    assert any("review" in c.commitment.lower() for c in results)


def test_deadline_scorer_no_deadline():
    scorer = DeadlineScorer()
    result = scorer.score("No deadline mentioned here")
    assert result.raw_score == 0.0


def test_deadline_scorer_today():
    scorer = DeadlineScorer()
    result = scorer.score("Please submit by today")
    assert result.raw_score > 0.8


def test_sentiment_scorer_urgent():
    scorer = SentimentScorer()
    result = scorer.score("This is URGENT and a critical blocker")
    assert result.raw_score == 1.0


def test_composite_aggregator_critical():
    aggregator = CompositeAggregator()
    axes = [
        AxisScore(axis="deadline", raw_score=1.0, explanation=""),
        AxisScore(axis="authority", raw_score=1.0, explanation=""),
        AxisScore(axis="sentiment", raw_score=1.0, explanation=""),
        AxisScore(axis="decay", raw_score=1.0, explanation=""),
        AxisScore(axis="action", raw_score=1.0, explanation=""),
    ]
    result = aggregator.aggregate(axes)
    assert result.priority == "CRITICAL"
    assert result.composite_score == 100.0


def test_pii_masking():
    from app.services.rag import mask_pii
    text = "Contact john@example.com or call +1-555-123-4567"
    masked = mask_pii(text)
    assert "@" not in masked
    assert "john" not in masked
