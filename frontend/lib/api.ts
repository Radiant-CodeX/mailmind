export const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function classifyEmail(text: string) {
  const res = await fetch(`${BASE}/api/classify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email_text: text }),
  });
  if (!res.ok) throw new Error('Classification failed');
  return res.json();
}

export async function triageEmail(payload: { email_id: string; sender: string; subject: string; body: string; received_at: string }) {
  const res = await fetch(`${BASE}/api/triage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Triage scoring failed');
  return res.json();
}

export async function extractCommitments(maskedText: string, threadSummary = '', emailId?: string) {
  const res = await fetch(`${BASE}/api/commitments/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      masked_email_text: maskedText,
      thread_summary: threadSummary,
      email_id: emailId
    }),
  });
  if (!res.ok) throw new Error('Commitment extraction failed');
  return res.json();
}

export async function confirmCommitments(emailId: string, commitments: any[]) {
  const res = await fetch(`${BASE}/api/commitments/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Approval-Token': process.env.NEXT_PUBLIC_APPROVAL_TOKEN || 'secret-approval-token',
    },
    body: JSON.stringify({ email_id: emailId, commitments }),
  });
  if (!res.ok) throw new Error('Confirmation failed');
  return res.json();
}

export async function retrievePrecedents(text: string) {
  const res = await fetch(`${BASE}/api/rag/retrieve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email_text: text }),
  });
  if (!res.ok) throw new Error('RAG retrieval failed');
  return res.json();
}

export async function generateDraftPrompt(text: string) {
  const res = await fetch(`${BASE}/api/rag/inject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email_text: text }),
  });
  if (!res.ok) throw new Error('Draft generation prompt inject failed');
  return res.json();
}

export async function fetchCalendar(days = 3) {
  const res = await fetch(`${BASE}/api/calendar?days=${days}`);
  if (!res.ok) throw new Error('Calendar fetch failed');
  return res.json();
}

export async function ingestEmail(payload: any) {
  const res = await fetch(`${BASE}/api/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (res.status === 429) {
    throw new Error('Rate limit exceeded. Please try again in 1 minute.');
  }
  if (!res.ok) throw new Error('Ingest failed');
  return res.json();
}

export async function fetchEmails(limit = 10) {
  const res = await fetch(`${BASE}/api/emails?limit=${limit}`);
  if (!res.ok) throw new Error('Emails fetch failed');
  return res.json();
}

export async function loginInitiate() {
  const res = await fetch(`${BASE}/api/auth/login-initiate`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to initiate login flow');
  return res.json();
}

export async function loginPoll(deviceCode: string) {
  const res = await fetch(`${BASE}/api/auth/login-poll`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_code: deviceCode }),
  });
  if (!res.ok) throw new Error('Polling request failed');
  return res.json();
}

export async function checkAuthStatus() {
  const res = await fetch(`${BASE}/api/auth/status`);
  if (!res.ok) throw new Error('Auth status check failed');
  return res.json();
}

export async function logoutUser() {
  const res = await fetch(`${BASE}/api/auth/logout`, { method: 'POST' });
  if (!res.ok) throw new Error('Logout request failed');
  return res.json();
}

export async function loginMock() {
  const res = await fetch(`${BASE}/api/auth/login-mock`, { method: 'POST' });
  if (!res.ok) throw new Error('Mock login failed');
  return res.json();
}
