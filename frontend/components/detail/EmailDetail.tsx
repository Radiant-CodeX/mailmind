"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Email,
  ClassificationResult,
  TriageResult,
  PrecedentItem,
  CommitmentItem as TypeCommitment,
  CalendarEvent,
  Attachment,
} from "../../lib/types";
import { TriageExplainer } from "../triage/TriageExplainer";
import { PrecedentList } from "./PrecedentList";
import { DraftPanel } from "./DraftPanel";
import { ThreadView } from "./ThreadView";
import { CommitmentGate } from "../commitments/CommitmentGate";
import { LoadingSpinner } from "../shared/LoadingSpinner";
import { ErrorBanner } from "../shared/ErrorBanner";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileIcon(mime: string): string {
  if (mime.startsWith("image/")) return "🖼️";
  if (mime.includes("pdf")) return "📄";
  if (mime.includes("word") || mime.includes("document")) return "📝";
  if (mime.includes("sheet") || mime.includes("excel")) return "📊";
  if (mime.includes("zip") || mime.includes("compressed")) return "🗜️";
  return "📎";
}

function getOriginalUrl(email: Email, provider: "google" | "microsoft"): string | null {
  // v3 id format: "provider:account_id:native_id" — extract native id
  const parts = email.id.split(":");
  const nativeId = parts.length >= 3 ? parts.slice(2).join(":") : email.id;
  if (provider === "google") {
    return `https://mail.google.com/mail/u/0/#inbox/${nativeId}`;
  }
  if (provider === "microsoft") {
    return `https://outlook.live.com/mail/0/`;
  }
  return null;
}

