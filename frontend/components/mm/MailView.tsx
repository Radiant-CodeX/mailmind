"use client";

import React, { useEffect, useState } from "react";
import {
  Archive,
  ArrowLeft,
  CalendarClock,
  Check,
  ChevronDown,
  CircleCheck,
  Download,
  ExternalLink,
  Mail,
  Paperclip,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  TriangleAlert,
  Trash2,
  X,
} from "lucide-react";
import type {
  CalendarEvent,
  ClassificationResult,
  CommitmentItem,
  Email,
  PrecedentItem,
  TriageResult,
} from "../../lib/types";
import type { ToneProfile } from "../../lib/api";
import { approveAgentDraft, downloadAttachment } from "../../lib/api";
import { MessageBody } from "./MessageBody";
import {
  AXIS_LABEL,
  CATEGORY_LABEL,
  PRIORITY_LABEL,
  deadlineLabel,
  fullDate,
  isNoReply,
  reasonFor,
  senderAddress,
  senderName,
  displayName,
} from "./format";
import { Avatar, Button, IconButton, PriorityChip, SectionHead, Tag } from "./ui";

type Style = "standard" | "formal" | "indepth";

export interface MailViewProps {
  email: Email;
  loading: boolean;
  error: string | null;
  showPipeline: boolean;
  classification: ClassificationResult | null;
  triage: TriageResult | null;
  precedents: PrecedentItem[];
  // draft
  draft: string | null;
  setDraft: (v: string) => void;
  generating: boolean;
  generate: (style?: Style) => void;
  sent: boolean;
  setSent: (v: boolean) => void;
  style: Style;
  setStyle: (s: Style) => void;
  sending: boolean;
  send: (text: string) => void;
  tone: ToneProfile | null;
  // commitments
  commitments: CommitmentItem[];
  commitmentsLoading: boolean;
  commitmentsError: string | null;
  confirming: boolean;
  confirmed: boolean;
  toggleCommitment: (id: string) => void;
  confirmCommitments: () => void;
  checkConflict: (deadline: string | null) => CalendarEvent | null;
  // actions
  onClose: () => void;
  onDone?: () => void;
  onArchive?: () => void;
  onTrash?: () => void;
  onStar: () => void;
  onMarkUnread?: () => void;
}

function gmailUrl(email: Email) {
  const parts = email.id.split(":");
  const nativeId = parts.length >= 3 ? parts.slice(2).join(":") : email.id;
  return `https://mail.google.com/mail/u/0/#all/${nativeId}`;
}

