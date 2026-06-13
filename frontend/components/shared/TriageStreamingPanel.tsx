'use client';

import React, { useEffect, useState } from 'react';

interface TriageStreamingPanelProps {
  /** Emails still being LLM-triaged right now (cache hits excluded). */
  count: number;
  /** Total LLM triage jobs in this batch. */
  total: number;
  /** How many have completed so far. */
  done: number;
}

export function TriageStreamingPanel({ count, total, done }: TriageStreamingPanelProps) {
  const [visible, setVisible] = useState(false);

  // Fade in when work starts, linger briefly then fade out when done.
  useEffect(() => {
    if (count > 0 || (total > 0 && done < total)) {
      setVisible(true);
    } else if (total > 0 && done >= total) {
      // Keep visible for 1.2s after completion so the 100% bar is seen.
      const t = setTimeout(() => setVisible(false), 1200);
      return () => clearTimeout(t);
    }
  }, [count, total, done]);

  if (!visible && count <= 0) return null;

  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const isDone = total > 0 && done >= total;

  return (
    <div
      className={`border-b border-base-200 px-4 py-3 transition-all duration-300 ${
        isDone ? 'bg-success/5' : 'bg-primary/5'
      }`}
    >
      {/* Top row: icon + label + count badge */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {isDone ? (
            <svg className="w-3.5 h-3.5 text-success shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5 text-primary animate-spin shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          <span className={`text-[11px] font-bold ${isDone ? 'text-success' : 'text-base-content'}`}>
            {isDone
              ? `Triage complete — ${total} ${total === 1 ? 'email' : 'emails'} scored`
              : `Triaging ${count} ${count === 1 ? 'email' : 'emails'}…`}
          </span>
        </div>

        {/* Fraction counter */}
        {total > 0 && (
          <span className="text-[10px] font-mono text-base-content/40 tabular-nums">
            {done}/{total}
          </span>
        )}
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="relative h-1.5 rounded-full bg-base-300 overflow-hidden">
          <div
            className={`absolute inset-y-0 left-0 rounded-full transition-all duration-300 ease-out ${
              isDone ? 'bg-success' : 'bg-primary'
            }`}
            style={{ width: `${pct}%` }}
          />
          {/* Shimmer on the leading edge while in progress */}
          {!isDone && pct > 0 && (
            <div
              className="absolute inset-y-0 w-8 rounded-full bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer-slide"
              style={{ left: `calc(${pct}% - 1rem)` }}
            />
          )}
        </div>
      )}

      {/* Dot-pulse skeleton while waiting for to_triage meta (total not known yet) */}
      {total === 0 && !isDone && (
        <div className="flex gap-1 mt-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="inline-block w-1.5 h-1.5 rounded-full bg-primary/40 animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
