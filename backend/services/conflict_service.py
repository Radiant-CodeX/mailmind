def detect_conflict_and_precedent(email):
    text = (email.subject + " " + email.body).lower()

    previous_cases = [
        {
            "type": "Scheduling Conflict",
            "keywords": ["reschedule", "meeting"],
            "precedent": "A meeting was previously rescheduled. Check calendar availability before approving.",
        },
        {
            "type": "Deadline Conflict",
            "keywords": ["today", "deadline", "report"],
            "precedent": "A same-day deadline request was previously marked as high priority.",
        },
        {
            "type": "Client Escalation",
            "keywords": ["urgent", "client", "asap"],
            "precedent": "Urgent client requests were previously escalated for quick response.",
        },
    ]

    for case in previous_cases:
        if all(keyword in text for keyword in case["keywords"]):
            return {
                "conflict_detected": True,
                "conflict_type": case["type"],
                "precedent_found": True,
                "precedent": case["precedent"],
                "recommendation": "Review this email carefully before approving an AI-generated response.",
            }

    return {
        "conflict_detected": False,
        "conflict_type": "None",
        "precedent_found": False,
        "precedent": "No matching precedent found.",
        "recommendation": "Safe to proceed with normal AI-assisted workflow.",
    }