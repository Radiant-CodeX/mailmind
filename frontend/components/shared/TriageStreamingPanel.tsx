'use client';

import React, { useEffect, useState } from 'react';

interface TriageEvent {
  email_id: string;
  priority: string;
  composite_score: number;
  cached?: boolean;
  error?: string;
  done?: boolean;
}

interface TriageStreamingPanelProps {
  totalEmails: number;
  isStreaming: boolean;
  completedEmails: number;
}

export function TriageStreamingPanel({
  totalEmails,
  isStreaming,
  completedEmails,
}: TriageStreamingPanelProps) {
  const percentage = totalEmails > 0 ? (completedEmails / totalEmails) * 100 : 0;

  if (!isStreaming && completedEmails === 0) return null;

  return (
    <div className="bg-base-100 border-b border-base-200 px-4 py-3 animate-fade-in">
      <div className="flex items-center gap-3 mb-2">
        {isStreaming && (
          <div className="relative w-4 h-4">
            <svg className="w-4 h-4 text-primary animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </div>
        )}
        <p className="text-[11px] font-bold text-base-content uppercase tracking-widest">
          Triaging Inbox
        </p>
        <span className="text-[10px] text-base-content/60 ml-auto">
          {completedEmails} of {totalEmails}
        </span>
      </div>

      <div className="flex gap-2 items-center">
        <div className="flex-1 h-1.5 bg-base-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className="text-[9px] text-base-content/60 font-mono min-w-fit">
          {Math.round(percentage)}%
        </span>
      </div>

      <p className="text-[9px] text-base-content/60 mt-2">
        {isStreaming ? 'Processing emails with 5 workers...' : 'Triage complete'}
      </p>
    </div>
  );
}
