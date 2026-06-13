import { CommitmentItem } from "./types";

/**
 * Resolve the backend base URL.
 *  - If NEXT_PUBLIC_API_URL is set (production), use it directly.
 *  - Otherwise, use relative paths in the browser so the Next.js proxy
 *    forwards /api/* to the backend — cookies are same-origin this way.
 *  - SSR fallback: 127.0.0.1:8000 (what uvicorn binds by default).
 */
function resolveBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) return configured;
  if (typeof window !== "undefined") return ""; // relative — proxy handles it
  return "http://127.0.0.1:8000";
}

export const BASE = resolveBase();

/**
 * Drop-in replacement for `fetch` that always sends HttpOnly session cookies
 * cross-origin (required for the mm_session / mm_quick cookie auth model).
 */
export function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  return fetch(input, { credentials: "include", ...init });
}

export interface UserInfo {
  id: string;
  display_name: string | null;
  primary_email: string | null;
}

export interface AccountInfo {
  id: string;
  provider: "google" | "microsoft";
  email: string;
  photo_url: string | null;
  nickname: string | null;
  color: string | null;
  is_default: boolean;
  sync_enabled: boolean;
  has_token: boolean;
  token_expires_at: string | null;
  created_at: string;
}

export interface AuthStatus {
  status: string;
  authenticated: boolean;
  /** v3 — user object (null when unauthenticated) */
  user: UserInfo | null;
  /** v3 — default account (null when unauthenticated) */
  default_account: AccountInfo | null;
  /** Legacy compat — resolved from user.primary_email */
  user_principal_name?: string | null;
  provider?: "google" | "microsoft";
}

export async function classifyEmail(text: string) {
  const res = await apiFetch(`${BASE}/api/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email_text: text }),
  });
  if (!res.ok) throw new Error("Classification failed");
  return res.json();
}

/**
 * Run ONLY the enrichment phase (commitment + calendar + rag in parallel).
 * Triage is skipped — caller passes the pre-computed triage state from the
 * inbox batch score. This halves the end-to-end latency since the most
 * expensive step (triage LLM call) was already done while loading the inbox.
 */
export async function enrichEmail(payload: {
  email_id: string;
  sender: string;
  subject: string;
  body: string;
  received_at: string;
  masked_body?: string | null;
  axes?: unknown[];
  composite_score?: number;
  priority?: string;
  approval_mode?: string;
  triage_reasoning?: string | null;
  calendar_events?: unknown[];
  current_user_email?: string | null;
  /** Default false — skips RAG/draft. Pass true only when user clicks Generate Draft. */
  generate_draft?: boolean;
}) {
  const res = await apiFetch(`${BASE}/api/agent/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Enrichment failed");
  return res.json();
}

/**
 * Full pipeline fallback — used only when no triage score is available.
 */
export async function processEmailFull(payload: {
  email_id: string;
  sender: string;
  subject: string;
  body: string;
  received_at: string;
  calendar_events?: unknown[];
}) {
  const res = await apiFetch(`${BASE}/api/agent/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Full pipeline failed");
  return res.json();
}

/**
 * Triage a single email through the LangGraph agent pipeline.
 * Uses /api/agent/triage so the LLM call is traced in LangSmith.
 */
export async function triageEmail(payload: {
  email_id: string;
  sender: string;
  subject: string;
  body: string;
  received_at: string;
  /** Bypass the server cache and force a fresh LLM triage (re-triage button). */
  force?: boolean;
}) {
  const res = await apiFetch(`${BASE}/api/agent/triage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Triage scoring failed");
  return res.json();
}

/**
 * Triage a single email with exponential backoff on 429 rate-limit responses.
 * Retries up to maxRetries times, doubling the delay each attempt.
 */
async function triageWithRetry(
  payload: {
    email_id: string;
    sender: string;
    subject: string;
    body: string;
    received_at: string;
  },
  maxRetries = 4,
): Promise<unknown> {
  let delay = 2000; // start at 2s
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const res = await apiFetch(`${BASE}/api/agent/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.status === 429) {
      // Respect Retry-After header if provided, otherwise exponential backoff
      const retryAfter = parseInt(res.headers.get("Retry-After") || "0", 10);
      const wait = retryAfter > 0 ? retryAfter * 1000 : delay;
      console.warn(
        `[triage] 429 rate-limited for ${payload.email_id}, waiting ${wait}ms (attempt ${attempt + 1}/${maxRetries})`,
      );
      if (attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, wait));
        delay = Math.min(delay * 2, 30000); // cap at 30s
        continue;
      }
      return null; // exhausted retries → fallback handles it
    }

    if (res.ok) return res.json();
    return null; // non-429 error → fallback handles it
  }
  return null;
}

/**
 * Score many emails — fans out to /api/agent/triage in parallel (capped at 2
 * concurrent) with exponential backoff on 429 so we don't hammer Azure OpenAI.
 * Falls back to the fast deterministic /api/triage/batch for any that fail.
 */
export async function triageEmailsBatch(
  payloads: Array<{
    email_id: string;
    sender: string;
    subject: string;
    body: string;
    received_at: string;
  }>,
) {
  if (payloads.length === 0) return [];

  // Low concurrency — Azure OpenAI TPM limits hit fast with 5+ parallel calls.
  const CONCURRENCY = 2;
  const results: unknown[] = new Array(payloads.length);

  // Process in windows of CONCURRENCY to avoid hammering the LLM.
  for (let i = 0; i < payloads.length; i += CONCURRENCY) {
    const chunk = payloads.slice(i, i + CONCURRENCY);
    const settled = await Promise.allSettled(
      chunk.map((p) => triageWithRetry(p)),
    );
    settled.forEach((s, j) => {
      results[i + j] = s.status === "fulfilled" ? s.value : null;
    });
  }

  // Any nulls (agent failures / exhausted retries) fall back to deterministic triage.
  const failedPayloads = payloads.filter((_, i) => !results[i]);
  if (failedPayloads.length > 0) {
    console.warn(
      `[triage] ${failedPayloads.length} emails falling back to deterministic triage`,
    );
    try {
      const fallback = await apiFetch(`${BASE}/api/triage/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(failedPayloads),
      });
      if (fallback.ok) {
        const fallbackData = await fallback.json();
        let fi = 0;
        results.forEach((r, i) => {
          if (!r) results[i] = fallbackData[fi++];
        });
      }
    } catch {
      /* ignore fallback errors */
    }
  }

  return results;
}

