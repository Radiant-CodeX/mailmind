# Privacy Policy

**Last Updated:** June 2026  
**Effective Date:** June 12, 2026

## 1. Introduction

MailMind ("**Company**," "**we**," "**us**," "**our**") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our service ("**Service**").

MailMind is an AI-powered email co-pilot that helps you triage, understand, and draft replies to email. We process your email data locally and securely to provide intelligent analysis without exposing sensitive information.

## 2. Information We Collect

### 2.1 Information You Provide Directly

**Authentication Data:**
- Email address
- OAuth tokens from Google or Microsoft (Google/Microsoft IDs, not email passwords)
- Display name and profile photo (if provided by your OAuth provider)
- Device fingerprints (User-Agent, Accept-Language) for trusted device detection

**Email Data:**
- Email headers (sender, subject, timestamp, thread metadata)
- Email body text (for triage analysis and draft generation)
- Attachment metadata (filename, size, type) — attachment contents are not processed
- Labels/folder information (Inbox, Sent, Spam, Trash, etc.)

**Application Data:**
- Feedback submissions (rating, category, message)
- Calendar event metadata (title, time, attendees) for conflict detection
- User preferences (RAG settings, tone DNA profile, account metadata)
- API usage logs (latency, error rates, LLM calls) for performance monitoring

### 2.2 Information Collected Automatically

**Usage Analytics:**
- Pages visited, features used, time spent
- Error and exception logs
- Triage pipeline performance metrics (latency per stage, cache hit rates, LLM error rates)

**Session & Security:**
- Session tokens (stored in HttpOnly cookies, never in application memory)
- Login attempts and device trust history
- Rate-limit events and abuse detection signals

## 3. How We Use Your Information

### 3.1 Core Service Delivery

We use email data to:
- **Triage emails** — score emails across five axes (deadline urgency, sender authority, sentiment, thread decay, action type) to prioritize your inbox
- **Extract commitments** — identify actionable items, deadlines, and stakeholders using AI
- **Detect calendar conflicts** — check proposed deadlines against your calendar
- **Generate drafts** — create AI-assisted replies in your writing style using past email examples (Tone DNA)
- **Retrieve precedents** — find similar past emails to inform your response

### 3.2 AI Processing & PII Protection

**Before any LLM processing, we mask personally identifiable information (PII):**
- Email addresses → `[PII_EMAIL]`
- Phone numbers → `[PII_PHONE]`
- Social Security numbers, credit card numbers, dates of birth → `[PII_REDACTED]`
- Confidential identifiers (API keys, tokens, passwords) → `[PII_SECRET]`

The masked email is sent to Azure OpenAI for triage and draft generation. Raw email bodies are never sent to external LLMs. Only masked metadata and analysis results are stored in our database.

### 3.3 Improving the Service

- Analyzing usage patterns to detect and fix bugs
- Understanding which features are most valuable
- Measuring performance (latency, cache efficiency, LLM cost)
- Training tone DNA models to improve draft quality

### 3.4 Legal & Safety

- Detecting and preventing fraud, abuse, and unauthorized access
- Complying with legal requests from law enforcement
- Protecting intellectual property and legal rights
- Enforcing this Agreement and other policies

## 4. Data Retention

- **Email data (headers & body):** Retained for the duration of your account. You can request deletion at any time, and we will permanently delete it within 30 days.
- **Triage results & drafts:** Cached for 1 hour to avoid re-processing identical emails. Deleted from cache after 1 hour; optionally persisted to the database indefinitely until you request deletion.
- **Tone DNA profiles:** Rebuilt monthly from your sent mail. Deleted when you disconnect an account or request data deletion.
- **Session tokens:** Expire after 24 hours (primary session) or 7 days (quick-login token). Tokens are hashed; raw tokens are never stored.
- **Audit logs:** Retained for 1 year for compliance and security auditing. Audit entries never contain raw PII.
- **Usage analytics:** Aggregate data (not user-attributed) retained indefinitely for performance monitoring.

## 5. Data Security

### 5.1 Encryption

- **In Transit:** All data transmitted over HTTPS (TLS 1.2+)
- **At Rest:** OAuth tokens are Fernet-encrypted before storage. Email bodies stored in the database are encrypted with application-level encryption keys.
- **Session tokens:** Stored as SHA-256 hashes only; raw tokens live exclusively in HttpOnly, Secure, SameSite cookies.

