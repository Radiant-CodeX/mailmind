import json
import logging
from typing import List, Optional
from app.models import TriageScore, Draft
from app.config import settings

logger = logging.getLogger("mailmind.llm")

# Initialize OpenAI client if API key is provided
client = None
if settings.OPENAI_API_KEY:
    try:
        if settings.OPENAI_API_TYPE == "azure":
            from openai import AzureOpenAI
            client = AzureOpenAI(
                api_key=settings.OPENAI_API_KEY,
                api_version=settings.OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
            )
            logger.info("Initialized Azure OpenAI client.")
        else:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("Initialized standard OpenAI client.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        client = None
else:
    logger.warning("No OPENAI_API_KEY found. Falling back to Simulated/Mock AI service.")


def analyze_email_with_llm(email_id: str, body: str, sender: str, subject: str) -> TriageScore:
    """
    Analyzes an email to compute the Five-Axis Triage Score.
    Uses LLM if API Key is configured, else falls back to Mock AI.
    """
    # Fallback to Mock AI if client is not configured
    if not client:
        from app.services.mock_ai import generate_mock_triage_score
        return generate_mock_triage_score(email_id)

    model_name = settings.AZURE_OPENAI_DEPLOYMENT if settings.OPENAI_API_TYPE == "azure" else "gpt-4o"
    
    prompt = f"""
    You are the MailMind AI email triage copilot. Analyze the following email and output a priority evaluation.
    
    Sender: {sender}
    Subject: {subject}
    Body:
    {body}
    
    Rate the email on the following five axes (each from 0 to 100):
    1. deadline_proximity: How urgent is the deadline? (0 = no deadline, 100 = immediate attention/today)
    2. sender_authority: Is the sender a high-authority figure or key stakeholder? (0 = unknown/mailing list, 100 = CEO/critical client)
    3. sentiment_urgency: Does the tone suggest a need for immediate action? (0 = informational/casual, 100 = angry/highly stressed/urgent request)
    4. thread_age_decay: Decay factor based on thread age (0 = brand new, 100 = very stale/archived)
    5. action_type: Type of action needed (0 = FYI/newsletter, 100 = critical task delegation/action item)
    
    Calculate a composite_score (float between 0 and 100) which represents the overall priority.
    Provide a concise explanation (1-2 sentences) justifying the scores.
    
    Your response must be a single valid JSON object with the following structure:
    {{
        "deadline_proximity": int,
        "sender_authority": int,
        "sentiment_urgency": int,
        "thread_age_decay": int,
        "action_type": int,
        "composite_score": float,
        "explanation": "string"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a precise enterprise email triage agent. Output only JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return TriageScore(
            deadline_proximity=result_json.get("deadline_proximity", 50),
            sender_authority=result_json.get("sender_authority", 50),
            sentiment_urgency=result_json.get("sentiment_urgency", 50),
            thread_age_decay=result_json.get("thread_age_decay", 10),
            action_type=result_json.get("action_type", 50),
            composite_score=result_json.get("composite_score", 50.0),
            explanation=result_json.get("explanation", "Evaluated by MailMind AI.")
        )
    except Exception as e:
        logger.error(f"LLM Triage score generation failed: {e}. Falling back to mock data.")
        from app.services.mock_ai import generate_mock_triage_score
        return generate_mock_triage_score(email_id)


def generate_draft_with_llm(email_id: str, body: str, sender: str, subject: str) -> Draft:
    """
    Generates a draft reply and extracts commitments.
    Uses LLM if API Key is configured, else falls back to Mock AI.
    """
    if not client:
        from app.services.mock_ai import generate_mock_draft
        return generate_mock_draft(email_id)

    model_name = settings.AZURE_OPENAI_DEPLOYMENT if settings.OPENAI_API_TYPE == "azure" else "gpt-4o"
    
    prompt = f"""
    You are the MailMind AI email drafting assistant. Draft a response to the following email and extract any commitments/tasks you (the recipient) are making.
    
    Email Sender: {sender}
    Email Subject: {subject}
    Email Body:
    {body}
    
    Instructions:
    1. Write a professional, polite, and context-appropriate reply matching a professional Tone DNA.
    2. Identify and list any commitments or tasks that the recipient is agreeing to or expected to perform (e.g., "deliver presentation by tomorrow EOD"). Keep each task brief.
    
    Your response must be a single valid JSON object with the following structure:
    {{
        "draft_content": "string response with newlines as \\n",
        "commitments_detected": ["string task 1", "string task 2"]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful AI email co-pilot. Output only JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return Draft(
            email_id=email_id,
            draft_content=result_json.get("draft_content", "Thank you, I will look into this."),
            commitments_detected=result_json.get("commitments_detected", [])
        )
    except Exception as e:
        logger.error(f"LLM Draft generation failed: {e}. Falling back to mock draft.")
        from app.services.mock_ai import generate_mock_draft
        return generate_mock_draft(email_id)