export async function extractCommitments(
  maskedText: string,
  threadSummary = "",
  emailId?: string,
) {
  const res = await apiFetch(`${BASE}/api/commitments/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      masked_email_text: maskedText,
      thread_summary: threadSummary,
      email_id: emailId,
    }),
  });
  if (!res.ok) throw new Error("Commitment extraction failed");
  return res.json();
}

export async function confirmCommitments(
  emailId: string,
  commitments: CommitmentItem[],
) {
  const res = await apiFetch(`${BASE}/api/commitments/confirm`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Approval-Token":
        process.env.NEXT_PUBLIC_APPROVAL_TOKEN || "secret-approval-token",
    },
    body: JSON.stringify({ email_id: emailId, commitments }),
  });
  if (!res.ok) {
    let message = "Confirmation failed";
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
  const res = await apiFetch(`${BASE}/api/rag/retrieve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email_text: text }),
  });
  if (!res.ok) throw new Error("RAG retrieval failed");
  return res.json();
}

export async function generateDraftPrompt(text: string) {
  const res = await apiFetch(`${BASE}/api/rag/inject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email_text: text }),
  });
  if (!res.ok) throw new Error("Draft generation prompt inject failed");
  return res.json();
}

export async function generateEmailDraft(
  text: string,
  style: string,
  sender?: string,
  subject?: string,
  currentUserEmail?: string,
) {
  const res = await apiFetch(`${BASE}/api/rag/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email_text: text,
      style: style,
      sender: sender,
      subject: subject,
      // Let the backend personalise the sign-off with the actual logged-in user.
      current_user_email: currentUserEmail,
    }),
  });
  if (!res.ok) throw new Error("Email draft generation failed");
  return res.json();
}

/** Fetch attachment metadata for an email. */
export async function fetchAttachments(emailId: string) {
  const res = await apiFetch(`${BASE}/api/emails/${encodeURIComponent(emailId)}/attachments`);
  if (!res.ok) throw new Error("Failed to fetch attachments");
  return res.json();
}