function senderInitials(sender: string): string {
  const name = sender.replace(/<.*?>/, "").trim();
  const parts = name.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function senderName(sender: string): string {
  const match = sender.match(/^(.+?)\s*</);
  if (match) return match[1].trim();
  return sender.replace(/<.*?>/, "").trim() || sender;
}

function senderEmail(sender: string): string {
  const match = sender.match(/<(.+?)>/);
  return match ? match[1] : sender;
}

function isNoReply(sender: string): boolean {
  const addr = senderEmail(sender).toLowerCase();
  return /no.?reply|noreply|do.?not.?reply|donotreply|mailer.?daemon|postmaster|bounce|notifications?@|alerts?@|automated@/.test(addr);
}

// ─── HTML body renderer (srcDoc + DOMPurify) ─────────────────────────────────

function buildSrcDoc(
  html: string,
  attachments: Attachment[] | undefined,
  emailId: string
): string {
  if (typeof window === "undefined") return html;

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const DOMPurify = require("dompurify");

  const clean = DOMPurify.sanitize(html, {
    FORCE_BODY: true,
    ADD_ATTR: [
      "target", "rel", "width", "height", "bgcolor", "align",
      "valign", "cellpadding", "cellspacing", "border",
    ],
    FORBID_TAGS: ["script", "object", "embed", "form", "input", "button", "textarea", "select"],
    FORBID_ATTR: ["action", "formaction", "onerror", "onload", "onclick", "onmouseover"],
  });

  const doc = new DOMParser().parseFromString(clean, "text/html");

  // Links → new tab
  doc.querySelectorAll("a").forEach((a) => {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
    if (/^javascript:/i.test(a.getAttribute("href") || "")) a.removeAttribute("href");
  });

  // CID → attachment endpoint
  if (attachments && attachments.length > 0) {
    const cidMap: Record<string, string> = {};
    attachments.forEach((att) => {
      cidMap[att.filename] = `/api/emails/${emailId}/attachments/${att.attachment_id}`;
      cidMap[att.attachment_id] = `/api/emails/${emailId}/attachments/${att.attachment_id}`;
    });
    doc.querySelectorAll("img").forEach((img) => {
      const src = img.getAttribute("src") || "";
      const m = src.match(/^cid:(.+)$/i);
      if (m) {
        const mapped = cidMap[m[1]] || cidMap[m[1].split("@")[0]];
        if (mapped) img.setAttribute("src", mapped);
        else { img.removeAttribute("src"); img.setAttribute("alt", "[embedded image]"); }
      }

      // Block unknown protocols (javascript:, file:, etc.)
      img.removeAttribute("src");
      img.setAttribute("alt", img.getAttribute("alt") || "[image]");
    });
  }

  // Block tracking pixels — only https: and data: and /api/ allowed
  doc.querySelectorAll("img").forEach((img) => {
    const src = img.getAttribute("src") || "";
    if (!src.startsWith("data:") && !src.startsWith("https://") && !src.startsWith("/api/")) {
      img.removeAttribute("src");
      img.setAttribute("alt", img.getAttribute("alt") || "[image]");
    }
  });

  // Quoted-text collapse
  doc.querySelectorAll("blockquote").forEach((bq) => {
    const txt = bq.textContent || "";
    if (/^on .+ wrote:$/i.test(txt.trim())) {
      const details = doc.createElement("details");
      const summary = doc.createElement("summary");
      summary.textContent = "Show quoted text";
      details.appendChild(summary);
      details.appendChild(bq.cloneNode(true));
      bq.parentNode?.replaceChild(details, bq);
    }
  });

  // Inject Gmail-parity styles
  const style = doc.createElement("style");
  style.textContent = `
    * { outline: none !important; box-sizing: border-box; border: none; }
    table, td, th { border: revert; }
    html, body {
      margin: 0; padding: 16px 20px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 14px; line-height: 1.6;
      color: #202124; background: #ffffff;
      word-break: break-word; overflow-wrap: break-word;
      -webkit-text-size-adjust: 100%;
    }
    p { margin: 0 0 12px 0; }
    a { color: #1a73e8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    a:visited { color: #681da8; }
    h1,h2,h3,h4,h5,h6 { margin: 16px 0 12px; font-weight: 500; line-height: 1.4; }
    h1 { font-size: 24px; } h2 { font-size: 20px; } h3 { font-size: 18px; }
    img { max-width: 100%; height: auto; }
    table { border-collapse: collapse; max-width: 100%; }
    td, th { border: 1px solid #dadce0; padding: 10px 12px; font-size: 13px; }
    th { background: #f8f9fa; font-weight: 600; }
    blockquote { border-left: 3px solid #1a73e8; margin: 12px 0; padding: 0 0 0 16px; color: #5f6368; }
    pre, code { font-family: "Monaco","Consolas","Courier New",monospace; font-size: 12px; }
    code { background: #f1f3f4; padding: 2px 6px; border-radius: 3px; }
    pre { background: #f1f3f4; padding: 12px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }
    pre code { background: none; padding: 0; }
    ul, ol { margin: 12px 0; padding-left: 24px; }
    li { margin: 6px 0; }
    hr { border: none; border-top: 1px solid #dadce0; margin: 16px 0; }
    details { margin: 12px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; }
    summary { cursor: pointer; font-weight: 500; color: #1a73e8; user-select: none; padding: 4px 0; }
    strong, b { font-weight: 600; }
    .center, [align="center"] { text-align: center; }
    .right, [align="right"] { text-align: right; }
  `;
  if (doc.head.firstChild) doc.head.insertBefore(style, doc.head.firstChild);
  else doc.head.appendChild(style);

  return doc.documentElement.outerHTML;
}

// ─── Email body components ────────────────────────────────────────────────────

function EmailBodyHtml({
  html,
  attachments,
  emailId,
}: {
  html: string;
  attachments?: Attachment[];
  emailId: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(400);

  const srcDoc = useMemo(
    () => buildSrcDoc(html, attachments, emailId),
    [html, attachments, emailId]
  );

  const handleLoad = () => {
    const body = iframeRef.current?.contentDocument?.body;
    if (body) setHeight(Math.max(200, body.scrollHeight + 40));
  };

  // Re-measure after fonts/images settle
  useEffect(() => {
    const t = setTimeout(handleLoad, 300);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [srcDoc]);

  return (
    <iframe
      ref={iframeRef}
      srcDoc={srcDoc}
      onLoad={handleLoad}
      sandbox="allow-popups allow-popups-to-escape-sandbox"
      style={{ width: "100%", height: `${height}px`, border: "none", display: "block" }}
      title="Email content"
    />
  );
}

function EmailBodyPlain({ text }: { text: string }) {
  return (
    <div className="px-5 py-4">
      <pre className="text-sm text-base-content whitespace-pre-wrap leading-relaxed font-sans break-words">
        {text}
      </pre>
    </div>
  );
}

// ─── Attachment strip ─────────────────────────────────────────────────────────

function AttachmentStrip({
  emailId,
  attachments,
}: {
  emailId: string;
  attachments: Attachment[];
}) {
  const download = (attId: string, filename: string) => {
    import("../../lib/api").then(({ downloadAttachment }) =>
      downloadAttachment(emailId, attId, filename)
    );
  };

  return (
    <div className="bg-base-100 border-t border-base-200 px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-3.5 h-3.5 text-base-content/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
        </svg>
        <span className="text-[10px] font-bold text-base-content/60 uppercase tracking-widest">
          {attachments.length} Attachment{attachments.length !== 1 ? "s" : ""}
        </span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-0.5 custom-scrollbar">
        {attachments.map((att) => (
          <button
            key={att.attachment_id}
            onClick={() => download(att.attachment_id, att.filename)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-base-300 bg-base-200/50 hover:bg-base-200 hover:border-primary/50 transition-all cursor-pointer shrink-0 group min-w-0"
            title={`Download ${att.filename}`}
          >
            <span className="text-sm shrink-0">{fileIcon(att.mime_type)}</span>
            <div className="text-left min-w-0">
              <p className="text-[11px] font-semibold text-base-content max-w-[110px] truncate">
                {att.filename}
              </p>
              <p className="text-[9px] text-base-content/60">{formatBytes(att.size)}</p>
            </div>
            <svg
              className="w-3 h-3 text-base-content/60 group-hover:text-primary shrink-0"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Main EmailDetail panel ───────────────────────────────────────────────────

interface EmailDetailProps {
  email: Email | null;
  loading: boolean;
  error: string | null;
  classification: ClassificationResult | null;
  triageResult: TriageResult | null;
  precedents: PrecedentItem[];
  aiDraft: string | null;
  setAiDraft: (val: string) => void;
  isGeneratingDraft: boolean;
  generateDraft: (style?: "standard" | "formal" | "indepth") => void;
  isDraftApproved: boolean;
  setIsDraftApproved: (val: boolean) => void;
  activeStyle: "standard" | "formal" | "indepth";
  setActiveStyle: (style: "standard" | "formal" | "indepth") => void;
  isSendingDraft: boolean;
  sendDraft: (comment: string) => void;
  commitments: TypeCommitment[];
  commitmentsLoading: boolean;
  commitmentsError: string | null;
  confirmingCommitments: boolean;
  confirmedCommitments: boolean;
  taskUrls: string[];
  eventUrls: string[];
  toggleCommitment: (id: string) => void;
  confirmSelectedCommitments: () => void;
  checkConflict: (deadline: string | null) => CalendarEvent | null;
  onClose: () => void;
  attachments?: Attachment[];
  showPipeline?: boolean;
  provider?: "google" | "microsoft";
}

export function EmailDetail({
  email,
  loading,
  error,
  classification,
  triageResult,
  precedents,
  aiDraft,
  setAiDraft,
  isGeneratingDraft,
  generateDraft,
  isDraftApproved,
  setIsDraftApproved,
  activeStyle,
  setActiveStyle,
  isSendingDraft,
  sendDraft,
  commitments,
  commitmentsLoading,
  commitmentsError,
  confirmingCommitments,
  confirmedCommitments,
  taskUrls,
  eventUrls,
  toggleCommitment,
  confirmSelectedCommitments,
  checkConflict,
  onClose,
  attachments: attachmentsProp,
  showPipeline = true,
  provider = "google",
}: EmailDetailProps) {
  const [isDraftExpanded, setIsDraftExpanded] = useState(false);
  const [isCommitmentsExpanded, setIsCommitmentsExpanded] = useState(false);
  const [isTriageExpanded, setIsTriageExpanded] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-base-300 p-8 text-center">
        <LoadingSpinner
          message="Analyzing email context, extracting action items, and prioritizing for review..."
          size="lg"
        />
      </div>
    );
  }

  if (!email) return null;

  const isHtml = !!(email.html_body && email.html_body.trim().length > 0);
  const originalUrl = getOriginalUrl(email, provider);
  const initials = senderInitials(email.sender);
  const name = senderName(email.sender);
  const emailAddr = senderEmail(email.sender);
  const hasAttachments = email.attachments && email.attachments.length > 0;
  const noReply = isNoReply(email.sender);

  return (
    <div className="h-full flex flex-col bg-base-300 overflow-hidden">

      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <div className="h-11 border-b border-base-200 px-4 flex items-center justify-between bg-base-100 shrink-0 gap-3">
        {/* Subject */}
        <h2 className="text-[13px] font-bold text-base-content truncate flex-1 min-w-0 tracking-tight">
          {email.subject || "(no subject)"}
        </h2>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Open in Gmail / Outlook */}
          {originalUrl && (
            <a
              href={originalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold text-base-content/60 hover:text-base-content hover:bg-base-200 transition-all"
              title={`Open in ${provider === "google" ? "Gmail" : "Outlook"}`}
            >
              {provider === "google" ? (
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20 4H4C2.9 4 2 4.9 2 6v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                  <rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M2 8h20M9 8v12" stroke="currentColor" strokeWidth="1.5"/>
                </svg>
              )}
              Open in {provider === "google" ? "Gmail" : "Outlook"}
            </a>
          )}

          {/* Divider */}
          <div className="w-px h-4 bg-base-200" />

          {/* Close */}
          <button
            onClick={onClose}
            className="flex items-center justify-center w-7 h-7 rounded-lg text-base-content/60 hover:text-base-content hover:bg-base-200 transition-all cursor-pointer"
            title="Close (Esc)"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Scrollable content ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">

        {error && (
          <div className="px-4 pt-4">
            <ErrorBanner message={error} />
          </div>
        )}

        {/* ── Sender metadata row ───────────────────────────────────────── */}
        <div className="px-4 py-3 border-b border-base-200 bg-base-100 flex items-center gap-3">
          {/* Avatar */}
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0 shadow-sm"
            style={{ background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" }}
          >
            {initials}
          </div>

          {/* Name / email / date */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-bold text-base-content truncate">{name}</span>
              {isHtml ? (
                <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-500 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full shrink-0">
                  HTML
                </span>
              ) : (
                <span className="text-[9px] font-bold uppercase tracking-widest text-base-content/60 bg-base-200 border border-base-300 px-1.5 py-0.5 rounded-full shrink-0">
                  Text
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[11px] text-base-content/60 truncate">{emailAddr}</span>
              <span className="text-base-content/20">·</span>
              <span className="text-[11px] text-base-content/60 shrink-0" suppressHydrationWarning>
                {new Date(email.received_at).toLocaleString(undefined, {
                  month: "short", day: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>
          </div>

          {/* Triage circle */}
          {triageResult && (
            <div className="relative group shrink-0">
              <div className="relative w-11 h-11 flex items-center justify-center cursor-help">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                  <circle className="text-base-content/40" strokeWidth="3" stroke="currentColor" fill="none" cx="18" cy="18" r="16" />
                  <circle
                    className={triageResult.composite_score >= 75 ? "text-red-500" : triageResult.composite_score >= 50 ? "text-orange-500" : triageResult.composite_score >= 25 ? "text-amber-500" : "text-slate-400"}
                    strokeDasharray="100, 100"
                    strokeDashoffset={100 - triageResult.composite_score}
                    strokeWidth="3" strokeLinecap="round"
                    stroke="currentColor" fill="none" cx="18" cy="18" r="16"
                  />
                </svg>
                <div className="absolute flex flex-col items-center justify-center">
                  <span className="text-[11px] font-black text-base-content font-mono leading-none">
                    {Math.round(triageResult.composite_score)}
                  </span>
                  <span className="text-[6px] text-base-content/60 font-bold tracking-wider uppercase leading-none mt-0.5">
                    Score
                  </span>
                </div>
              </div>
              <div className="absolute right-0 top-[48px] hidden group-hover:block bg-base-100 border border-base-300 rounded-xl shadow-2xl p-4 w-[340px] z-50 animate-fade-in text-left">
                <TriageExplainer triage={triageResult} classification={classification} />
              </div>
            </div>
          )}
        </div>

        {/* ── Email body — flush white, no wrapper borders ──────────────── */}
        <div className="bg-white w-full">
          {isHtml ? (
            <EmailBodyHtml
              html={email.html_body!}
              attachments={email.attachments}
              emailId={email.id}
            />
          ) : (
            <EmailBodyPlain text={email.body} />
          )}
        </div>

        {/* Thin rule below email body */}
        <div className="h-px bg-base-200" />

        {/* ── Attachment strip ──────────────────────────────────────────── */}
        {hasAttachments && (
          <AttachmentStrip emailId={email.id} attachments={email.attachments!} />
        )}

        {/* ── AI pipeline accordions ────────────────────────────────────── */}
        {showPipeline && (
          <div className="divide-y divide-base-200">

            {/* Triage Breakdown — full 5-axis explainability (visible, not hover-only) */}
            {triageResult && (
              <div className="bg-base-100">
                <button
                  onClick={() => setIsTriageExpanded(!isTriageExpanded)}
                  className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-base-200/30 transition-colors text-left cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-lg bg-purple-500/10 text-purple-500 border border-purple-500/20 flex items-center justify-center shrink-0">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[11px] font-bold text-base-content uppercase tracking-widest">Triage Breakdown</p>
                      <p className="text-[10px] text-base-content/60 mt-0.5">
                        Composite {Math.round(triageResult.composite_score)} · {triageResult.axes?.length ?? 0} scoring axes
                      </p>
                    </div>
                  </div>
                  <svg className={`w-4 h-4 text-base-content/60 transition-transform duration-200 ${isTriageExpanded ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {isTriageExpanded && (
                  <div className="border-t border-base-200 bg-base-300/20 px-4 py-4">
                    <TriageExplainer triage={triageResult} classification={classification} />
                  </div>
                )}
              </div>
            )}

            {/* AI Draft */}
            <div className="bg-base-100">
              {noReply ? (
                /* No-reply sender — draft disabled */
                <div className="w-full flex items-center justify-between px-4 py-3.5 opacity-50 cursor-not-allowed select-none">
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-lg bg-base-200 border border-base-300 flex items-center justify-center shrink-0">
                      <svg className="w-3.5 h-3.5 text-base-content/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[11px] font-bold text-base-content/60 uppercase tracking-widest">AI Co-Pilot Draft</p>
                      <p className="text-[10px] text-base-content/60 mt-0.5">No-reply address — replies not supported</p>
                    </div>
                  </div>
                </div>
              ) : (
                /* Normal sender — draft enabled */
                <>
                  <button
                    onClick={() => setIsDraftExpanded(!isDraftExpanded)}
                    className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-base-200/30 transition-colors text-left cursor-pointer"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-lg bg-blue-500/10 text-blue-500 border border-blue-500/20 flex items-center justify-center shrink-0">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-[11px] font-bold text-base-content uppercase tracking-widest">AI Co-Pilot Draft</p>
                        <p className="text-[10px] text-base-content/60 mt-0.5">
                          {isDraftApproved ? "✓ Draft sent" : aiDraft ? "Draft ready — click to review" : "Generate a smart reply"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {aiDraft && !isDraftApproved && (
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
                      )}
                      <svg className={`w-4 h-4 text-base-content/60 transition-transform duration-200 ${isDraftExpanded ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  {isDraftExpanded && (
                    <div className="border-t border-base-200 bg-base-300/20 px-4 py-4">
                      <DraftPanel
                        draft={aiDraft} setDraft={setAiDraft}
                        isGenerating={isGeneratingDraft} onGenerate={generateDraft}
                        isApproved={isDraftApproved} setIsApproved={setIsDraftApproved}
                        activeStyle={activeStyle} setActiveStyle={setActiveStyle}
                        isSending={isSendingDraft} onSend={sendDraft}
                        approvalMode={triageResult?.approval_mode}
                        triageScore={triageResult?.composite_score}
                        triageReasons={triageResult?.axes
                          ?.filter((a: { raw_score: number }) => a.raw_score >= 0.7)
                          ?.map((a: { axis: string; explanation: string }) => `${a.axis}: ${a.explanation}`)
                          ?? undefined}
                        emailId={email.id}
                      />
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Commitment Gate */}
            <div className="bg-base-100">
              <button
                onClick={() => setIsCommitmentsExpanded(!isCommitmentsExpanded)}
                className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-base-200/30 transition-colors text-left cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 flex items-center justify-center shrink-0">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-[11px] font-bold text-base-content uppercase tracking-widest">Commitment Gate</p>
                    <p className="text-[10px] text-base-content/60 mt-0.5">
                      {confirmedCommitments
                        ? "✓ Action items synced"
                        : commitments.length > 0
                        ? `${commitments.length} commitment${commitments.length !== 1 ? "s" : ""} detected`
                        : "Extract action items & deadlines"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {commitments.length > 0 && !confirmedCommitments && (
                    <span className="text-[9px] font-bold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 px-1.5 py-0.5 rounded-full">
                      {commitments.length}
                    </span>
                  )}
                  <svg className={`w-4 h-4 text-base-content/60 transition-transform duration-200 ${isCommitmentsExpanded ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>
              {isCommitmentsExpanded && (
                <div className="border-t border-base-200 bg-base-300/20 px-4 py-4">
                  <CommitmentGate
                    commitments={commitments} loading={commitmentsLoading}
                    error={commitmentsError} confirming={confirmingCommitments}
                    confirmed={confirmedCommitments} taskUrls={taskUrls}
                    eventUrls={eventUrls} toggleCommitment={toggleCommitment}
                    confirmSelected={confirmSelectedCommitments} checkConflict={checkConflict}
                  />
                </div>
              )}
            </div>

            {/* Precedents + Thread */}
            <div className="px-4 py-4 space-y-4 bg-base-300">
              <PrecedentList precedents={precedents} />
              <ThreadView emailId={email.id} />
            </div>
          </div>
        )}

        {!showPipeline && (
          <div className="px-4 py-4">
            <ThreadView emailId={email.id} />
          </div>
        )}
      </div>
    </div>
  );
}
