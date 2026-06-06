import React from 'react';
import { CalendarEvent } from '../../lib/types';

interface ConflictBadgeProps {
  conflict: CalendarEvent | null;
}

export function ConflictBadge({ conflict }: ConflictBadgeProps) {
  if (!conflict) return null;

  return (
    <div className="relative group inline-block shrink-0" id="conflict-badge">
      {/* Warning amber triangle */}
      <div className="text-[var(--accent-warning)] hover:text-[var(--text-primary)] cursor-help transition-all">
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
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>

      {/* Floating Tooltip card */}
      <div className="absolute right-0 bottom-6 hidden group-hover:block bg-[var(--bg-elevated)] border border-[var(--border)] rounded shadow-xl p-3 w-60 z-50 text-left pointer-events-none animate-fade-in">
        <h5 className="text-[10px] font-extrabold text-[var(--accent-warning)] uppercase tracking-wider mb-1">
          Calendar Conflict Detected
        </h5>
        <h6 className="text-xs font-semibold text-[var(--text-primary)] mb-1 truncate">
          {conflict.title}
        </h6>
        <p className="text-[10px] text-[var(--text-muted)] font-mono leading-tight">
          Timeslot: {new Date(conflict.start_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })} - {new Date(conflict.end_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  );
}
