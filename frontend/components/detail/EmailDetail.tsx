import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Email,
  ClassificationResult,
  TriageResult,
  PrecedentItem,
  CommitmentItem as TypeCommitment,
  CalendarEvent,
} from "../../lib/types";

/**
 * Sanitize and render HTML email bodies using DOMPurify.
 *
 * Rendering strategy:
 *   - DOMPurify strips all XSS vectors (scripts, event handlers, data: URIs)
 *   - Rendered inside a sandboxed iframe so email CSS cannot affect the app
 *   - All links open in a new tab with rel="noopener noreferrer"
 *   - Iframe auto-resizes to fit the email content height
 */
function EmailBodyHtml({ html }: { html: string }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(300);

  const sanitized = useMemo(() => {
    if (typeof window === "undefined") return "";
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const DOMPurify = require("dompurify");

    const clean = DOMPurify.sanitize(html, {
      FORCE_BODY: true,
      ADD_ATTR: [
        "target",
        "rel",
        "width",
        "height",
        "bgcolor",
        "align",
        "valign",
        "cellpadding",
        "cellspacing",
        "border",
      ],
      FORBID_TAGS: [
        "script",
        "object",
        "embed",
        "form",
        "input",
        "textarea",
        "select",
      ],
      FORBID_ATTR: [
        "action",
        "formaction",
        "onerror",
        "onload",
        "onclick",
        "onmouseover",
      ],
    });

    const doc = new DOMParser().parseFromString(clean, "text/html");

    // Force all links to open in a new tab — required for sandbox allow-popups.
    doc.querySelectorAll("a").forEach((a) => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
      // Strip javascript: hrefs entirely.
      if (/^javascript:/i.test(a.getAttribute("href") || ""))
        a.removeAttribute("href");
    });

    // Block tracking pixels and external images that could leak the user's IP.
    // Only data: URIs (inline images) and https: CDN images are allowed.
    doc.querySelectorAll("img").forEach((img) => {
      const src = img.getAttribute("src") || "";
      if (!src.startsWith("data:") && !src.startsWith("https://")) {
        img.removeAttribute("src");
        img.setAttribute("alt", img.getAttribute("alt") || "[image]");
      }
    });

    // Base styles — match Gmail's rendering defaults.
    const style = doc.createElement("style");
    style.textContent = `
      html, body {
        margin: 0; padding: 8px 0;
        font-family: Arial, sans-serif;
        font-size: 14px; line-height: 1.6;
        color: #202124;
        background: #ffffff;
        word-break: break-word;
        overflow-wrap: break-word;
        -webkit-text-size-adjust: 100%;
      }
      img { max-width: 100%; height: auto; }
      a { color: #1a73e8; cursor: pointer; }
      table { border-collapse: collapse; }
      blockquote { border-left: 2px solid #ccc; margin: 8px 0; padding-left: 12px; color: #555; }
      pre, code { font-family: monospace; font-size: 13px; white-space: pre-wrap; }
    `;
    if (doc.head.firstChild) doc.head.insertBefore(style, doc.head.firstChild);
    else doc.head.appendChild(style);

    return doc.documentElement.outerHTML;
  }, [html]);

  // Auto-resize the iframe to the email content height once it loads.
  // srcdoc is the correct declarative approach; doc.write() is deprecated and
  // unreliable inside sandboxed iframes across browsers.
  const handleLoad = () => {
    const body = iframeRef.current?.contentDocument?.body;
    if (body) setHeight(Math.max(200, body.scrollHeight + 32));
  };

  return (
    <iframe
      ref={iframeRef}
      // allow-same-origin: lets us read scrollHeight for auto-resize
      // allow-popups + allow-popups-to-escape-sandbox: lets target="_blank" links open new tabs
      // allow-top-navigation-by-user-activation: lets clicked links that lack target="_blank" navigate
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
      srcDoc={sanitized}
      onLoad={handleLoad}
      style={{
        width: "100%",
        height: `${height}px`,
        border: "none",
        background: "white",
        borderRadius: "6px",
      }}
      title="Email content"
    />
  );
}

/** Plain-text email body — preserves whitespace and wraps long lines. */
function EmailBodyPlain({ text }: { text: string }) {
  return (
    <p className="text-xs text-[var(--text-primary)]/90 whitespace-pre-wrap leading-relaxed font-medium break-words">
      {text}
    </p>
  );
}

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

