import React from 'react';

/**
 * Placeholder shimmer rows shown while a folder's emails (and their triage
 * scores) are loading, so the list never appears blank during navigation.
 */
export function EmailListSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="animate-pulse" aria-hidden="true" data-testid="email-list-skeleton">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-subtle)]"
        >
          {/* Triage score circle placeholder */}
          <div className="w-9 h-9 rounded-full bg-[var(--bg-elevated)] shrink-0" />

          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center justify-between gap-3">
              {/* Sender */}
              <div className="h-3 rounded bg-[var(--bg-elevated)] w-32" />
              {/* Timestamp */}
              <div className="h-2.5 rounded bg-[var(--bg-elevated)] w-14" />
            </div>
            {/* Subject */}
            <div className="h-3 rounded bg-[var(--bg-elevated)] w-3/4" />
            {/* Preview */}
            <div className="h-2.5 rounded bg-[var(--bg-elevated)] w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}
