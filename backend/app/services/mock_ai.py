from app.models import Draft, TriageScore


def generate_mock_triage_score(email_id: str) -> TriageScore:
    if email_id == "1":
        return TriageScore(
            deadline_proximity=90,
            sender_authority=80,
            sentiment_urgency=75,
            thread_age_decay=10,
            action_type=85,
            composite_score=83.5,
            explanation=(
                "High priority due to approaching project deadline and sender "
                "is a key stakeholder."
            )
        )
    elif email_id == "2":
        return TriageScore(
            deadline_proximity=20,
            sender_authority=50,
            sentiment_urgency=10,
            thread_age_decay=5,
            action_type=40,
            composite_score=25.0,
            explanation="Low priority newsletter update."
        )
    else:
        return TriageScore(
            deadline_proximity=50,
            sender_authority=60,
            sentiment_urgency=50,
            thread_age_decay=20,
            action_type=60,
            composite_score=55.0,
            explanation="Standard priority follow-up request."
        )

def generate_mock_draft(email_id: str) -> Draft:
    if email_id == "1":
        return Draft(
            email_id=email_id,
            draft_content=(
                "Hi Sarah,\n\nThanks for the update. "
                "I will have the final presentation ready by EOD tomorrow as requested.\n\n"
                "Best,\nMailMind User"
            ),
            commitments_detected=["Deliver final presentation by EOD tomorrow"]
        )
    return Draft(
        email_id=email_id,
        draft_content="Noted, thank you.",
        commitments_detected=[]
    )
