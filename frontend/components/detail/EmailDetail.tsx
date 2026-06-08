import React, { useState } from 'react';
import { Email, ClassificationResult, TriageResult, PrecedentItem, CommitmentItem as TypeCommitment, CalendarEvent } from '../../lib/types';
import { TriageExplainer } from '../triage/TriageExplainer';
import { PrecedentList } from './PrecedentList';
import { DraftPanel } from './DraftPanel';
import { ThreadView } from './ThreadView';
import { CommitmentGate } from '../commitments/CommitmentGate';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { ErrorBanner } from '../shared/ErrorBanner';

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
  generateDraft: (style?: 'standard' | 'formal' | 'indepth') => void;
  isDraftApproved: boolean;
  setIsDraftApproved: (val: boolean) => void;
  activeStyle: 'standard' | 'formal' | 'indepth';
  setActiveStyle: (style: 'standard' | 'formal' | 'indepth') => void;
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
  showPipeline = true,
}: EmailDetailProps) {
  const [isDraftExpanded, setIsDraftExpanded] = useState(false);
  const [isCommitmentsExpanded, setIsCommitmentsExpanded] = useState(false);

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!email) {
    return null;
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/15 z-50 flex justify-end" id="email-detail-loading-overlay">
        <div className="absolute inset-0 cursor-default" onClick={onClose} />
        <div className="relative bg-[var(--bg-base)] w-full max-w-3xl h-full border-l border-[var(--border)] shadow-2xl flex flex-col items-center justify-center p-8 text-center animate-slide-in-right z-50">
          <LoadingSpinner message="Performing NLP classification and calculating priority indices..." size="lg" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/15 z-50 flex justify-end" id="email-detail-overlay">
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
            <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Email Inspection</span>
          </div>
          <button 
            onClick={onClose}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md hover:bg-[var(--bg-elevated)] text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer font-semibold uppercase tracking-wide border border-[var(--border)]"
            id="btn-close-email-detail"
          >
            <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Close
          </button>
        </div>

        {/* Detail Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {error && <ErrorBanner message={error} />}

          {/* Email Header Card */}
          <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 text-left shadow-sm flex items-center justify-between gap-4" id="email-header-card">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-4 mb-3">
                <span className="text-xs font-semibold text-[var(--accent-primary)] font-mono">
                  From: {email.sender}
                </span>
                <span className="text-[10px] text-[var(--text-muted)] font-mono" suppressHydrationWarning>
                  Received: {new Date(email.received_at).toLocaleString()}
                </span>
              </div>
              <h2 className="text-base font-bold text-[var(--text-primary)] leading-snug">
                {email.subject}
              </h2>
            </div>

            {/* Triage Score Circle Graph */}
            {triageResult && (
              <div className="flex flex-col items-center shrink-0 relative group" id="header-triage-graph">
                <div className="relative w-14 h-14 flex items-center justify-center cursor-help">
                  {/* SVG Progress Circle Graph */}
                  <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
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
                          ? 'text-red-500'
                          : triageResult.composite_score >= 50
                          ? 'text-orange-500'
                          : triageResult.composite_score >= 25
                          ? 'text-amber-500'
                          : 'text-slate-400'
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
                  <TriageExplainer triage={triageResult} classification={classification} />
                </div>
              </div>
            )}
          </div>

          {/* Full Email Body */}
          <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 text-left shadow-sm">
            <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider mb-3 pb-1.5 border-b border-[var(--border-subtle)]">
              Message Body
            </h3>
            <p className="text-xs text-[var(--text-primary)]/90 whitespace-pre-wrap leading-relaxed font-medium">
              {email.body}
            </p>
          </div>

          {showPipeline && (<>
          {/* AI Draft Tool Accordion */}
          <div className="border border-[var(--border)] rounded-lg bg-[var(--bg-surface)] overflow-hidden shadow-sm" id="accordion-draft">
            <button
              onClick={() => setIsDraftExpanded(!isDraftExpanded)}
              className="w-full flex items-center justify-between p-4 bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]/25 transition-all text-left cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <div className={`p-1.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20`}>
                  <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">AI Co-Pilot Draft</h3>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                    {isDraftApproved ? 'Draft Sent Successfully' : aiDraft ? 'Draft response generated' : 'Click to trigger email auto-reply draft'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--text-muted)] font-semibold">{isDraftExpanded ? 'Collapse' : 'Expand'}</span>
                <svg
                  className={`w-4 h-4 text-[var(--text-muted)] transition-transform duration-200 ${isDraftExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
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
          <div className="border border-[var(--border)] rounded-lg bg-[var(--bg-surface)] overflow-hidden shadow-sm" id="accordion-commitments">
            <button
              onClick={() => setIsCommitmentsExpanded(!isCommitmentsExpanded)}
              className="w-full flex items-center justify-between p-4 bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)]/25 transition-all text-left cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <div className={`p-1.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20`}>
                  <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">Commitment Gate</h3>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                    {confirmedCommitments ? 'Action items synchronized' : commitments.length > 0 ? `${commitments.length} commitments detected for tracking` : 'Click to extract natural-language action items'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--text-muted)] font-semibold">{isCommitmentsExpanded ? 'Collapse' : 'Expand'}</span>
                <svg
                  className={`w-4 h-4 text-[var(--text-muted)] transition-transform duration-200 ${isCommitmentsExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
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
          </>)}

          {/* Thread History View */}
          <ThreadView emailId={email.id} />
        </div>
      </div>
    </div>
  );
}