/** Trigger a browser download of an email attachment. */
export function downloadAttachment(
  emailId: string,
  attachmentId: string,
  filename: string,
): void {
  const url = `${BASE}/api/emails/${encodeURIComponent(emailId)}/attachments/${encodeURIComponent(attachmentId)}?filename=${encodeURIComponent(filename)}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/** Check if a new email has arrived — returns latest email id + received_at. */
export async function pollNewEmail(): Promise<{
  has_new: boolean;
  latest_id: string | null;
  received_at: string | null;
  subject?: string;
}> {
  try {
    const res = await apiFetch(`${BASE}/api/inbox/poll`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return { has_new: false, latest_id: null, received_at: null };
    return await res.json();
  } catch {
    return { has_new: false, latest_id: null, received_at: null };
  }
}

/** Triage up to 10 emails in one batch call — Redis → DB → LLM (3-level cache). */
export async function* triagePageStream(requests: Array<{
  email_id: string;
  sender: string;
  subject: string;
  body: string;
  received_at?: string;
}>) {
  const res = await apiFetch(`${BASE}/api/agent/triage-page-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requests),
  });
  if (!res.ok) throw new Error("Failed to start triage stream");
  if (!res.body) throw new Error("No response body for stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data.trim()) {
            yield JSON.parse(data);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function triagePageBatch(
  payloads: Array<{
    email_id: string;
    sender: string;
    subject: string;
    body: string;
    received_at: string;
  }>,
): Promise<unknown[]> {
  if (payloads.length === 0) return [];
  try {
    const res = await apiFetch(`${BASE}/api/agent/triage-page`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloads),
    });
    if (res.ok) return res.json();
  } catch {
    /* fall through to per-email fallback */
  }
  // Fallback: individual calls with retry
  return triageEmailsBatch(payloads);
}

export async function fetchCalendar(days = 7) {
  try {
    const res = await apiFetch(`${BASE}/api/calendar?days=${days}`);
    if (!res.ok) return []; // Gracefully handle calendar fetch failures
    return res.json();
  } catch (err) {
    console.error("Calendar fetch failed:", err);
    return []; // Return empty array on error
  }
}

export async function createCalendarEvent(payload: {
  title: string;
  start_time: string;
  end_time?: string;
  description?: string;
  email_id?: string;
}) {
  const res = await apiFetch(`${BASE}/api/calendar/event`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create calendar event");
  return res.json();
}

export async function fetchTasks(limit = 20) {
  try {
    const res = await apiFetch(`${BASE}/api/tasks?limit=${limit}`);
    if (!res.ok) return []; // Gracefully handle tasks fetch failures
    return res.json();
  } catch (err) {
    console.error("Tasks fetch failed:", err);
    return []; // Return empty array on error
  }
}

export async function createTask(title: string) {
  const res = await apiFetch(`${BASE}/api/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("Failed to create task");
  return res.json();
}

export async function ingestEmail(payload: Record<string, unknown>) {
  const res = await apiFetch(`${BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.status === 429) {
    throw new Error("Rate limit exceeded. Please try again in 1 minute.");
  }
  if (!res.ok) throw new Error("Ingest failed");
  return res.json();
}

export async function fetchEmails(limit = 10) {
  const res = await apiFetch(`${BASE}/api/emails?limit=${limit}`);
  if (!res.ok) throw new Error("Emails fetch failed");
  return res.json();
}

export interface MailboxPage {
  emails: Array<Record<string, unknown>>;
  next_page_token: string | null;
  total: number;
}

/** Paginated mailbox listing (50/page) with optional server-side search. */
export async function fetchMailbox(
  folder: string,
  limit = 50,
  pageToken?: string | null,
  query?: string,
): Promise<MailboxPage> {
  const params = new URLSearchParams({ folder, limit: String(limit) });
  if (pageToken) params.set("page_token", pageToken);
  if (query && query.trim()) params.set("q", query.trim());
  const res = await apiFetch(`${BASE}/api/mailbox?${params.toString()}`);
  if (!res.ok) {
    let detail = "";

    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await res.text();
    }

    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export async function fetchSentEmails(limit = 10) {
  const res = await apiFetch(`${BASE}/api/emails/sent?limit=${limit}`);
  if (!res.ok) throw new Error("Sent emails fetch failed");
  return res.json();
}

export async function fetchDraftEmails(limit = 10) {
  const res = await apiFetch(`${BASE}/api/emails/drafts?limit=${limit}`);
  if (!res.ok) throw new Error("Drafts fetch failed");
  return res.json();
}

export async function fetchSpamEmails(limit = 10) {
  const res = await apiFetch(`${BASE}/api/emails/spam?limit=${limit}`);
  if (!res.ok) throw new Error("Spam fetch failed");
  return res.json();
}

export async function fetchTrashEmails(limit = 10) {
  const res = await apiFetch(`${BASE}/api/emails/trash?limit=${limit}`);
  if (!res.ok) throw new Error("Trash fetch failed");
  return res.json();
}

export async function approveAgentDraft(
  emailId: string,
  action: "approve" | "reject" | "edit",
  editedDraft?: string,
  reviewerNote?: string,
) {
  const res = await apiFetch(`${BASE}/api/agent/approve/${emailId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      edited_draft: editedDraft ?? null,
      reviewer_note: reviewerNote ?? null,
    }),
  });
  if (!res.ok) throw new Error("Failed to record approval decision");
  return res.json();
}

export async function sendEmailReply(emailId: string, comment: string) {
  const res = await apiFetch(`${BASE}/api/emails/${emailId}/reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comment }),
  });
  if (!res.ok) throw new Error("Failed to send email reply");
  return res.json();
}