### 5.2 Access Controls

- API endpoints are authenticated; only your authenticated session can access your data
- Engineers cannot access user data without explicit audit trail
- Database credentials are rotated regularly and never committed to version control
- All API calls are rate-limited and monitored for abuse

### 5.3 Third-Party Services

- **Azure OpenAI:** Email (masked) is sent to Microsoft's Azure OpenAI service for triage and draft generation. Microsoft processes this data according to their [Privacy Statement](https://privacy.microsoft.com/).
- **Gmail API / Microsoft Graph API:** Your OAuth tokens are used only to fetch email data via official APIs; we do not have access to your email passwords.

## 6. Data Sharing

We **do not sell or rent your personal data** to third parties.

**We share data only in these cases:**

- **Service Providers:** Azure OpenAI (masked email processing), cloud database providers (Amazon RDS, Supabase/PostgreSQL), and payment processors—only as necessary to provide the Service.
- **Legal Requests:** If required by law, court order, or government request, we will disclose information to the extent legally required. We will attempt to notify you unless prohibited by law.
- **Safety & Fraud:** If we believe disclosure is necessary to prevent fraud, physical harm, or violation of this Agreement.

## 7. Your Rights & Choices

### 7.1 Data Access & Portability (GDPR / DPDP)

You have the right to:
- **Access:** Request a copy of all data we hold about you
- **Portability:** Export your data in a standard format (CSV, JSON)
- **Deletion:** Request permanent deletion of your account and all associated data

To exercise these rights, email us at **[support@mailmind.com]** with proof of identity.

### 7.2 Consent & Withdrawal

By using MailMind, you consent to this Privacy Policy. You can withdraw consent at any time by:
- Disconnecting your email account (revokes our access to future emails)
- Deleting your MailMind account (we delete all stored data within 30 days)

### 7.3 Cookie Management

Our service uses HttpOnly cookies for session management (cannot be accessed by JavaScript). You can clear cookies in your browser settings, which will log you out but not delete your account data.

### 7.4 Email Retention

You control which emails we process:
- Only folders you explicitly sync are monitored (Inbox by default)
- You can disable syncing for any folder
- Requesting account deletion removes all email data we've indexed

## 8. Children's Privacy

MailMind is not intended for use by children under 13 (or the age of digital consent in your jurisdiction). We do not knowingly collect information from children. If we learn that we have collected information from a child, we will promptly delete it.

## 9. International Data Transfers

If you are located outside the United States, your data may be transferred to, and processed in, the United States or other countries. By using MailMind, you consent to this transfer.

For users in the EU/EEA, we rely on Standard Contractual Clauses (SCCs) and Privacy Shield equivalents with our data processors.

## 10. Changes to This Privacy Policy

We may update this Privacy Policy from time to time. We will notify you of material changes by:
1. Posting the updated policy on our website with a new "Last Updated" date
2. Sending an email notification (if you have provided an email)
3. Requiring you to accept the updated policy on next login (if changes materially increase data use)

Continued use of MailMind after updates constitutes your acceptance of the new Privacy Policy.

## 11. Contact Us

If you have questions, concerns, or requests regarding this Privacy Policy, please contact:

**MailMind Support**  
Email: **[support@mailmind.com]**  
Website: **https://mailmind.com**  
Address: **[Your Address]**

For privacy requests (GDPR Subject Access Requests, DPDP grievances, etc.):  
Email: **[privacy@mailmind.com]** with subject "Privacy Request — [Your Name]"

We will respond within 30 days (or as required by applicable law).

---

## 12. Regulatory Compliance

### GDPR (European Users)
MailMind complies with the General Data Protection Regulation (GDPR). You have rights to access, rectification, erasure, restriction, portability, and objection. [See Section 7.1].

### CCPA (California Users)
Under the California Consumer Privacy Act, California residents have rights to know, delete, and opt-out of the "sale" of personal information. MailMind does not sell personal information as defined by CCPA.

### DPDP Act (India)
MailMind complies with India's Digital Personal Data Protection Act (DPDP), 2023. Personal data is processed with consent and clear purpose, and you have rights to grievance redressal.

---

**Version 1.0** — June 2026