/** Downloadable attachment list — clicking a row streams the file via the backend. */
function AttachmentList({
  emailId,
  attachments,
}: {
  emailId: string;
  attachments: NonNullable<Email["attachments"]>;
}) {
  const download = (attId: string, filename: string) => {
    import("../../lib/api").then(({ downloadAttachment }) =>
      downloadAttachment(emailId, attId, filename),
    );
  };

  return (
    <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 text-left shadow-sm">
      <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider mb-3 pb-1.5 border-b border-[var(--border-subtle)]">
        Attachments ({attachments.length})
      </h3>
      <div className="flex flex-col gap-2">
        {attachments.map((att) => (
          <button
            key={att.attachment_id}
            onClick={() => download(att.attachment_id, att.filename)}
            className="flex items-center gap-3 p-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/30 hover:bg-[var(--bg-elevated)] hover:border-[var(--accent-primary)] transition-all cursor-pointer text-left group"
          >
            <span className="text-lg shrink-0">{fileIcon(att.mime_type)}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-[var(--text-primary)] truncate">
                {att.filename}
              </p>
              <p className="text-[10px] text-[var(--text-muted)]">
                {formatBytes(att.size)}
              </p>
            </div>
            <svg
              className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)] shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}
import { TriageExplainer } from "../triage/TriageExplainer";
import { PrecedentList } from "./PrecedentList";
import { DraftPanel } from "./DraftPanel";
import { ThreadView } from "./ThreadView";
import { CommitmentGate } from "../commitments/CommitmentGate";
import { LoadingSpinner } from "../shared/LoadingSpinner";
import { ErrorBanner } from "../shared/ErrorBanner";

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

  // Commitment Gate Props
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
  /** Fetched attachment metadata (replaces empty email.attachments from inbox). */
  attachments?: NonNullable<Email["attachments"]>;
  /** When false (e.g. the Sent folder) the AI pipeline panels are hidden. */
  showPipeline?: boolean;
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
}: EmailDetailProps) {
  const [isDraftExpanded, setIsDraftExpanded] = useState(false);
  const [isCommitmentsExpanded, setIsCommitmentsExpanded] = useState(false);

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!email) {
    return null;
  }

  if (loading) {
    return (
      <div
        className="fixed inset-0 bg-black/15 z-50 flex justify-end"
        id="email-detail-loading-overlay"
      >
        <div className="absolute inset-0 cursor-default" onClick={onClose} />
        <div className="relative bg-[var(--bg-base)] w-full max-w-3xl h-full border-l border-[var(--border)] shadow-2xl flex flex-col items-center justify-center p-8 text-center animate-slide-in-right z-50">
          <LoadingSpinner
            message="Analyzing email context, extracting action items, and prioritizing for review..."
            size="lg"
          />
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 bg-black/15 z-50 flex justify-end"
      id="email-detail-overlay"
    >
      {/* Click outside to close backdrop */}
      <div className="absolute inset-0 cursor-default" onClick={onClose} />

      {/* Drawer Content container */}
      <div
        className="relative bg-[var(--bg-base)] w-full max-w-3xl h-full border-l border-[var(--border)] shadow-2xl flex flex-col overflow-hidden animate-slide-in-right z-50"
        onClick={(e) => e.stopPropagation()}
        id="email-detail-modal"
      >
        {/* Top action bar */}
        <div className="h-14 border-b border-[var(--border-subtle)] px-6 flex items-center justify-between bg-[var(--bg-surface)] shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
              Email Inspection
            </span>
          </div>
          <button
            onClick={onClose}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md hover:bg-[var(--bg-elevated)] text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer font-semibold uppercase tracking-wide border border-[var(--border)]"
            id="btn-close-email-detail"
          >
            <svg
              className="w-4.5 h-4.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            Close
          </button>
        </div>

        {/* Detail Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {error && <ErrorBanner message={error} />}

          {/* Email Header Card */}
          <div
            className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 text-left shadow-sm flex items-center justify-between gap-4"
            id="email-header-card"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-4 mb-3">
                <span className="text-xs font-semibold text-[var(--accent-primary)] font-mono">
                  From: {email.sender}
                </span>
                <span
                  className="text-[10px] text-[var(--text-muted)] font-mono"
                  suppressHydrationWarning
                >
                  Received: {new Date(email.received_at).toLocaleString()}
                </span>
              </div>
              <h2 className="text-base font-bold text-[var(--text-primary)] leading-snug">
                {email.subject}
              </h2>
            </div>

            {/* Triage Score Circle Graph */}
            {triageResult && (
              <div
                className="flex flex-col items-center shrink-0 relative group"
                id="header-triage-graph"
              >
                <div className="relative w-14 h-14 flex items-center justify-center cursor-help">
                  {/* SVG Progress Circle Graph */}
                  <svg
                    className="w-full h-full transform -rotate-90"
                    viewBox="0 0 36 36"
                  >
                    {/* Background track circle */}
                    <circle
                      className="text-[var(--border)]"
                      strokeWidth="3.5"
                      stroke="currentColor"
                      fill="none"
                      cx="18"
                      cy="18"
                      r="16"
                    />
                    {/* Foreground progress circle */}
                    <circle
                      className={`transition-all duration-500 ${
                        triageResult.composite_score >= 75
                          ? "text-red-500"
                          : triageResult.composite_score >= 50
                            ? "text-orange-500"
                            : triageResult.composite_score >= 25
                              ? "text-amber-500"
                              : "text-slate-400"
                      }`}
                      strokeDasharray="100, 100"
                      strokeDashoffset={100 - triageResult.composite_score}
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      stroke="currentColor"
                      fill="none"
                      cx="18"
                      cy="18"
                      r="16"
                    />
                  </svg>
                  {/* Center text integer */}
                  <div className="absolute flex flex-col items-center justify-center">
                    <span className="text-xs font-black text-[var(--text-primary)] font-mono leading-none">
                      {Math.round(triageResult.composite_score)}
                    </span>
                    <span className="text-[7px] text-[var(--text-muted)] font-bold tracking-wider uppercase leading-none mt-0.5">
                      Triage
                    </span>
                  </div>
                </div>

                {/* Hover Triage Insights Popover */}
                <div className="absolute right-0 top-[56px] hidden group-hover:block bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl shadow-2xl p-5 w-[320px] sm:w-[480px] md:w-[540px] z-50 pointer-events-auto cursor-default animate-fade-in text-left">
                  <TriageExplainer
                    triage={triageResult}
                    classification={classification}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Full Email Body */}
          <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 text-left shadow-sm">
            <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider mb-3 pb-1.5 border-b border-[var(--border-subtle)]">
              Message Body
            </h3>
            {email.html_body ? (
              <EmailBodyHtml html={email.html_body} />
            ) : (
              <EmailBodyPlain text={email.body} />
            )}
          </div>

          {/* Attachments */}
          {(() => {
            const atts = attachmentsProp && attachmentsProp.length > 0
              ? attachmentsProp
              : email.attachments && email.attachments.length > 0 ? email.attachments : null;
            return atts ? <AttachmentList emailId={email.id} attachments={atts} /> : null;
          })()}
          )}

          {showPipeline && (
            <>
              {/* AI Draft Tool Accordion */}
              <div
                className="border border-[var(--border)] rounded-lg bg-[var(--bg-surface)] overflow-hidden shadow-sm"
                id="accordion-draft"
              >
                <button
                  onClick={() => setIsDraftExpanded(!isDraftExpanded)}
                  className="w-full flex items-center justify-between p-4 bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]/25 transition-all text-left cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`p-1.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20`}
                    >
                      <svg
                        className="w-4.5 h-4.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 10V3L4 14h7v7l9-11h-7z"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                        AI Co-Pilot Draft
                      </h3>
                      <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                        {isDraftApproved
                          ? "Draft Sent Successfully"
                          : aiDraft
                            ? "Draft response generated"
                            : "Click to trigger email auto-reply draft"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-[var(--text-muted)] font-semibold">
                      {isDraftExpanded ? "Collapse" : "Expand"}
                    </span>
                    <svg
                      className={`w-4 h-4 text-[var(--text-muted)] transition-transform duration-200 ${isDraftExpanded ? "rotate-180" : ""}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.5}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </div>
                </button>
                {isDraftExpanded && (
                  <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-base)]/10 p-4">
                    <DraftPanel
                      draft={aiDraft}
                      setDraft={setAiDraft}
                      isGenerating={isGeneratingDraft}
                      onGenerate={generateDraft}
                      isApproved={isDraftApproved}
                      setIsApproved={setIsDraftApproved}
                      activeStyle={activeStyle}
                      setActiveStyle={setActiveStyle}
                      isSending={isSendingDraft}
                      onSend={sendDraft}
                    />
                  </div>
                )}
              </div>

              {/* Commitment Gate Accordion */}
              <div
                className="border border-[var(--border)] rounded-lg bg-[var(--bg-surface)] overflow-hidden shadow-sm"
                id="accordion-commitments"
              >
                <button
                  onClick={() =>
                    setIsCommitmentsExpanded(!isCommitmentsExpanded)
                  }
                  className="w-full flex items-center justify-between p-4 bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]/25 transition-all text-left cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`p-1.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20`}
                    >
                      <svg
                        className="w-4.5 h-4.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
                        Commitment Gate
                      </h3>
                      <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                        {confirmedCommitments
                          ? "Action items synchronized"
                          : commitments.length > 0
                            ? `${commitments.length} commitments detected for tracking`
                            : "Click to extract natural-language action items"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-[var(--text-muted)] font-semibold">
                      {isCommitmentsExpanded ? "Collapse" : "Expand"}
                    </span>
                    <svg
                      className={`w-4 h-4 text-[var(--text-muted)] transition-transform duration-200 ${isCommitmentsExpanded ? "rotate-180" : ""}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.5}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </div>
                </button>
                {isCommitmentsExpanded && (
                  <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-base)]/10 p-4">
                    <CommitmentGate
                      commitments={commitments}
                      loading={commitmentsLoading}
                      error={commitmentsError}
                      confirming={confirmingCommitments}
                      confirmed={confirmedCommitments}
                      taskUrls={taskUrls}
                      eventUrls={eventUrls}
                      toggleCommitment={toggleCommitment}
                      confirmSelected={confirmSelectedCommitments}
                      checkConflict={checkConflict}
                    />
                  </div>
                )}
              </div>

              {/* RAG Precedents List */}
              <PrecedentList precedents={precedents} />
            </>
          )}

          {/* Thread History View */}
          <ThreadView emailId={email.id} />
        </div>
      </div>
    </div>
  );
}
