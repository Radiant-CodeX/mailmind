import React from 'react';
import { LoadingSpinner } from '../shared/LoadingSpinner';

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
}


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
}: DraftPanelProps) {
  if (isGenerating) {
    return (
      <div className="p-6 text-center animate-fade-in" id="draft-panel-loading">
        <LoadingSpinner message={`Generating ${activeStyle === 'indepth' ? 'in-depth' : activeStyle} response draft...`} />
      </div>
    );
  }

  if (isApproved) {
    return (
      <div
        className="p-5 bg-[var(--bg-elevated)] border border-[var(--border)] rounded-lg text-left animate-fade-in"
        id="draft-panel-success"
      >
        <div className="flex items-center gap-2 text-[var(--text-primary)] mb-2">
          <svg
            className="w-5 h-5 text-emerald-500"
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

  return (
    <div className="text-left animate-fade-in" id="draft-panel-active">
      {/* Style Tabs selector */}
      <div className="flex border-b border-[var(--border-subtle)] mb-4 gap-1">
        {(['standard', 'formal', 'indepth'] as const).map((style) => (
          <button
            key={style}
            onClick={() => setActiveStyle(style)}
            className={`px-4 py-2 text-xs font-bold border-b-2 transition-all cursor-pointer capitalize ${
              activeStyle === style
                ? 'border-[var(--accent-primary)] text-[var(--accent-primary)]'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
          >
            {style === 'indepth' ? 'In-depth' : style}
          </button>
        ))}
      </div>

      {!draft ? (
        <div className="p-6 text-center bg-[var(--bg-elevated)]/30 border border-dashed border-[var(--border)] rounded-lg animate-fade-in" id="draft-panel-empty">
          <p className="text-xs text-[var(--text-muted)] mb-4 leading-relaxed max-w-md mx-auto">
            {activeStyle === 'standard' && 'Standard reply builds a brief, helpful template answering the main inquiry directly.'}
            {activeStyle === 'formal' && 'Formal reply applies structured, professional business language with formal greetings.'}
            {activeStyle === 'indepth' && 'In-depth reply breaks down details point-by-point, structuring action items and next steps.'}
          </p>
          <button
            onClick={() => onGenerate(activeStyle)}
            className="py-2.5 px-4 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] rounded-lg text-xs font-bold transition-all inline-flex items-center gap-2 shadow-sm cursor-pointer"
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
            Generate {activeStyle === 'indepth' ? 'In-depth' : activeStyle.charAt(0).toUpperCase() + activeStyle.slice(1)} Draft
          </button>
        </div>
      ) : (
        <div className="animate-fade-in">
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
              AI-Generated {activeStyle === 'indepth' ? 'In-depth' : activeStyle} Draft
            </h4>
            <button
              onClick={() => onGenerate(activeStyle)}
              className="text-[10px] font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer font-mono"
            >
              REGENERATE
            </button>
          </div>

          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={8}
            className="w-full p-3 rounded bg-[var(--bg-elevated)] border border-[var(--border)] text-xs text-[var(--text-primary)] leading-relaxed focus:outline-none focus:border-[var(--accent-primary)] resize-y min-h-[140px] font-medium custom-scrollbar"
          ></textarea>

          <div className="mt-3 flex justify-end">
            <button
              onClick={() => {
                if (onSend && draft) {
                  onSend(draft);
                } else {
                  setIsApproved(true);
                }
              }}
              disabled={isSending}
              className="py-2 px-4 bg-[var(--accent-primary)] hover:opacity-90 disabled:opacity-50 text-[var(--bg-surface)] rounded text-xs font-bold transition-all shadow-sm cursor-pointer flex items-center gap-1.5"
            >
              {isSending ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-[var(--bg-surface)] border-t-transparent animate-spin rounded-full"></span>
                  Sending...
                </>
              ) : (
                'Approve & Send'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
