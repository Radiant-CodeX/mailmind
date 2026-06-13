'use client';

import React from 'react';

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
  // Only shown while actively triaging — disappears the moment it's done.
  if (!isStreaming) return null;

  const remaining = Math.max(0, totalEmails - completedEmails);

  return (
    <div className="bg-base-100 border-b border-base-200 px-4 py-2.5 animate-fade-in">
      <div className="flex items-center gap-2.5">
        <svg className="w-3.5 h-3.5 text-primary animate-spin shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        <p className="text-[11px] font-bold text-base-content">
          Triaging {remaining} {remaining === 1 ? 'email' : 'emails'}…
        </p>
      </div>
    </div>
  );
}
