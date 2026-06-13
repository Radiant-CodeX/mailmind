import React, { useState } from 'react';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { approveAgentDraft } from '../../lib/api';

interface DraftPanelProps {
  draft: string | null;
  setDraft: (text: string) => void;
  isGenerating: boolean;
  onGenerate: (style: 'standard' | 'formal' | 'indepth') => void;
  isApproved: boolean;
  setIsApproved: (approved: boolean) => void;
  activeStyle: 'standard' | 'formal' | 'indepth';
  setActiveStyle: (style: 'standard' | 'formal' | 'indepth') => void;
  isSending?: boolean;
  onSend?: (comment: string) => void;
  // HITL gate props
  approvalMode?: string;       // "GATE" | "SUGGEST" | undefined
  triageScore?: number;
  triageReasons?: string[];    // why it was gated
  emailId?: string;
}

type GateStep = 'idle' | 'confirming' | 'rejected';

export function DraftPanel({
  draft,
  setDraft,
  isGenerating,
  onGenerate,
  isApproved,
  setIsApproved,
  activeStyle,
  setActiveStyle,
  isSending = false,
  onSend,
  approvalMode,
  triageScore,
  triageReasons,
  emailId,
}: DraftPanelProps) {
  const [gateStep, setGateStep] = useState<GateStep>('idle');
  const [gateLoading, setGateLoading] = useState(false);

  const isCritical = approvalMode === 'GATE';

  // Always require human confirmation before sending any AI draft.
  const handleSendClick = () => {
    setGateStep('confirming');
  };

  const doSend = async () => {
    if (!draft) return;
    // Record approval in backend (fire-and-forget, don't block send)
    if (emailId) {
      approveAgentDraft(emailId, 'approve', draft).catch(() => {});
    }
    onSend?.(draft);
  };

  const handleConfirmSend = async () => {
    setGateLoading(true);
    try {
      await doSend();
      setGateStep('idle');
    } finally {
      setGateLoading(false);
    }
  };

  const handleReject = async () => {
    if (emailId) {
      approveAgentDraft(emailId, 'reject').catch(() => {});
    }
    setGateStep('rejected');
  };

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isGenerating) {
    return (
      <div className="p-6 text-center animate-fade-in">
        <LoadingSpinner message={`Generating ${activeStyle === 'indepth' ? 'in-depth' : activeStyle} response draft...`} />
      </div>
    );
  }

  // ── Sent successfully ────────────────────────────────────────────────────
  if (isApproved) {
    return (
      <div className="p-5 bg-base-200 border border-base-300 rounded-lg text-left animate-fade-in">
        <div className="flex items-center gap-2 text-base-content mb-2">
          <svg className="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-bold tracking-tight">Draft Approved & Sent Successfully</span>
        </div>
        <p className="text-xs text-base-content/60 leading-relaxed">
          The email response has been transmitted and queued for delivery.
        </p>
        <button
          onClick={() => setIsApproved(false)}
          className="mt-3 text-xs text-primary hover:underline font-semibold cursor-pointer"
        >
          View sent text
        </button>
      </div>
    );
  }

  // ── Rejected ─────────────────────────────────────────────────────────────
  if (gateStep === 'rejected') {
    return (
      <div className="p-5 bg-base-200 border border-red-500/20 rounded-lg text-left animate-fade-in">
        <div className="flex items-center gap-2 mb-2">
          <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
          <span className="text-sm font-bold text-base-content">Draft Discarded</span>
        </div>
        <p className="text-xs text-base-content/60 leading-relaxed">
          The draft was not sent. You can generate a new one or close this panel.
        </p>
        <button
          onClick={() => setGateStep('idle')}
          className="mt-3 text-xs text-primary hover:underline font-semibold cursor-pointer"
        >
          ← Back to draft
        </button>
      </div>
    );
  }

  // ── Severity styling for the confirmation screen ─────────────────────────
  const score = triageScore ?? 0;
  const severity =
    isCritical ? 'critical' :
    score >= 50 ? 'high' :
    'normal';

  const severityStyles = {
    critical: {
      border: 'border-red-500/30',
      bg: 'bg-red-500/8',
      iconBg: 'bg-red-500/15 border-red-500/25',
      icon: 'text-red-500',
      label: '⛔ Human Approval Required — Critical Email',
      labelColor: 'text-red-500',
      scoreColor: 'text-red-500',
      dot: 'bg-red-500/60',
      btn: 'bg-red-600 hover:bg-red-700 text-white',
    },
    high: {
      border: 'border-amber-500/30',
      bg: 'bg-amber-500/8',
      iconBg: 'bg-amber-500/15 border-amber-500/25',
      icon: 'text-amber-500',
      label: '⚠ Review Before Sending — High Priority',
      labelColor: 'text-amber-500',
      scoreColor: 'text-amber-500',
      dot: 'bg-amber-500/60',
      btn: 'bg-amber-600 hover:bg-amber-700 text-white',
    },
    normal: {
      border: 'border-base-300',
      bg: 'bg-base-200/50',
      iconBg: 'bg-blue-500/10 border-blue-500/20',
      icon: 'text-blue-400',
      label: '✉ Confirm Send',
      labelColor: 'text-base-content',
      scoreColor: 'text-base-content/60',
      dot: 'bg-base-content/60/40',
      btn: 'bg-primary hover:opacity-90 text-base-100',
    },
  }[severity];

  // ── HITL Gate confirmation screen ────────────────────────────────────────
  if (gateStep === 'confirming') {
    return (
      <div className="animate-fade-in space-y-4">
        {/* Contextual warning banner */}
        <div className={`rounded-lg border ${severityStyles.border} ${severityStyles.bg} px-4 py-3.5`}>
          <div className="flex items-start gap-3">
            <div className={`w-7 h-7 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 ${severityStyles.iconBg}`}>
              <svg className={`w-4 h-4 ${severityStyles.icon}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-[12px] font-bold uppercase tracking-wider mb-1 ${severityStyles.labelColor}`}>
                {severityStyles.label}
              </p>
              <p className="text-[12px] text-base-content leading-relaxed">
                {severity === 'normal'
                  ? 'You are about to send an AI-generated reply. Review the draft below before confirming.'
                  : <>
                      Triage score:{' '}
                      <span className={`font-bold ${severityStyles.scoreColor}`}>
                        {triageScore !== undefined ? Math.round(triageScore) : '—'}/100
                      </span>
                      . Review your draft carefully before sending.
                    </>
                }
              </p>
              {triageReasons && triageReasons.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {triageReasons.map((r, i) => (
                    <li key={i} className="text-[11px] text-base-content/60 flex items-center gap-1.5">
                      <span className={`w-1 h-1 rounded-full shrink-0 ${severityStyles.dot}`} />
                      {r}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>

        {/* Draft preview (read-only) */}
        <div>
          <p className="text-[10px] font-bold text-base-content/60 uppercase tracking-widest mb-2">
            Draft to be sent:
          </p>
          <div className="bg-base-200 border border-base-300 rounded-lg p-3 text-xs text-base-content leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto custom-scrollbar">
            {draft}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 justify-end pt-1">
          <button
            onClick={handleReject}
            disabled={gateLoading}
            className="px-4 py-2 text-xs font-bold text-base-content/60 hover:text-base-content border border-base-300 hover:border-red-500/40 rounded-lg transition-all cursor-pointer disabled:opacity-50"
          >
            Discard Draft
          </button>
          <button
            onClick={() => setGateStep('idle')}
            disabled={gateLoading}
            className="px-4 py-2 text-xs font-bold text-base-content/60 hover:text-base-content border border-base-300 rounded-lg transition-all cursor-pointer disabled:opacity-50"
          >
            ← Edit First
          </button>
          <button
            onClick={handleConfirmSend}
            disabled={gateLoading || isSending}
            className={`px-4 py-2 text-xs font-bold disabled:opacity-50 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 shadow-sm ${severityStyles.btn}`}
          >
            {gateLoading || isSending ? (
              <>
                <span className="w-3 h-3 border-2 border-white/40 border-t-white animate-spin rounded-full" />
                Sending...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Confirm & Send
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  // ── Normal draft panel ───────────────────────────────────────────────────
  return (
    <div className="text-left animate-fade-in">
      {/* Style tabs */}
      <div className="flex border-b border-base-200 mb-4 gap-1">
        {(['standard', 'formal', 'indepth'] as const).map((style) => (
          <button
            key={style}
            onClick={() => setActiveStyle(style)}
            className={`px-4 py-2 text-xs font-bold border-b-2 transition-all cursor-pointer capitalize ${
              activeStyle === style
                ? 'border-primary text-primary'
                : 'border-transparent text-base-content/60 hover:text-base-content'
            }`}
          >
            {style === 'indepth' ? 'In-depth' : style}
          </button>
        ))}
      </div>

      {/* Pre-send notice — shown when CRITICAL/HIGH before draft is generated */}
      {isCritical && !draft && (
        <div className="mb-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-red-500/8 border border-red-500/20">
          <svg className="w-3.5 h-3.5 text-red-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <span className="text-[11px] text-red-500 font-semibold">
            CRITICAL email — review required before sending
          </span>
        </div>
      )}

      {!draft ? (
        <div className="p-6 text-center bg-base-200/30 border border-dashed border-base-300 rounded-lg">
          <p className="text-xs text-base-content/60 mb-4 leading-relaxed max-w-md mx-auto">
            {activeStyle === 'standard' && 'Standard reply builds a brief, helpful template answering the main inquiry directly.'}
            {activeStyle === 'formal' && 'Formal reply applies structured, professional business language with formal greetings.'}
            {activeStyle === 'indepth' && 'In-depth reply breaks down details point-by-point, structuring action items and next steps.'}
          </p>
          <button
            onClick={() => onGenerate(activeStyle)}
            className="py-2.5 px-4 bg-primary hover:opacity-90 text-base-100 rounded-lg text-xs font-bold transition-all inline-flex items-center gap-2 shadow-sm cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Generate {activeStyle === 'indepth' ? 'In-depth' : activeStyle.charAt(0).toUpperCase() + activeStyle.slice(1)} Draft
          </button>
        </div>
      ) : (
        <div className="animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-bold text-base-content uppercase tracking-wider flex items-center gap-1.5">
              <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              AI-Generated {activeStyle === 'indepth' ? 'In-depth' : activeStyle} Draft
            </h4>
            <button
              onClick={() => onGenerate(activeStyle)}
              className="text-[10px] font-semibold text-base-content/60 hover:text-base-content transition-all cursor-pointer font-mono"
            >
              REGENERATE
            </button>
          </div>

          {/* PII badge */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 600,
            marginBottom: 8, background: 'var(--color-background-success)',
            color: 'var(--color-text-success)', border: '0.5px solid var(--color-border-success)',
          }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            PII check: passed
          </div>

          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={8}
            className="w-full p-3 rounded bg-base-200 border border-base-300 text-xs text-base-content leading-relaxed focus:outline-none focus:border-primary resize-y min-h-[140px] font-medium custom-scrollbar"
          />

          <div className="mt-3 flex items-center justify-between">
            {isCritical && (
              <div className="flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
                <span className="text-[11px] font-bold text-red-500">Approval required</span>
              </div>
            )}
            {!isCritical && <div />}

            <button
              onClick={handleSendClick}
              disabled={isSending}
              className="py-2 px-4 bg-primary hover:opacity-90 disabled:opacity-50 text-base-100 rounded text-xs font-bold transition-all shadow-sm cursor-pointer flex items-center gap-1.5"
            >
              {isSending ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-current/40 border-t-current animate-spin rounded-full" />
                  Sending...
                </>
              ) : (
                'Review & Send'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
