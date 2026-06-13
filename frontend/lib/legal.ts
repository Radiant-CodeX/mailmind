/**
 * Legal document content (Markdown). Kept in sync with the repo-root
 * PRIVACY_POLICY.md and TERMS_OF_SERVICE.md, which are also linked from the
 * Google OAuth consent screen.
 */

export const PRIVACY_MARKDOWN = `# Privacy Policy

**Last Updated:** June 2026
**Effective Date:** June 12, 2026

MailMind ("we", "us", "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use MailMind (the "Service") — an AI-powered email co-pilot that helps you triage, understand, and draft replies to email.

## 1. Information We Collect

### Information You Provide
- **Authentication:** email address, OAuth tokens from Google or Microsoft (provider account IDs — never your email password), display name, and profile photo.
- **Email data:** headers (sender, subject, timestamp, thread metadata), body text (for triage and draft generation), attachment metadata (filename, size, type — contents are not processed), and folder labels.
- **Application data:** feedback submissions, calendar event metadata, preferences (RAG settings, Tone DNA profile, account metadata).

### Information Collected Automatically
- Usage analytics (features used, errors), pipeline performance metrics (latency, cache hit rates, LLM error rates), and security signals (login attempts, device trust, rate-limit events).

## 2. How We Use Your Information

### Core Service
- **Triage** emails across five axes (deadline urgency, sender authority, sentiment, thread decay, action type).
- **Extract commitments** — actionable items, deadlines, and stakeholders.
- **Detect calendar conflicts** against proposed deadlines.
- **Generate drafts** in your writing style (Tone DNA) using similar past emails.
- **Retrieve precedents** — find similar past emails to inform responses.

### AI Processing & PII Protection
Before any LLM processing, we mask personally identifiable information:
- Email addresses → \`[PII_EMAIL]\`
- Phone numbers → \`[PII_PHONE]\`
- SSNs, credit card numbers, dates of birth → \`[PII_REDACTED]\`
- Secrets (API keys, tokens, passwords) → \`[PII_SECRET]\`

The masked email is sent to Azure OpenAI for analysis. **Raw email bodies are never sent to external LLMs.** Only masked metadata and analysis results are stored.

## 3. Data Retention
- **Email data:** retained while your account is active; permanently deleted within 30 days of a deletion request.
- **Triage results & drafts:** cached for 1 hour; optionally persisted until you request deletion.
- **Tone DNA profiles:** deleted when you disconnect an account or delete your data.
- **Session tokens:** expire after 24 hours (session) or 7 days (quick-login); stored only as hashes.
- **Audit logs:** retained 1 year for compliance; never contain raw PII.

## 4. Data Security
- **In transit:** all data over HTTPS (TLS 1.2+).
- **At rest:** OAuth tokens are Fernet-encrypted; session tokens stored as SHA-256 hashes only — raw tokens live exclusively in HttpOnly, Secure, SameSite cookies.
- **Access controls:** every data-touching API endpoint requires an authenticated session; all calls are rate-limited and monitored.

### Third-Party Services
- **Azure OpenAI** — masked email is processed under Microsoft's [Privacy Statement](https://privacy.microsoft.com/).
- **Gmail API / Microsoft Graph API** — OAuth tokens fetch email via official APIs only; we never see your email password.

## 5. Data Sharing
We **do not sell or rent your personal data.** We share data only with service providers (Azure OpenAI, our database host) as necessary to run the Service, when legally required, or to prevent fraud and abuse.

## 6. Your Rights & Choices
You have the right to **access**, **export**, and **delete** your data. Exercise these rights by emailing **[privacy@mailmind.com]** with proof of identity; we respond within 30 days. You may withdraw consent at any time by disconnecting your email account or deleting your MailMind account.

## 7. Children's Privacy
MailMind is not intended for children under 13 (or the age of digital consent in your jurisdiction). We do not knowingly collect their information.

## 8. International Data Transfers
Your data may be processed in the United States or other countries. For EU/EEA users we rely on Standard Contractual Clauses with our processors.

## 9. Changes to This Policy
We may update this policy and will post the revised version with a new "Last Updated" date and notify you of material changes. Continued use constitutes acceptance.

## 10. Regulatory Compliance
- **GDPR (EU):** rights to access, rectification, erasure, restriction, portability, and objection.
- **CCPA (California):** rights to know, delete, and opt out of the "sale" of personal information. We do not sell personal information.
- **DPDP Act (India):** consent-based processing with clear purpose and grievance redressal.

## 11. Contact Us
**MailMind Support** — **[support@mailmind.com]** — **https://mailmind.com**
For privacy requests: **[privacy@mailmind.com]** (subject: "Privacy Request").

---

**Version 1.0** — June 2026
`;

