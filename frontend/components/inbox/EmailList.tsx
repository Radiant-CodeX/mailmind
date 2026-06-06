import React from 'react';
import { Email } from '../../lib/types';
import { EmailListItem } from './EmailListItem';
import { SortMenu } from './SortMenu';
import { SortKey } from '../../hooks/useEmails';

interface EmailListProps {
  emails: Email[];
  selectedEmailId: string | null;
  onSelectEmail: (id: string) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortKey?: SortKey;
  onSortChange?: (key: SortKey) => void;
  loading?: boolean;
  onRefresh?: () => void;
  isFullWidth?: boolean;
  activeFolder?: string;
  onToggleStar: (id: string) => void;
  onTrashEmail?: (id: string) => void;
  onRestoreEmail?: (id: string) => void;
}

export function EmailList({
  emails,
  selectedEmailId,
  onSelectEmail,
  searchQuery,
  onSearchChange,
  sortKey = 'normal',
  onSortChange,
  loading = false,
  onRefresh,
  isFullWidth = false,
  activeFolder = 'Inbox',
  onToggleStar,
  onTrashEmail,
  onRestoreEmail,
}: EmailListProps) {
  return (
    <div 
      className={`${
        isFullWidth ? 'flex-1' : 'w-[320px] shrink-0 border-r border-[var(--border)]'
      } bg-[var(--bg-surface)] flex flex-col h-full overflow-hidden`}
      id="email-list"
    >
      {/* Header and counter */}
      <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2 uppercase tracking-wide">
          {activeFolder}
        </h2>
        <div className="flex items-center gap-2">
          {onSortChange && <SortMenu value={sortKey} onChange={onSortChange} />}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className={`p-1.5 rounded-md hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all ${
                loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
              }`}
              title="Sync Outlook Emails"
              id="btn-sync-emails"
            >
              <svg
                className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M21 20v-5h-.581m0 0a8.003 8.003 0 01-15.357-2"
                />
              </svg>
            </button>
          )}
          <span className="px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] border border-[var(--border)] text-[10px] font-bold text-[var(--text-primary)]">
            {emails.length}
          </span>
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
        {emails.length === 0 ? (
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
              isFullWidth={isFullWidth}
            />
          ))
        )}
      </div>
    </div>
  );
}
