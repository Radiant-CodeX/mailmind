import type { Email, Priority } from "../../lib/types";

/* Plain-language names for the four triage levels. The technical names stay
   visible in the five-axis explanation; rows speak like a person would. */
export const PRIORITY_LABEL: Record<Priority, string> = {
  CRITICAL: "Urgent",
  HIGH: "Soon",
  MEDIUM: "Later",
  LOW: "Can wait",
};

export const PRIORITY_ORDER: Record<Priority, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export function priorityOf(email: Email): Priority | null {
  if (email.triage?.priority) return email.triage.priority;
  const s = email.composite_score;
  if (s === undefined || s === null) return null;
  if (s >= 75) return "CRITICAL";
  if (s >= 50) return "HIGH";
  if (s >= 25) return "MEDIUM";
  return "LOW";
}

export const needsYou = (e: Email) => {
  const p = priorityOf(e);
  return p === "CRITICAL" || p === "HIGH";
};

/* Campus categories from the backend's triage (email_type). */
export const CATEGORY_LABEL: Record<string, string> = {
  placement: "Placements",
  exams: "Exams",
  academics: "Academics",
  fees: "Fees",
  administrative: "Admin",
  events: "Events",
  research: "Research",
  campus_life: "Campus life",
  personal: "Personal",
  promotions: "Promotions",
  other: "Other",
};

export const CATEGORY_ORDER = [
  "placement", "exams", "academics", "fees", "administrative",
  "events", "research", "campus_life", "personal", "promotions",
];

export function categoryOf(email: Email): string | null {
  const t = email.triage?.email_type;
  if (!t || t === "uncategorised") return null;
  return CATEGORY_LABEL[t] ? t : null;
}

/* Why this email is where it is: the model's one-line reasoning, else the
   strongest axis explanation. */
export function reasonFor(email: Email): string | null {
  const r = email.triage?.triage_reasoning?.trim();
  if (r && !/deterministic fallback/i.test(r)) return r;
  // Freshness says when it arrived, not why it matters, so it never counts.
  const axes = (email.triage?.axes ?? []).filter((a) => a.axis !== "decay");
  const top = [...axes].sort((a, b) => b.raw_score - a.raw_score)[0];
  if (top && top.raw_score >= 0.5 && top.explanation) return top.explanation;
  return null;
}

export function displayName(email: { sender: string; senderName?: string }): string {
  return email.senderName?.trim() || senderName(email.sender);
}

export function senderName(sender: string): string {
  const m = sender.match(/^\s*"?([^"<]+?)"?\s*</);
  if (m) return m[1].trim();
  const addr = sender.replace(/[<>]/g, "").trim();
  const local = addr.split("@")[0] ?? addr;
  return local
    .replace(/[._-]+/g, " ")
    .replace(/\d+/g, "")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase()) || addr;
}

export function senderAddress(sender: string): string {
  const m = sender.match(/<(.+?)>/);
  return (m ? m[1] : sender).trim();
}

export function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export function isNoReply(sender: string): boolean {
  return /no.?reply|donotreply|do.?not.?reply|mailer.?daemon|postmaster|bounce|notifications?@|alerts?@|automated@/i
    .test(senderAddress(sender));
}

export function shortTime(iso: string, now: number = Date.now()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date(now);
  const sameDay = d.toDateString() === today.toDateString();
  if (sameDay) return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const yesterday = new Date(now - 86_400_000);
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  const diffDays = (now - d.getTime()) / 86_400_000;
  if (diffDays < 6) return d.toLocaleDateString(undefined, { weekday: "short" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function dayBucket(iso: string, now: number = Date.now()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Earlier";
  const today = new Date(now);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === new Date(now - 86_400_000).toDateString()) return "Yesterday";
  if ((now - d.getTime()) / 86_400_000 < 7) return "This week";
  return "Earlier";
}

export function fullDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export function deadlineLabel(iso: string | null): { text: string; overdue: boolean; soon: boolean } | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const now = Date.now();
  const hours = (d.getTime() - now) / 3_600_000;
  const hasTime = !(d.getHours() === 0 && d.getMinutes() === 0) && !/T00:00(:00)?/.test(iso) && /T/.test(iso);
  const date = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  const time = hasTime ? `, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}` : "";
  return { text: `${date}${time}`, overdue: hours < 0, soon: hours >= 0 && hours < 48 };
}

/* Axis names as a person would say them. */
export const AXIS_LABEL: Record<string, { name: string; hint: string }> = {
  deadline: { name: "Deadline", hint: "How close the cut-off is" },
  authority: { name: "Sender", hint: "Who is asking" },
  sentiment: { name: "Tone", hint: "Warnings or escalation" },
  thread_risk: { name: "Stakes", hint: "What you lose by waiting" },
  decay: { name: "Freshness", hint: "How recent it is" },
  action: { name: "Action", hint: "Whether you must do something" },
};
