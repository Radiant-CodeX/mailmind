import React from 'react';
import { LoadingSpinner } from '../shared/LoadingSpinner';

interface DraftPanelProps {
  draft: string | null;
  setDraft: (text: string) => void;
  isGenerating: boolean;
  onGenerate: () => void;
  isApproved: boolean;
  setIsApproved: (approved: boolean) => void;
}

export function DraftPanel({
  draft,
  setDraft,
  isGenerating,
  onGenerate,
  isApproved,
  setIsApproved,
}: DraftPanelProps) {
  if (isGenerating) {
    return (
      <div className="p-4 text-center animate-fade-in" id="draft-panel-loading">
        <LoadingSpinner message="Querying RAG store & drafting response..." />
      </div>
    );
  }

  if (isApproved) {
    return (
      <div
        className="p-4 bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg text-left animate-fade-in"
        id="draft-panel-success"
      >
        <div className="flex items-center gap-2 text-[var(--text-primary)] mb-2">
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-sm font-bold tracking-tight">Draft Approved & Sent Successfully</span>
        </div>
        <p className="text-xs text-[var(--text-muted)] leading-relaxed">
          The email response has been transmitted to Microsoft Graph API and queued for delivery.
        </p>
        <button
          onClick={() => setIsApproved(false)}
          className="mt-3 text-xs text-[var(--accent-primary)] hover:underline font-semibold cursor-pointer"
        >
          View sent text
        </button>
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="p-4 text-center animate-fade-in" id="draft-panel-empty">
        <button
          onClick={onGenerate}
          className="w-full py-2.5 px-4 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-sm cursor-pointer"
        >
          <svg
            className="w-4 h-4"
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
          Generate AI Draft
        </button>
      </div>
    );
  }

  return (
    <div className="text-left animate-fade-in" id="draft-panel-active">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center gap-1.5">
          <svg
            className="w-4 h-4 text-[var(--accent-primary)]"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
            />
          </svg>
          AI-Generated Draft Response
        </h4>
        <button
          onClick={onGenerate}
          className="text-[10px] font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer"
        >
          Regenerate
        </button>
      </div>

      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={6}
        className="w-full p-3 rounded bg-[var(--bg-elevated)] border border-[var(--border)] text-xs text-[var(--text-primary)] leading-relaxed focus:outline-none focus:border-[var(--accent-primary)] resize-none font-medium custom-scrollbar"
      ></textarea>

      <div className="mt-3 flex justify-end">
        <button
          onClick={() => setIsApproved(true)}
          className="py-2 px-4 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] rounded text-xs font-bold transition-all shadow-sm cursor-pointer"
        >
          Approve & Send
        </button>
      </div>
    </div>
  );
}
