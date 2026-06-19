import React from 'react';
import { Email } from '../../lib/types';
import { EmailListItem } from './EmailListItem';
import { EmailListSkeleton } from './EmailListSkeleton';
import { SortMenu } from './SortMenu';
import { FilterMenu } from './FilterMenu';
import { TriageStreamingPanel } from '../shared/TriageStreamingPanel';
import { SortKey, MailFilters } from '../../hooks/useEmails';

interface EmailListProps {
  emails: Email[];
  selectedEmailId: string | null;
  onSelectEmail: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  /** Priority distribution shown as chips where the search bar used to be. */
  priorityCounts?: { CRITICAL: number; HIGH: number; MEDIUM: number; LOW: number };
  sortKey?: SortKey;
  onSortChange?: (key: SortKey) => void;
  filters?: MailFilters;
  onFiltersChange?: (f: MailFilters) => void;
  total?: number;
  pageIndex?: number;
  pageSize?: number;
  hasNextPage?: boolean;
  hasPrevPage?: boolean;
  onNextPage?: () => void;
  onPrevPage?: () => void;
  loading?: boolean;
  onRefresh?: () => void;
  isFullWidth?: boolean;
  activeFolder?: string;
  onToggleStar: (id: string) => void;
  onTrashEmail?: (id: string) => void;
  onRestoreEmail?: (id: string) => void;
  onArchiveEmail?: (id: string) => void;
  onReportSpam?: (id: string) => void;
  onToggleRead?: (id: string, read: boolean) => void;
  onMarkDone?: (id: string, sender: string, priority?: string) => void;
  onOverridePriority?: (id: string, sender: string, priority: import('./PriorityOverrideMenu').OverridePriority, current: import('../../lib/types').Priority) => void;
  doneEmailIds?: Set<string>;
  // Streaming triage progress
  isStreaming?: boolean;
  triageProgress?: number;
  /** Emails actively being LLM-triaged (cache hits excluded). */
  triageActive?: number;
  /** Total LLM triage jobs in this batch (from to_triage meta event). */
  triageTotal?: number;
}