export async function restoreEmailFromTrash(emailId: string) {
  const res = await apiFetch(`${BASE}/api/emails/${emailId}/restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to restore email from trash");
  return res.json();
}

export async function fetchEvaluation() {
  const res = await apiFetch(`${BASE}/api/evaluate`);
  if (!res.ok) throw new Error("Evaluation fetch failed");
  return res.json();
}

export interface LiveMetrics {
  cache: {
    hit_rate: number;
    total_hits: number;
    total_misses: number;
    total_lookups: number;
    per_cache: Record<string, { hits: number; misses: number; entries: number }>;
  };
  latency: {
    overall: { p50: number; p95: number; count: number };
    per_stage: Record<string, { p50: number; p95: number; count: number }>;
  };
  llm: { error_rate: number; errors: number; ok: number; total: number };
  speedup: {
    sequential_ms: number;
    parallel_ms: number;
    sequential_s: number;
    parallel_s: number;
    speedup_x: number;
    time_saved_pct: number;
    measured: boolean;
    runs: number;
  };
  uptime_seconds: number;
  queue_depth: number;
  sla_targets_seconds: { triage: number; enrichment: number };
  timestamp: string;
}

export async function fetchLiveMetrics(): Promise<LiveMetrics> {
  const res = await apiFetch(`${BASE}/api/metrics/live`);
  if (!res.ok) throw new Error("Live metrics fetch failed");
  return res.json();
}

export async function moveEmailToTrash(emailId: string) {
  const res = await apiFetch(`${BASE}/api/emails/${emailId}/trash`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to move email to trash");
  return res.json();
}

async function emailAction(
  emailId: string,
  action: string,
  body?: Record<string, unknown>,
) {
  const res = await apiFetch(`${BASE}/api/emails/${emailId}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let message = `Failed: ${action}`;
    try {
      const d = await res.json();
      if (d?.detail) message = d.detail;
    } catch {}
    throw new Error(message);
  }
  return res.json();
}

export const markEmailRead = (id: string, read: boolean) =>
  emailAction(id, "read", { read });
export const archiveEmail = (id: string) => emailAction(id, "archive");
export const reportSpam = (id: string) => emailAction(id, "spam");
export const forwardEmail = (id: string, to: string, comment: string) =>
  emailAction(id, "forward", { to, comment });
export const replyAllEmail = (id: string, comment: string) =>
  emailAction(id, "reply-all", { comment });