export const TERMS_MARKDOWN = `# Terms of Service

**Last Updated:** June 2026
**Effective Date:** June 12, 2026

These Terms of Service ("Terms") are a binding agreement between you and MailMind ("we", "us", "our"). By accessing or using MailMind (the "Service"), you agree to these Terms. If you do not agree, you may not use the Service.

## 1. Service Description
MailMind is an AI-powered email co-pilot that helps you triage emails, extract commitments, generate AI-assisted drafts, detect calendar conflicts, and retrieve precedents. The Service is provided on an "AS-IS" basis with no warranty that it is error-free, uninterrupted, or fit for a specific purpose.

## 2. Eligibility & Accounts
You must be at least 13 (or the age of digital consent in your jurisdiction) and have authority to enter this agreement. You are responsible for safeguarding your credentials and for all activity under your account, and must notify us of any unauthorized access.

## 3. Use License & Restrictions
We grant you a non-exclusive, non-transferable, revocable license to use the Service for personal email management. You agree **not to**:
- Scrape, crawl, or bulk-harvest email data.
- Reverse-engineer the Service or its algorithms.
- Access accounts or data you do not own or have permission to access.
- Send spam, phishing, or malicious content.
- Use the Service for illegal activity or to infringe third-party rights.
- Overload our infrastructure (rate limiting applies).
- Impersonate others or harass, threaten, or abuse anyone.

## 4. Intellectual Property
- **Our IP:** all software, designs, algorithms, and documentation are owned by MailMind or our licensors.
- **Your content:** you retain ownership of your email data, calendars, and feedback. You grant us a limited license to store and analyze email data to provide the Service and to build your Tone DNA profile. You may revoke it by deleting your account.
- **Feedback:** suggestions you provide are voluntary and grant us a perpetual, royalty-free license to use them.

## 5. Limitation of Liability
**THE SERVICE IS PROVIDED "AS-IS" WITHOUT WARRANTIES OF ANY KIND.** We do not warrant that triage scores, drafts, or summaries are accurate or appropriate for every context. **Always review AI-generated drafts before sending.** To the maximum extent permitted by law, MailMind is not liable for indirect, consequential, or punitive damages, and our total liability is limited to the amount you paid us in the prior 12 months (or $100, whichever is less).

## 6. Third-Party Services
MailMind integrates with the Gmail API, Microsoft Graph API, Azure OpenAI, and Google Calendar API. We are not responsible for third-party outages, breaches, policy changes, or API changes that affect our integrations.

## 7. Suspension & Termination
You may delete your account at any time; we permanently delete associated data within 30 days. We may suspend or terminate accounts that violate these Terms, engage in abuse or illegal activity, or pose a security risk. You may appeal a suspension at **[support@mailmind.com]**.

## 8. Payment & Fees
MailMind offers a free tier and optional paid plans. Paid plans renew automatically until canceled; cancellation takes effect at the end of the current billing period. We may change pricing with 30 days' notice.

## 9. Indemnification
You agree to indemnify and hold harmless MailMind from claims, damages, or expenses arising from your violation of these Terms, your misuse of the Service, or your content.

## 10. Governing Law & Disputes
These Terms are governed by the laws of **[Your Jurisdiction]**. Disputes will be resolved through binding arbitration (except IP claims and injunctive relief), and **you waive participation in class actions**. Before arbitration, send written notice to **[disputes@mailmind.com]** and allow 30 days to resolve.

## 11. General
If any provision is found unenforceable, the rest remain in effect. These Terms, with our [Privacy Policy](/privacy), are the entire agreement between you and MailMind.

## 12. Regional Rights
- **California:** rights to know, delete, correct, and opt out of the "sale" of personal data (we do not sell it).
- **GDPR (EU):** rights to access, rectification, erasure, restriction, portability, and to withdraw consent.
- **DPDP Act (India):** consent-based processing, access/correction/deletion, and grievance redressal.

## 13. Contact
**MailMind Support** — **[support@mailmind.com]** — **https://mailmind.com**
Legal notices: **[legal@mailmind.com]**.

## Glossary

| Term | Definition |
|------|-----------|
| Service | MailMind software, APIs, and related features |
| User / You | Any person or entity using MailMind |
| Content | Email, calendar, feedback, and other data you provide |
| AI-Generated Content | Triage scores, drafts, and summaries created by MailMind |
| Masked Data | Email data with PII redacted (e.g. emails → \`[PII_EMAIL]\`) |
| Tone DNA | Your personalized writing-style profile |

---

**Version 1.0** — June 2026

By using MailMind, you acknowledge that you have read, understood, and agree to be bound by these Terms.
`;