export function EmailList({
  emails,
  selectedEmailId,
  onSelectEmail,
  searchQuery,
  onSearchChange,
  priorityCounts,
  sortKey = 'normal',
  onSortChange,
  filters,
  onFiltersChange,
  total = 0,
  pageIndex = 0,
  pageSize = 50,
  hasNextPage = false,
  hasPrevPage = false,
  onNextPage,
  onPrevPage,
  loading = false,
  onRefresh,
  isFullWidth = false,
  activeFolder = 'Inbox',
  onToggleStar,
  onTrashEmail,
  onRestoreEmail,
  onArchiveEmail,
  onReportSpam,
  onToggleRead,
  onMarkDone,
  onOverridePriority,
  doneEmailIds,
  isStreaming = false,
  triageProgress = 0,
  triageActive = 0,
  triageTotal = 0,
}: EmailListProps) {
  // Archive/spam/read actions only make sense in the standard mail folders.
  const showActions = !['Trash', 'Sent', 'Drafts', 'Spam'].includes(activeFolder);
  return (
    <div 
      className={`${
        isFullWidth ? 'flex-1' : 'w-[320px] shrink-0 border-r border-base-300'
      } bg-base-100 flex flex-col h-full overflow-hidden`}
      id="email-list"
    >
      {/* Live triage streaming progress — counts only real LLM triage work */}
      <TriageStreamingPanel streaming={isStreaming} count={triageActive} total={triageTotal} done={triageProgress} />

      {/* Header and counter */}
      <div className="p-4 border-b border-base-200 flex items-center justify-between">
        <h2 className="text-sm font-bold text-base-content flex items-center gap-2 uppercase tracking-wide">
          {activeFolder}
        </h2>
        <div className="flex items-center gap-1.5">
          {filters && onFiltersChange && <FilterMenu value={filters} onChange={onFiltersChange} />}
          {onSortChange && <SortMenu value={sortKey} onChange={onSortChange} />}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className={`p-1.5 rounded-full hover:bg-base-200 text-base-content/60 hover:text-base-content transition-all ${
                loading ? 'cursor-not-allowed' : 'cursor-pointer'
              }`}
              title="Refresh"
              id="btn-sync-emails"
            >
              {/* Gmail-style circular reload (single curved arrow) */}
              <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M17.65 6.35A7.958 7.958 0 0 0 12 4a8 8 0 1 0 8 8h-2a6 6 0 1 1-6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
              </svg>
            </button>
          )}

          {/* Gmail-style pagination: "1–50 of N" with prev/next */}
          {total > 0 && (
            <div className="flex items-center gap-0.5 ml-1">
              <span className="text-[11px] font-medium text-base-content/60 tabular-nums whitespace-nowrap px-1">
                {pageIndex * pageSize + (emails.length ? 1 : 0)}–{pageIndex * pageSize + emails.length} of {total.toLocaleString()}
              </span>
              <button
                onClick={onPrevPage}
                disabled={!hasPrevPage || loading}
                className="p-1 rounded-md hover:bg-base-200 text-base-content/60 hover:text-base-content transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                title="Newer"
                id="btn-prev-page"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <button
                onClick={onNextPage}
                disabled={!hasNextPage || loading}
                className="p-1 rounded-md hover:bg-base-200 text-base-content/60 hover:text-base-content transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                title="Older"
                id="btn-next-page"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Priority distribution — replaced the search bar. Shows how many of the
          loaded emails fall into each triage priority. */}
      {priorityCounts && (
        <div className="p-3 bg-base-100 border-b border-base-200">
          <div className="flex items-center gap-2">
            {([
              { key: 'CRITICAL', label: 'Critical', dot: 'bg-red-500', text: 'text-red-500', ring: 'border-red-500/20 bg-red-500/5' },
              { key: 'HIGH', label: 'High', dot: 'bg-orange-500', text: 'text-orange-500', ring: 'border-orange-500/20 bg-orange-500/5' },
              { key: 'MEDIUM', label: 'Medium', dot: 'bg-amber-500', text: 'text-amber-500', ring: 'border-amber-500/20 bg-amber-500/5' },
              { key: 'LOW', label: 'Low', dot: 'bg-slate-400', text: 'text-slate-400', ring: 'border-slate-400/20 bg-slate-400/5' },
            ] as const).map((p) => (
              <div
                key={p.key}
                className={`flex-1 flex items-center justify-between gap-1.5 px-2.5 py-1.5 rounded-lg border ${p.ring}`}
                title={`${priorityCounts[p.key]} ${p.label} ${priorityCounts[p.key] === 1 ? 'email' : 'emails'}`}
              >
                <span className="flex items-center gap-1.5 min-w-0">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${p.dot}`} />
                  <span className="text-[10px] font-bold uppercase tracking-wide text-base-content/60 truncate">{p.label}</span>
                </span>
                <span className={`text-xs font-extrabold tabular-nums ${p.text}`}>{priorityCounts[p.key]}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Email List container */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading && emails.length === 0 ? (
          <EmailListSkeleton />
        ) : emails.length === 0 ? (
          <div className="p-8 text-center text-base-content/60 text-xs">
            No emails found
          </div>
        ) : (
          emails.map((email) => (
            <EmailListItem
              key={email.id}
              email={email}
              isSelected={email.id === selectedEmailId}
              onClick={() => onSelectEmail(email.id)}
              onToggleStar={onToggleStar}
              onTrash={activeFolder !== 'Trash' ? onTrashEmail : undefined}
              onRestore={activeFolder === 'Trash' ? onRestoreEmail : undefined}
              onArchive={showActions ? onArchiveEmail : undefined}
              onSpam={showActions ? onReportSpam : undefined}
              onToggleRead={showActions ? onToggleRead : undefined}
              onMarkDone={showActions ? onMarkDone : undefined}
              onOverridePriority={showActions ? onOverridePriority : undefined}
              isDone={doneEmailIds?.has(email.id)}
              isFullWidth={isFullWidth}
              triageApplies={['Inbox', 'Starred', 'Important'].includes(activeFolder)}
            />
          ))
        )}
      </div>
    </div>
  );
}
