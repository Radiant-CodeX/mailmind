import { CommitmentItem } from './types';

/**
 * Resolve the backend base URL.
 *  1. Explicit NEXT_PUBLIC_API_URL wins.
 *  2. Otherwise use the SAME host the page is served from (so opening the app at
 *     127.0.0.1:3000 talks to 127.0.0.1:8000, and localhost:3000 to localhost:8000).
 *     This avoids the Windows "localhost → IPv6 ::1" mismatch that makes fetch fail.
 *  3. SSR fallback: 127.0.0.1 (IPv4 — what uvicorn binds by default).
 */
function resolveBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return 'http://127.0.0.1:8000';
}

export const BASE = resolveBase();

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

export async function confirmCommitments(emailId: string, commitments: CommitmentItem[]) {
  const res = await fetch(`${BASE}/api/commitments/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Approval-Token': process.env.NEXT_PUBLIC_APPROVAL_TOKEN || 'secret-approval-token',
    },
    body: JSON.stringify({ email_id: emailId, commitments }),
  });
  if (!res.ok) {
    let message = 'Confirmation failed';
    try {
      const errData = await res.json();
      if (errData && errData.detail) message = errData.detail;
    } catch {
      // keep default message
    }
    throw new Error(message);
  }
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

export async function generateEmailDraft(text: string, style: string, sender?: string, subject?: string) {
  const res = await fetch(`${BASE}/api/rag/draft`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email_text: text,
      style: style,
      sender: sender,
      subject: subject,
    }),
  });
  if (!res.ok) throw new Error('Email draft generation failed');
  return res.json();
}


export async function fetchCalendar(days = 3) {
  const res = await fetch(`${BASE}/api/calendar?days=${days}`);
  if (!res.ok) throw new Error('Calendar fetch failed');
  return res.json();
}

export async function fetchTasks(limit = 20) {
  const res = await fetch(`${BASE}/api/tasks?limit=${limit}`);
  if (!res.ok) throw new Error('Tasks fetch failed');
  return res.json();
}

export async function createTask(title: string) {
  const res = await fetch(`${BASE}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create task');
  return res.json();
}

export async function ingestEmail(payload: Record<string, unknown>) {
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

export async function fetchSentEmails(limit = 10) {
  const res = await fetch(`${BASE}/api/emails/sent?limit=${limit}`);
  if (!res.ok) throw new Error('Sent emails fetch failed');
  return res.json();
}

export async function fetchDraftEmails(limit = 10) {
  const res = await fetch(`${BASE}/api/emails/drafts?limit=${limit}`);
  if (!res.ok) throw new Error('Drafts fetch failed');
  return res.json();
}

export async function fetchSpamEmails(limit = 10) {
  const res = await fetch(`${BASE}/api/emails/spam?limit=${limit}`);
  if (!res.ok) throw new Error('Spam fetch failed');
  return res.json();
}

export async function fetchTrashEmails(limit = 10) {
  const res = await fetch(`${BASE}/api/emails/trash?limit=${limit}`);
  if (!res.ok) throw new Error('Trash fetch failed');
  return res.json();
}

export async function sendEmailReply(emailId: string, comment: string) {
  const res = await fetch(`${BASE}/api/emails/${emailId}/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment }),
  });
  if (!res.ok) throw new Error('Failed to send email reply');
  return res.json();
}

export async function restoreEmailFromTrash(emailId: string) {
  const res = await fetch(`${BASE}/api/emails/${emailId}/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to restore email from trash');
  return res.json();
}

export async function fetchEvaluation() {
  const res = await fetch(`${BASE}/api/evaluate`);
  if (!res.ok) throw new Error('Evaluation fetch failed');
  return res.json();
}

export async function moveEmailToTrash(emailId: string) {
  const res = await fetch(`${BASE}/api/emails/${emailId}/trash`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to move email to trash');
  return res.json();
}

export async function composeEmail(payload: { to: string; subject: string; body: string; cc?: string; bcc?: string }) {
  const res = await fetch(`${BASE}/api/emails/compose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to send email');
  return res.json();
}



export async function loginInitiate() {
  const res = await fetch(`${BASE}/api/auth/login-initiate`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to initiate login flow');
  return res.json();
}

export async function loginPoll(deviceCode: string) {
  try {
    const res = await fetch(`${BASE}/api/auth/login-poll`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_code: deviceCode }),
    });

    if (!res.ok) {
      let errorMessage = 'Polling request failed';
      try {
        const errData = await res.json();
        if (errData && errData.detail) {
          errorMessage = errData.detail;
        }
      } catch {
        // fallback to default message
      }
      throw new Error(errorMessage);
    }

    return res.json();
  } catch (err) {
    throw err;
  }
}

export async function checkAuthStatus() {
  // Fail fast (5s) so the login screen never hangs on a slow/unreachable backend.
  const res = await fetch(`${BASE}/api/auth/status`, { signal: AbortSignal.timeout(5000) });
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

export async function googleLoginInitiate(email?: string) {
  const res = await fetch(`${BASE}/api/auth/google/login-initiate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    let message = 'Google sign-in failed';
    try {
      const data = await res.json();
      if (data?.detail) message = data.detail;
    } catch {
      // keep default
    }
    throw new Error(message);
  }
  return res.json();
}

export async function googleLoginPoll(state: string) {
  const res = await fetch(`${BASE}/api/auth/google/poll`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state }),
  });
  if (!res.ok) {
    let message = 'Google sign-in failed';
    try {
      const data = await res.json();
      if (data?.detail) message = data.detail;
    } catch {
      // keep default
    }
    throw new Error(message);
  }
  return res.json();
}

export async function quickLogin(email: string, provider: string = 'microsoft') {
  const res = await fetch(`${BASE}/api/auth/quick-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, provider }),
  });
  if (!res.ok) {
    let message = 'Quick login failed';
    try {
      const data = await res.json();
      if (data?.detail) message = data.detail;
    } catch {
      // keep default
    }
    throw new Error(message);
  }
  return res.json();
}
