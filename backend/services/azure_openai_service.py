from openai import AzureOpenAI

from app.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_ENDPOINT,
)

azure_client = None

if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME:
    azure_client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def azure_summary(email, priority):
    if azure_client is None:
        raise Exception("Azure OpenAI environment variables missing.")

    prompt = f"""
Analyze this email and return a concise business summary.

Sender: {email.sender}
Subject: {email.subject}
Body: {email.body}
Priority: {priority["priority_label"]}
Score: {priority["priority_score"]}

Return only this format:
Summary: ...
Action Required: ...
Recommended Response Time: ...
"""

    response = azure_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": "You are MailMind AI, an enterprise email triage assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=180,
        temperature=0.3,
    )

    return response.choices[0].message.content


def azure_draft(email):
    if azure_client is None:
        raise Exception("Azure OpenAI environment variables missing.")

    prompt = f"""
Write a professional email reply.

Original Email:
Sender: {email.sender}
Subject: {email.subject}
Body: {email.body}

Requirements:
- Be professional and polite
- Keep it concise
- Do not say anything unrealistic
- End with:
Regards,
Rithish Barath
"""

    response = azure_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": "You are MailMind AI, a professional email drafting assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=250,
        temperature=0.4,
    )

    return response.choices[0].message.content