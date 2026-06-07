import React from 'react';
import { Email, Priority } from '../../lib/types';
import { PriorityBadge } from './PriorityBadge';

interface EmailListItemProps {
  email: Email;
  isSelected: boolean;
  onClick: () => void;
  onToggleStar: (id: string) => void;
  onTrash?: (id: string) => void;
  onRestore?: (id: string) => void;
  isFullWidth: boolean;
}

export function EmailListItem({ email, isSelected, onClick, onToggleStar, onTrash, onRestore, isFullWidth }: EmailListItemProps) {
  // Restore button — shown only inside Trash folder
  const RestoreButton = onRestore ? (
    <button
      onClick={(e) => { e.stopPropagation(); onRestore(email.id); }}
      className="p-1 rounded-md hover:bg-emerald-500/10 text-[var(--text-muted)] hover:text-emerald-500 transition-all cursor-pointer"
      title="Restore to Inbox"
      id={`btn-restore-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
      </svg>
    </button>
  ) : null;

  const TrashButton = onTrash ? (
    <button
      onClick={(e) => { e.stopPropagation(); onTrash(email.id); }}
      className="p-1 rounded-md hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-500 transition-all cursor-pointer"
      title="Move to Trash"
      id={`btn-trash-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    </button>
  ) : null;

  // Map composite score to priority if triage object is not populated
  const getPriority = (score: number): Priority => {
    if (score >= 75) return 'CRITICAL';
    if (score >= 50) return 'HIGH';
    if (score >= 25) return 'MEDIUM';
    return 'LOW';
  };

  const priority = email.triage?.priority || getPriority(email.composite_score || 0);

  const [now, setNow] = React.useState<number | null>(null);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setNow(Date.now());
    }, 0);
    return () => clearTimeout(timer);
  }, []);

  // Format time (e.g. 10:14 AM or Yesterday)
  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      const currentNow = now || date.getTime();
      const diffMs = currentNow - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      
      if (diffMins < 60) {
        return `${diffMins}m ago`;
      }
      
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) {
        return `${diffHours}h ago`;
      }

      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  if (isFullWidth) {
    return (
      <div
        onClick={onClick}
        className={`p-4 border-b border-[var(--border-subtle)] cursor-pointer transition-all duration-200 text-left select-none relative ${
          isSelected
            ? 'bg-[var(--bg-elevated)] border-l-4 border-l-[var(--accent-primary)]'
            : 'hover:bg-[var(--bg-elevated)]/40 bg-transparent'
        }`}
        id={`email-item-${email.id}`}
      >
        <div className="flex items-center justify-between gap-6 w-full">
          {/* 1. Leftmost column: Mail ID / Sender */}
          <div className="w-[140px] shrink-0 overflow-hidden">
            <span className={`text-xs font-semibold truncate block ${
              isSelected ? 'text-[var(--text-primary)] font-bold' : 'text-[var(--text-primary)]/80'
            }`} title={email.sender}>
              {email.sender.split('@')[0]}
            </span>
            <span className="text-[9px] text-[var(--text-muted)] font-mono block mt-0.5" suppressHydrationWarning>
              {formatTime(email.received_at)}
            </span>
          </div>

          {/* 2. Middle column: Subject and snippet of body somewhat visible */}
          <div className="flex-1 min-w-0 pr-4">
            <h4 className="text-xs font-semibold text-[var(--text-primary)] truncate">
              {email.subject}
            </h4>
            <p className="text-[11px] text-[var(--text-muted)] truncate mt-0.5 font-medium opacity-80">
              {email.body.replace(/\s+/g, ' ')}
            </p>
          </div>

          {/* 3. Rightmost column: Score, Priority, Star */}
          <div className="flex items-center gap-4 shrink-0">
            {email.composite_score !== undefined && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${
                priority === 'CRITICAL' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
                priority === 'HIGH' ? 'bg-orange-500/10 text-orange-500 border border-orange-500/20' :
                priority === 'MEDIUM' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
                'bg-slate-500/10 text-slate-500 border border-slate-500/20'
              }`} title="Triage Score">
                {email.composite_score}
              </span>
            )}
            
            <PriorityBadge priority={priority} />

            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleStar(email.id);
              }}
              className={`p-1 rounded-md hover:bg-[var(--bg-elevated)] transition-all cursor-pointer ${
                email.isStarred ? 'text-amber-400' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
              title={email.isStarred ? 'Unstar email' : 'Star email'}
              id={`btn-star-${email.id}`}
            >
              <svg
                className="w-4 h-4"
                fill={email.isStarred ? 'currentColor' : 'none'}
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.245.588 1.81l-3.97 2.883a1 1 0 00-.364 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.971-2.883a1 1 0 00-1.18 0l-3.97 2.883c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.364-1.118l-3.97-2.883c-.772-.565-.373-1.81.588-1.81h4.906a1 1 0 00.951-.69l1.519-4.674z"
                />
              </svg>
            </button>

            {TrashButton}
            {RestoreButton}
          </div>
        </div>
      </div>
    );
  }

  // Collapsed / Stacked Mode (Sidebar Feed view)
  return (
    <div
      onClick={onClick}
      className={`p-4 border-b border-[var(--border-subtle)] cursor-pointer transition-all duration-200 text-left select-none relative ${
        isSelected
          ? 'bg-[var(--bg-elevated)] border-l-4 border-l-[var(--accent-primary)]'
          : 'hover:bg-[var(--bg-elevated)]/40 bg-transparent'
      }`}
      id={`email-item-${email.id}`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className={`text-xs font-semibold truncate max-w-[150px] ${
          isSelected ? 'text-[var(--text-primary)] font-bold' : 'text-[var(--text-primary)]/80'
        }`}>
          {email.sender.split('@')[0]}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          {email.composite_score !== undefined && (
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${
              priority === 'CRITICAL' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
              priority === 'HIGH' ? 'bg-orange-500/10 text-orange-500 border border-orange-500/20' :
              priority === 'MEDIUM' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
              'bg-slate-500/10 text-slate-500 border border-slate-500/20'
            }`}>
              {email.composite_score}
            </span>
          )}
          <span className="text-[10px] text-[var(--text-muted)] font-mono" suppressHydrationWarning>
            {formatTime(email.received_at)}
          </span>
        </div>
      </div>

      <h4 className="text-xs font-medium text-[var(--text-primary)] truncate mb-2 pr-4">
        {email.subject}
      </h4>

      <div className="flex items-center justify-between gap-2">
        <PriorityBadge priority={priority} />
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleStar(email.id);
          }}
          className={`p-1 rounded-md hover:bg-[var(--bg-elevated)] transition-all cursor-pointer ${
            email.isStarred ? 'text-amber-400' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
          }`}
          title={email.isStarred ? 'Unstar email' : 'Star email'}
          id={`btn-star-${email.id}`}
        >
          <svg
            className="w-4 h-4"
            fill={email.isStarred ? 'currentColor' : 'none'}
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.245.588 1.81l-3.97 2.883a1 1 0 00-.364 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.971-2.883a1 1 0 00-1.18 0l-3.97 2.883c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.364-1.118l-3.97-2.883c-.772-.565-.373-1.81.588-1.81h4.906a1 1 0 00.951-.69l1.519-4.674z"
            />
          </svg>
        </button>
        {TrashButton}
        {RestoreButton}
      </div>
    </div>
  );
}
