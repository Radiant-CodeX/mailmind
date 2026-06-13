import React from 'react';
import { CommitmentItem as TypeCommitment, CalendarEvent } from '../../lib/types';
import { ConflictBadge } from './ConflictBadge';

interface CommitmentItemProps {
  item: TypeCommitment;
  onToggle: () => void;
  conflict: CalendarEvent | null;
}

export function CommitmentItem({ item, onToggle, conflict }: CommitmentItemProps) {
  const getDeadlineDetails = (dlStr: string | null) => {
    if (!dlStr) return null;
    try {
      const dl = new Date(dlStr);
      const now = new Date();
      
      const formatted = dl.toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      // Reset hours to compare dates only
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
      const dlDate = new Date(dl.getFullYear(), dl.getMonth(), dl.getDate()).getTime();
      
      return {
        text: formatted,
        isUrgent: dlDate <= today,
      };
    } catch {
      return null;
    }
  };

  const dlInfo = getDeadlineDetails(item.deadline);

  return (
    <div
      className={`p-3 bg-base-100 border rounded-lg flex items-start justify-between gap-3 transition-all duration-200 ${
        item.confirmed
          ? 'border-emerald-500/30 bg-emerald-500/5'
          : item.approved
          ? 'border-primary/40 bg-primary/5'
          : 'border-base-200 hover:border-base-300'
      }`}
      id={`commitment-item-${item.id}`}
    >
      <div className="flex items-start gap-2.5 flex-1 min-w-0">
        {/* Checkbox / Confirmed Green Check */}
        {item.confirmed ? (
          <div className="mt-1 w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center text-base-200 shrink-0 shadow-sm animate-scale-in">
            <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          </div>
        ) : (
          <input
            type="checkbox"
            checked={!!item.approved}
            onChange={onToggle}
            className="mt-1 w-4 h-4 rounded bg-base-200 border-base-300 text-primary focus:ring-primary cursor-pointer"
          />
        )}

        <div className="flex-1 min-w-0 text-left">
          <p className={`text-xs leading-relaxed break-words font-medium ${
            item.confirmed ? 'text-base-content/75 line-through font-normal' : item.approved ? 'text-base-content font-semibold' : 'text-base-content/80'
          }`}>
            {item.commitment}
          </p>

          <div className="flex flex-wrap items-center gap-2 mt-2">
            {/* Confidence Badge */}
            <span className="px-1 py-0.5 rounded bg-base-200 border border-base-300 text-[9px] font-mono text-base-content/60">
              {Math.round(item.confidence * 100)}% confidence
            </span>

            {/* Deadline */}
            {dlInfo && (
              <span className={`text-[9px] font-semibold flex items-center gap-1 ${
                dlInfo.isUrgent ? 'text-red-500 dark:text-red-400 font-bold' : 'text-emerald-500 dark:text-emerald-400 font-semibold'
              }`}>
                <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {dlInfo.text}
              </span>
            )}

            {/* Confirmation Links */}
            {item.confirmed && (
              <div className="flex gap-2 ml-1">
                {item.task_url && (
                  <a
                    href={item.task_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[9px] text-primary hover:underline flex items-center gap-0.5 font-bold uppercase tracking-wider"
                  >
                    View Task
                  </a>
                )}
                {item.event_url && (
                  <a
                    href={item.event_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[9px] text-emerald-500 hover:underline flex items-center gap-0.5 font-bold uppercase tracking-wider"
                  >
                    View Event
                  </a>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Conflict Warning icon */}
      <ConflictBadge conflict={conflict} />
    </div>
  );
}