export async function composeEmail(payload: {
  to: string;
  subject: string;
  body: string;
  cc?: string;
  bcc?: string;
}) {
  const res = await apiFetch(`${BASE}/api/emails/compose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to send email");
  return res.json();
}

/** Override an email's triage priority and feed the correction into the triage loop. */
export async function overrideEmailPriority(payload: {
  email_id: string;
  sender: string;
  override_priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'DONE';
  original_priority?: string;
}): Promise<{ ok: boolean; priority: string; persisted: boolean }> {
  const res = await apiFetch(`${BASE}/api/agent/triage/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to override priority');
  return res.json();
}

/** Generate a brand-new email body from a prompt, using Tone DNA + RAG. */
export async function composeDraftWithAI(payload: {
  prompt: string;
  recipient?: string;
  subject?: string;
}): Promise<{ draft: string; precedent_citations: { subject: string; similarity: number }[] }> {
  const res = await apiFetch(`${BASE}/api/rag/compose-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: payload.prompt,
      recipient: payload.recipient || null,
      subject: payload.subject || null,
    }),
  });
  if (!res.ok) {
    let detail = `Failed to generate AI draft (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function loginInitiate() {
  const res = await apiFetch(`${BASE}/api/auth/login-initiate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to initiate login flow");
  return res.json();
}

export async function loginPoll(deviceCode: string) {
  try {
    const res = await apiFetch(`${BASE}/api/auth/login-poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_code: deviceCode }),
    });

    if (!res.ok) {
      let errorMessage = "Polling request failed";
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

    return await res.json();
  } catch (err) {
    throw err;
  }
}

export async function checkAuthStatus(): Promise<AuthStatus> {
  // Fail fast (5s) so the login screen never hangs on a slow/unreachable backend.
  const res = await apiFetch(`${BASE}/api/auth/status`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) throw new Error("Auth status check failed");
  return res.json();
}

/** Full sign-out: invalidates session + quick login, deletes both cookies. */
export async function logoutUser() {
  const res = await apiFetch(`${BASE}/api/auth/logout`, { method: "POST" });
  if (!res.ok) throw new Error("Logout request failed");
  return res.json();
}

/** Session-only sign-out: invalidates mm_session, keeps mm_quick for quick login. */
export async function logoutSession() {
  const res = await apiFetch(`${BASE}/api/auth/logout-session`, { method: "POST" });
  if (!res.ok) throw new Error("Logout session request failed");
  return res.json();
}

/** Explicit quick-login: validates mm_quick cookie and issues a new session. */
export async function quickLogin() {
  const res = await apiFetch(`${BASE}/api/auth/quick-login`, { method: "POST" });
  if (!res.ok) throw new Error("Quick login failed");
  return res.json();
}

export async function microsoftLoginInitiate() {
  const res = await apiFetch(`${BASE}/api/auth/microsoft/login-initiate`, {
    method: "POST",
  });
  if (!res.ok) {
    let message = "Microsoft sign-in failed";
    try {
      const d = await res.json();
      if (d?.detail) message = d.detail;
    } catch {}
    throw new Error(message);
  }
  return await res.json();
}

export async function microsoftLoginPoll(state: string) {
  const res = await apiFetch(`${BASE}/api/auth/microsoft/poll`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!res.ok) {
    let message = "Microsoft sign-in failed";
    try {
      const d = await res.json();
      if (d?.detail) message = d.detail;
    } catch {}
    throw new Error(message);
  }
  return await res.json();
}

export async function googleLoginInitiate(email?: string) {
  const res = await apiFetch(`${BASE}/api/auth/google/login-initiate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    let message = "Google sign-in failed";
    try {
      const data = await res.json();
      if (data?.detail) message = data.detail;
    } catch {
      // keep default
    }
    throw new Error(message);
  }
  return await res.json();
}

export async function googleLoginPoll(state: string) {
  const res = await apiFetch(`${BASE}/api/auth/google/poll`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state }),
  });
  if (!res.ok) {
    let message = "Google sign-in failed";
    try {
      const data = await res.json();
      if (data?.detail) message = data.detail;
    } catch {
      // keep default
    }
    throw new Error(message);
  }
  return await res.json();
}

// ── Account management (v3) ──────────────────────────────────────────────────

export async function fetchAccounts(): Promise<AccountInfo[]> {
  const res = await apiFetch(`${BASE}/api/accounts`);
  if (!res.ok) throw new Error("Failed to fetch accounts");
  return res.json();
}

export async function setDefaultAccount(accountId: string): Promise<void> {
  const res = await apiFetch(`${BASE}/api/accounts/${accountId}/set-default`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to set default account");
}

export async function updateAccountMetadata(
  accountId: string,
  payload: { nickname?: string; color?: string; sync_enabled?: boolean },
): Promise<AccountInfo> {
  const res = await apiFetch(`${BASE}/api/accounts/${accountId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update account");
  return res.json();
}

export async function disconnectAccount(accountId: string): Promise<void> {
  const res = await apiFetch(`${BASE}/api/accounts/${accountId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to disconnect account");
}

// ── Feedback ─────────────────────────────────────────────────────────────────

export interface FeedbackPayload {
  rating: number;
  category: string;
  message: string;
  role?: string | null;
}

export async function submitFeedback(payload: FeedbackPayload): Promise<{ ok: boolean; id: string }> {
  const res = await apiFetch(`${BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to submit feedback");
  return res.json();
}

