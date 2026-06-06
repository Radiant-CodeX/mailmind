def calculate_priority(email):
    score = 0
    explanation = []

    text = (email.subject + " " + email.body).lower()

    if "today" in text or "tomorrow" in text or "deadline" in text:
        score += 30
        explanation.append("Deadline detected: +30")

    if "manager" in email.sender or "client" in email.sender:
        score += 25
        explanation.append("Important sender: +25")

    if "urgent" in text or "asap" in text or "immediately" in text:
        score += 20
        explanation.append("Urgent language detected: +20")

    if "please" in text or "send" in text or "review" in text:
        score += 10
        explanation.append("Action required: +10")

    priority = "Critical" if score >= 70 else "High" if score >= 40 else "Normal"

    urgency = (
        "Immediate"
        if "urgent" in text or "immediately" in text or "asap" in text
        else "Time Sensitive"
        if "today" in text or "tomorrow" in text or "deadline" in text
        else "Low"
    )

    if "reschedule" in text or "meeting" in text:
        intent = "Meeting Request"
    elif "send" in text or "report" in text or "review" in text:
        intent = "Task Request"
    elif "issue" in text or "problem" in text or "complaint" in text:
        intent = "Complaint"
    else:
        intent = "General Information"

    if "thank" in text or "great" in text or "good" in text:
        sentiment = "Positive"
    elif "problem" in text or "issue" in text or "angry" in text:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    if "client" in email.sender:
        category = "Client Communication"
    elif "manager" in email.sender:
        category = "Internal Management"
    elif "meeting" in text:
        category = "Scheduling"
    elif "report" in text:
        category = "Project Work"
    else:
        category = "General"

    return {
        "priority_score": score,
        "priority_label": priority,
        "urgency": urgency,
        "intent": intent,
        "sentiment": sentiment,
        "category": category,
        "explanation": explanation,
    }