function formatBytes(bytes: number) {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ─────────────────────────── Why it's here ─────────────────────────── */

function WhyPanel({ triage, classification, email }: { triage: TriageResult; classification: ClassificationResult | null; email: Email }) {
  const [open, setOpen] = useState(true);
  const reasoning = (triage.triage_reasoning ?? "").trim();
  const rulesOnly = !reasoning || /fallback|LLM unavailable|rule-based|deterministic/i.test(reasoning);
  const reason = reasonFor({ ...email, triage });
  const axes = triage.axes ?? [];
  const cat = triage.email_type && CATEGORY_LABEL[triage.email_type] ? CATEGORY_LABEL[triage.email_type] : classification?.category && CATEGORY_LABEL[classification.category];

  return (
    <section aria-label="Why this email is here" className="rounded-[14px] border border-rule bg-surface">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left cursor-pointer"
      >
        <PriorityChip priority={triage.priority} className="mt-0.5 shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block text-[13.5px] leading-snug text-ink">
            {reason ?? `Ranked ${PRIORITY_LABEL[triage.priority].toLowerCase()} from its deadline, sender and what it asks of you.`}
          </span>
          <span className="mt-1 block text-[12px] text-ink-3">
            {cat ? `${cat}, ` : ""}priority {Math.round(triage.composite_score)} of 100 across five signals
          </span>
        </span>
        <ChevronDown className={`mt-0.5 size-4 shrink-0 text-ink-3 transition-transform duration-200 ${open ? "rotate-180" : ""}`} strokeWidth={1.75} aria-hidden />
      </button>

      {open && (
        <div className="animate-fade-in border-t border-rule px-4 pb-4 pt-3">
          {axes.length === 0 ? (
            <p className="text-[12.5px] text-ink-3">
              The per-signal breakdown is not available for this email; it was sorted from a learned sender preference.
            </p>
          ) : (
            <dl className="grid gap-3">
              {axes.map((a) => {
                const meta = AXIS_LABEL[a.axis] ?? { name: a.axis, hint: "" };
                const pct = Math.round(a.raw_score * 100);
                const strong = a.raw_score >= 0.7;
                return (
                  <div key={a.axis} className="grid grid-cols-[6.5rem_minmax(0,1fr)_2.5rem] items-center gap-x-3 gap-y-0.5">
                    <dt className="text-[12.5px] font-medium text-ink" title={meta.hint}>{meta.name}</dt>
                    <div className="h-1.5 overflow-hidden rounded-full bg-sunk" aria-hidden>
                      <div
                        className={`h-full rounded-full transition-[width] duration-700 ease-out-expo ${strong ? "bg-cobalt" : "bg-ink-3/45"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <dd className="text-right text-[12px] tabular-nums text-ink-3">{pct}</dd>
                    {a.explanation && <dd className="col-start-2 col-end-4 text-[12px] leading-snug text-ink-2">{a.explanation}</dd>}
                  </div>
                );
              })}
            </dl>
          )}
          <div className="mt-3 rounded-lg bg-sunk px-3 py-2 text-[12.5px] leading-snug text-ink-2">
            <p className="flex items-center gap-2 font-medium text-ink">
              <Sparkles className={`size-3.5 shrink-0 ${rulesOnly ? "text-ink-3" : "text-cobalt"}`} strokeWidth={1.75} aria-hidden />
              {rulesOnly ? "Scored by MailMind's built-in campus rules" : "Scored by your AI model"}
            </p>
            <p className="mt-1 text-ink-3">
              {rulesOnly
                ? /your AI model failed/i.test(reasoning)
                  ? reasoning.replace(/^Rule-based fallback:\s*/i, "")
                  : "No AI model answered for this email. Add or check your key in Settings, AI model, for sharper scores."
                : reasoning}
            </p>
          </div>
          {triage.approval_mode === "GATE" && (
            <p className="mt-3 flex items-center gap-2 rounded-lg bg-sunk px-3 py-2 text-[12.5px] text-ink-2">
              <ShieldCheck className="size-4 shrink-0 text-cobalt" strokeWidth={1.75} aria-hidden />
              High-stakes email. Any reply waits for you to read and confirm it.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

/* ─────────────────────────── What you need to do ─────────────────────────── */

function ActionItems(props: Pick<MailViewProps,
  "commitments" | "commitmentsLoading" | "commitmentsError" | "confirming" | "confirmed" | "toggleCommitment" | "confirmCommitments" | "checkConflict">) {
  const { commitments, commitmentsLoading, commitmentsError, confirming, confirmed, toggleCommitment, confirmCommitments, checkConflict } = props;
  const selected = commitments.filter((c) => c.approved).length;

  return (
    <section aria-label="What you need to do" className="rounded-[14px] border border-rule bg-surface p-4">
      <SectionHead
        title="What you need to do"
        meta={commitments.length ? commitments.length : undefined}
      />
      {commitmentsLoading ? (
        <div className="mt-3 space-y-2" aria-label="Finding tasks">
          <span className="mm-skeleton block h-10" />
          <span className="mm-skeleton block h-10 w-4/5" />
        </div>
      ) : commitmentsError ? (
        <p className="mt-2 text-[13px] text-urgent">Could not read tasks from this email. {commitmentsError}</p>
      ) : commitments.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-3">Nothing to do in this email. No deadlines or requests for you.</p>
      ) : (
        <>
          <ul className="mt-3 grid gap-2">
            {commitments.map((c) => {
              const dl = deadlineLabel(c.deadline);
              const clash = c.conflict_badge ? { title: c.conflict_detail || "Something else" } : checkConflict(c.deadline);
              const done = c.confirmed || confirmed;
              return (
                <li key={c.id}>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-xl px-3 py-2.5 transition-colors ${
                      done ? "bg-ok-soft" : c.approved ? "bg-cobalt-soft" : "bg-sunk hover:bg-rule/60"
                    }`}
                  >
                    {done ? (
                      <span className="mt-0.5 inline-flex size-[18px] shrink-0 items-center justify-center rounded-md bg-ok text-surface">
                        <Check className="size-3" strokeWidth={3} aria-hidden />
                      </span>
                    ) : (
                      <input
                        type="checkbox"
                        checked={!!c.approved}
                        onChange={() => toggleCommitment(c.id)}
                        className="mt-0.5 size-[18px] shrink-0 cursor-pointer rounded-md accent-[var(--mm-accent)]"
                      />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13.5px] leading-snug text-ink">{c.commitment}</span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
                        {dl && (
                          <span className={`inline-flex items-center gap-1 ${dl.overdue ? "text-urgent" : dl.soon ? "text-soon" : "text-ink-2"}`}>
                            <CalendarClock className="size-3.5" strokeWidth={1.75} aria-hidden />
                            {dl.overdue ? "Was due " : "Due "}{dl.text}
                          </span>
                        )}
                        {clash && (
                          <span className="inline-flex items-center gap-1 text-urgent">
                            <TriangleAlert className="size-3.5" strokeWidth={1.75} aria-hidden />
                            Clashes with {clash.title}
                          </span>
                        )}
                        {done && c.task_url && (
                          <a href={c.task_url} target="_blank" rel="noopener noreferrer" className="text-cobalt hover:underline">Open task</a>
                        )}
                        {done && c.event_url && (
                          <a href={c.event_url} target="_blank" rel="noopener noreferrer" className="text-cobalt hover:underline">Open event</a>
                        )}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          {!confirmed ? (
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-[12px] text-ink-3">Nothing is added until you confirm.</p>
              <Button variant="primary" size="sm" icon={CalendarClock} loading={confirming} disabled={!selected} onClick={confirmCommitments}>
                Add {selected || ""} to Tasks and Calendar
              </Button>
            </div>
          ) : (
            <p className="mt-3 flex items-center gap-1.5 text-[12.5px] text-ok">
              <CircleCheck className="size-4" strokeWidth={1.75} aria-hidden />
              Added to your Google Tasks and Calendar.
            </p>
          )}
        </>
      )}
    </section>
  );
}

/* ─────────────────────────── Reply ─────────────────────────── */

function toneTraits(tone: ToneProfile | null): string[] {
  if (!tone?.features) return [];
  const f = tone.features;
  const traits: string[] = [];
  if (f.avg_sentence_length) traits.push(f.avg_sentence_length < 13 ? "Short sentences" : f.avg_sentence_length > 21 ? "Longer sentences" : "Medium-length sentences");
  if (typeof f.formality_score === "number") traits.push(f.formality_score > 0.66 ? "Formal" : f.formality_score < 0.34 ? "Casual" : "Polite, not stiff");
  const greet = f.greeting_patterns?.[0];
  if (greet) traits.push(`Opens with "${greet.replace(/[,!.]+$/, "")}"`);
  const sign = f.signoff_patterns?.[0];
  if (sign) traits.push(`Signs off "${sign.replace(/[,!.]+$/, "")}"`);
  return traits.slice(0, 4);
}

const STYLE_LABEL: Record<Style, string> = { standard: "Brief", formal: "Formal", indepth: "Detailed" };

function ReplyCard(props: Pick<MailViewProps,
  "email" | "triage" | "draft" | "setDraft" | "generating" | "generate" | "sent" | "setSent" | "style" | "setStyle" | "sending" | "send" | "tone">) {
  const { email, triage, draft, setDraft, generating, generate, sent, setSent, style, setStyle, sending, send, tone } = props;
  const [confirmingSend, setConfirmingSend] = useState(false);
  const traits = toneTraits(tone);
  const recipient = displayName(email);

  if (isNoReply(email.sender)) {
    return (
      <section aria-label="Reply" className="rounded-[14px] border border-dashed border-rule px-4 py-3.5">
        <p className="text-[13px] text-ink-3">
          This came from a no-reply address, so there is nobody to answer. Act on it through the portal or link it mentions.
        </p>
      </section>
    );
  }

  if (sent) {
    return (
      <section aria-label="Reply" className="rounded-[14px] border border-rule bg-ok-soft px-4 py-3.5">
        <p className="flex items-center gap-2 text-[13.5px] font-medium text-ok">
          <CircleCheck className="size-4" strokeWidth={1.75} aria-hidden />
          Reply sent to {recipient}
        </p>
        <button type="button" onClick={() => setSent(false)} className="mt-1 text-[12.5px] text-ink-2 hover:text-ink hover:underline cursor-pointer">
          See what was sent
        </button>
      </section>
    );
  }

  return (
    <section aria-label="Reply" className="rounded-[14px] border border-rule bg-surface p-4">
      <SectionHead
        title={draft ? "Draft in your voice" : "Reply"}
        meta={draft ? "Waiting for you" : undefined}
        action={
          <div role="radiogroup" aria-label="Reply length" className="inline-flex rounded-full bg-sunk p-0.5">
            {(Object.keys(STYLE_LABEL) as Style[]).map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={style === s}
                onClick={() => { setStyle(s); if (draft) generate(s); }}
                className={`h-7 rounded-full px-2.5 text-[12px] font-medium transition-colors cursor-pointer ${
                  style === s ? "bg-surface text-ink shadow-paper" : "text-ink-3 hover:text-ink"
                }`}
              >
                {STYLE_LABEL[s]}
              </button>
            ))}
          </div>
        }
      />

      {generating ? (
        <div className="mt-3 space-y-2" aria-label="Writing a draft">
          <span className="mm-skeleton block h-3.5 w-2/5" />
          <span className="mm-skeleton block h-3.5" />
          <span className="mm-skeleton block h-3.5 w-11/12" />
          <span className="mm-skeleton block h-3.5 w-3/5" />
        </div>
      ) : !draft ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sunk px-3.5 py-3">
          <p className="text-[13px] text-ink-2">
            Draft a reply to {recipient} in your own voice. You read and send it yourself.
          </p>
          <Button variant="primary" size="sm" icon={Sparkles} onClick={() => generate(style)}>
            Draft reply
          </Button>
        </div>
      ) : confirmingSend ? (
        <div className="animate-fade-in mt-3 space-y-3">
          <div className="rounded-xl bg-sunk px-3.5 py-3 text-[13px] text-ink-2">
            Send this reply to <span className="font-medium text-ink">{senderAddress(email.sender)}</span>?
            {triage?.approval_mode === "GATE" && " This is a high-stakes email, so check names, dates and numbers once more."}
          </div>
          <div className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-xl border border-rule px-3.5 py-3 text-[13.5px] leading-relaxed text-ink mm-scroll">
            {draft}
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setConfirmingSend(false)}>Keep editing</Button>
            <Button
              variant="primary"
              size="sm"
              icon={Send}
              loading={sending}
              onClick={() => {
                approveAgentDraft(email.id, "approve", draft).catch(() => {});
                send(draft);
              }}
            >
              Send now
            </Button>
          </div>
        </div>
      ) : (
        <div className="animate-fade-in mt-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={8}
            aria-label="Draft reply"
            className="mm-scroll w-full resize-y rounded-xl border border-rule bg-surface px-3.5 py-3 text-[13.5px] leading-relaxed text-ink focus:border-cobalt focus:outline-none"
          />
          {traits.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5" aria-label="What MailMind matched from your sent mail">
              {traits.map((t) => <Tag key={t}>{t}</Tag>)}
            </div>
          )}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-1.5 text-[12px] text-ink-3">
              <ShieldCheck className="size-3.5" strokeWidth={1.75} aria-hidden />
              Personal details were hidden from the AI while writing this.
            </p>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" icon={RotateCcw} onClick={() => generate(style)}>Rewrite</Button>
              <Button variant="primary" size="sm" icon={Send} onClick={() => setConfirmingSend(true)}>Review and send</Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

/* ─────────────────────────── Sheet ─────────────────────────── */

export function MailView(props: MailViewProps) {
  const { email, loading, error, showPipeline, triage, classification, precedents, onClose, onDone, onArchive, onTrash, onStar, onMarkUnread } = props;
  const name = displayName(email);
  const attachments = email.attachments ?? [];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT")) return;
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <article aria-label={email.subject || "Email"} className="flex h-full min-w-0 flex-col bg-bg">
      <div className="flex h-12 shrink-0 items-center gap-1 border-b border-rule bg-surface px-2">
        <IconButton icon={ArrowLeft} label="Back to list" onClick={onClose} className="lg:hidden" />
        <IconButton icon={X} label="Close (Esc)" onClick={onClose} className="hidden lg:inline-flex" />
        <div className="mx-1 h-4 w-px bg-rule" />
        {onDone && (
          <Button variant="ghost" size="sm" icon={CircleCheck} onClick={onDone}>Done</Button>
        )}
        {onArchive && <IconButton icon={Archive} label="Archive" onClick={onArchive} />}
        <IconButton icon={Star} label={email.isStarred ? "Unstar" : "Star"} active={email.isStarred} onClick={onStar} />
        {onMarkUnread && <IconButton icon={Mail} label="Mark unread" onClick={onMarkUnread} />}
        {onTrash && <IconButton icon={Trash2} label="Delete" tone="danger" onClick={onTrash} />}
        <a
          href={gmailUrl(email)}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[12.5px] text-ink-3 transition-colors hover:bg-hover hover:text-ink"
        >
          Open in Gmail
          <ExternalLink className="size-3.5" strokeWidth={1.75} aria-hidden />
        </a>
      </div>

      <div className="mm-scroll min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto grid max-w-[46rem] gap-4 px-4 pb-16 pt-5 md:px-8">
          <header>
            <h2 className="text-balance text-[21px] font-semibold leading-tight tracking-[-0.015em] text-ink">
              {email.subject || "(no subject)"}
            </h2>
            <div className="mt-3 flex items-center gap-3">
              <Avatar name={name} size={36} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-medium text-ink">{name}</p>
                <p className="truncate text-[12.5px] text-ink-3">{senderAddress(email.sender)}</p>
              </div>
              <time className="shrink-0 text-[12.5px] text-ink-3" dateTime={email.received_at} suppressHydrationWarning>
                {fullDate(email.received_at)}
              </time>
            </div>
          </header>

          {error && (
            <p className="rounded-xl bg-urgent-soft px-3.5 py-2.5 text-[13px] text-urgent">{error}</p>
          )}

          {showPipeline && (loading && !triage ? (
            <span className="mm-skeleton block h-16 rounded-[14px]" aria-label="Reading this email" />
          ) : triage ? (
            <WhyPanel triage={triage} classification={classification} email={email} />
          ) : null)}

          <div className="overflow-hidden rounded-[14px] border border-rule bg-white px-5 py-4 shadow-paper">
            <MessageBody html={email.html_body} text={email.body} attachments={attachments} emailId={email.id} />
            {attachments.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 border-t border-[#e2e3de] pt-3">
                {attachments.map((a) => (
                  <button
                    key={a.attachment_id}
                    type="button"
                    onClick={() => downloadAttachment(email.id, a.attachment_id, a.filename)}
                    className="inline-flex max-w-[16rem] items-center gap-2 rounded-lg border border-[#e2e3de] px-2.5 py-1.5 text-left text-[12.5px] text-[#111418] transition-colors hover:bg-[#f7f7f4] cursor-pointer"
                  >
                    <Paperclip className="size-3.5 shrink-0 text-[#676d75]" strokeWidth={1.75} aria-hidden />
                    <span className="truncate">{a.filename}</span>
                    <span className="shrink-0 text-[#676d75]">{formatBytes(a.size)}</span>
                    <Download className="size-3.5 shrink-0 text-[#676d75]" strokeWidth={1.75} aria-hidden />
                  </button>
                ))}
              </div>
            )}
          </div>

          {showPipeline && (
            <>
              <ActionItems {...props} />
              <ReplyCard {...props} />
              {precedents.length > 0 && (
                <section aria-label="Similar emails you handled" className="px-1">
                  <p className="text-[12.5px] font-medium text-ink-3">How you handled similar emails</p>
                  <ul className="mt-1.5 grid gap-1">
                    {precedents.slice(0, 3).map((p) => (
                      <li key={p.email_id} className="truncate text-[12.5px] text-ink-2">
                        {p.subject} <span className="text-ink-3">{Math.round(p.similarity_score * 100)}% alike</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </article>
  );
}
