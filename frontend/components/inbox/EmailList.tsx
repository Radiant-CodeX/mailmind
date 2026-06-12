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
  // Streaming triage progress
  isStreaming?: boolean;
  triageProgress?: number;
}

export function EmailList({
  emails,
  selectedEmailId,
  onSelectEmail,
  searchQuery,
  onSearchChange,
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
  isStreaming = false,
  triageProgress = 0,
}: EmailListProps) {
  // Archive/spam/read actions only make sense in the standard mail folders.
  const showActions = !['Trash', 'Sent', 'Drafts', 'Spam'].includes(activeFolder);
  return (
    <div 
      className={`${
        isFullWidth ? 'flex-1' : 'w-[320px] shrink-0 border-r border-[var(--border)]'
      } bg-[var(--bg-surface)] flex flex-col h-full overflow-hidden`}
      id="email-list"
    >
      {/* Live triage streaming progress */}
      {(isStreaming || triageProgress > 0) && (
        <TriageStreamingPanel
          totalEmails={emails.length}
          isStreaming={isStreaming}
          completedEmails={triageProgress}
        />
      )}

      {/* Header and counter */}
      <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2 uppercase tracking-wide">
          {activeFolder}
        </h2>
        <div className="flex items-center gap-1.5">
          {filters && onFiltersChange && <FilterMenu value={filters} onChange={onFiltersChange} />}
          {onSortChange && <SortMenu value={sortKey} onChange={onSortChange} />}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className={`p-1.5 rounded-full hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all ${
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
              <span className="text-[11px] font-medium text-[var(--text-muted)] tabular-nums whitespace-nowrap px-1">
                {pageIndex * pageSize + (emails.length ? 1 : 0)}–{pageIndex * pageSize + emails.length} of {total.toLocaleString()}
              </span>
              <button
                onClick={onPrevPage}
                disabled={!hasPrevPage || loading}
                className="p-1 rounded-md hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
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
                className="p-1 rounded-md hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
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

      {/* Search Input */}
      <div className="p-3 bg-[var(--bg-surface)] border-b border-[var(--border-subtle)]">
        <div className="relative">
          <input
            type="text"
            placeholder="Search email body, sender..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border)] text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)] transition-all font-medium"
            id="inbox-search"
          />
          <div className="absolute left-2.5 top-2.5 text-[var(--text-muted)] pointer-events-none">
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        </div>
      </div>

      {/* Email List container */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading && emails.length === 0 ? (
          <EmailListSkeleton />
        ) : emails.length === 0 ? (
          <div className="p-8 text-center text-[var(--text-muted)] text-xs">
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
              isFullWidth={isFullWidth}
              triageApplies={['Inbox', 'Starred', 'Important'].includes(activeFolder)}
            />
          ))
        )}
      </div>
    </div>
  );
}
