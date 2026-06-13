import React from 'react';
import { CommitmentItem as TypeCommitment, CalendarEvent } from '../../lib/types';
import { CommitmentItem } from './CommitmentItem';
import { ConfirmButton } from './ConfirmButton';
import { LoadingSpinner } from '../shared/LoadingSpinner';
import { ErrorBanner } from '../shared/ErrorBanner';

interface CommitmentGateProps {
  commitments: TypeCommitment[];
  loading: boolean;
  error: string | null;
  confirming: boolean;
  confirmed: boolean;
  taskUrls: string[];
  eventUrls: string[];
  toggleCommitment: (id: string) => void;
  confirmSelected: () => void;
  checkConflict: (deadline: string | null) => CalendarEvent | null;
}

export function CommitmentGate({
  commitments,
  loading,
  error,
  confirming,
  confirmed,
  taskUrls,
  eventUrls,
  toggleCommitment,
  confirmSelected,
  checkConflict,
}: CommitmentGateProps) {
  const selectedCount = commitments.filter((c) => c.approved).length;

  return (
    <div className="text-left space-y-4" id="commitment-gate">
      {/* Main List Area */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-4">
            <LoadingSpinner message="Extracting commitments & matching natural language entities..." />
          </div>
        ) : error ? (
          <ErrorBanner message={error} />
        ) : confirmed ? (
          /* Success confirmed state */
          <div className="p-4 bg-base-200 border border-base-300 rounded-lg space-y-4 text-left animate-fade-in" id="commitments-confirmed">
            <div className="flex items-center gap-2 text-base-content">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs font-bold tracking-tight">Sync Completed Successfully</span>
            </div>
            <p className="text-[11px] text-base-content/60 leading-relaxed">
              Approved tasks have been synchronized. Access details via links below:
            </p>

            {taskUrls.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-base-200">
                <h4 className="text-[10px] font-bold text-base-content uppercase tracking-wider">MS To-Do Tasks</h4>
                {taskUrls.map((url, idx) => (
                  <a
                    key={idx}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[11px] text-primary hover:underline truncate max-w-full font-medium"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    View Synchronized Task #{idx + 1}
                  </a>
                ))}
              </div>
            )}

            {eventUrls.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-base-200">
                <h4 className="text-[10px] font-bold text-base-content uppercase tracking-wider">Calendar Events</h4>
                {eventUrls.map((url, idx) => (
                  <a
                    key={idx}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[11px] text-base-content hover:underline truncate max-w-full font-medium"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    View Calendar Event #{idx + 1}
                  </a>
                ))}
              </div>
            )}
          </div>
        ) : commitments.length === 0 ? (
          <div className="py-6 text-center text-xs text-base-content/60 font-medium">
            No commitments detected in email text.
          </div>
        ) : (
          commitments.map((c) => (
            <CommitmentItem
              key={c.id}
              item={c}
              onToggle={() => toggleCommitment(c.id)}
              conflict={checkConflict(c.deadline)}
            />
          ))
        )}
      </div>

      {/* Confirmation Drawer Bottom */}
      {!confirmed && commitments.length > 0 && (
        <div className="pt-4 border-t border-base-200">
          <ConfirmButton
            onClick={confirmSelected}
            disabled={selectedCount === 0}
            loading={confirming}
          />
          <p className="mt-2 text-[10px] text-center text-base-content/60 font-medium">
            Synchronizes {selectedCount} selected tasks with Microsoft Graph.
          </p>
        </div>
      )}
    </div>
  );
}
