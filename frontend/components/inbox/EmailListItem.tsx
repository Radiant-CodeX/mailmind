import React from 'react';
import { Email, Priority } from '../../lib/types';
import { PriorityBadge } from './PriorityBadge';
import { PriorityOverrideMenu, OverridePriority } from './PriorityOverrideMenu';

interface EmailListItemProps {
  email: Email;
  isSelected: boolean;
  onClick: () => void;
  onToggleStar: (id: string) => void;
  onTrash?: (id: string) => void;
  onRestore?: (id: string) => void;
  onArchive?: (id: string) => void;
  onSpam?: (id: string) => void;
  onToggleRead?: (id: string, read: boolean) => void;
  onMarkDone?: (id: string, sender: string, priority?: string) => void;
  onOverridePriority?: (id: string, sender: string, priority: OverridePriority, current: Priority) => void;
  isFullWidth: boolean;
  /** Whether triage scoring applies to this folder (false for Sent/Drafts/etc). */
  triageApplies?: boolean;
  isDone?: boolean;
}

export function EmailListItem({ email, isSelected, onClick, onToggleStar, onTrash, onRestore, onArchive, onSpam, onToggleRead, onMarkDone, onOverridePriority, isFullWidth, triageApplies = true, isDone = false }: EmailListItemProps) {
  const isUnread = email.isRead === false;
  // Triage score is still being computed when the folder uses triage but this
  // email has no triage object yet — show a shimmer instead of a misleading 0.
  const scorePending = triageApplies && !email.triage;

  const ReadButton = onToggleRead ? (
    <button
      onClick={(e) => { e.stopPropagation(); onToggleRead(email.id, isUnread); }}
      className="p-1 rounded-md text-base-content/60 hover:bg-base-200 hover:text-primary transition-all cursor-pointer"
      title={isUnread ? 'Mark as read' : 'Mark as unread'}
      id={`btn-read-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {isUnread
          ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />}
      </svg>
    </button>
  ) : null;

  const ArchiveButton = onArchive ? (
    <button
      onClick={(e) => { e.stopPropagation(); onArchive(email.id); }}
      className="p-1 rounded-md text-base-content/60 hover:bg-amber-500/10 hover:text-amber-500 transition-all cursor-pointer"
      title="Archive" id={`btn-archive-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
      </svg>
    </button>
  ) : null;

  const SpamButton = onSpam ? (
    <button
      onClick={(e) => { e.stopPropagation(); onSpam(email.id); }}
      className="p-1 rounded-md text-base-content/60 hover:bg-red-500/10 hover:text-red-500 transition-all cursor-pointer"
      title="Report spam" id={`btn-spam-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
      </svg>
    </button>
  ) : null;
  // Restore button — shown only inside Trash folder
  const RestoreButton = onRestore ? (
    <button
      onClick={(e) => { e.stopPropagation(); onRestore(email.id); }}
      className="p-1 rounded-md hover:bg-emerald-500/10 text-base-content/60 hover:text-emerald-500 transition-all cursor-pointer"
      title="Restore to Inbox"
      id={`btn-restore-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
      </svg>
    </button>
  ) : null;

  const DoneButton = onMarkDone && !isDone ? (
    <button
      onClick={(e) => { e.stopPropagation(); onMarkDone(email.id, email.sender ?? '', email.triage?.priority); }}
      className="p-1 rounded-md text-base-content/60 hover:bg-emerald-500/10 hover:text-emerald-500 transition-all cursor-pointer"
      title="Mark as Done"
      id={`btn-done-${email.id}`}
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </button>
  ) : null;

  const TrashButton = onTrash ? (
    <button
      onClick={(e) => { e.stopPropagation(); onTrash(email.id); }}
      className="p-1 rounded-md hover:bg-red-500/10 text-base-content/60 hover:text-red-500 transition-all cursor-pointer"
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
        className={`p-4 border-b border-base-200 cursor-pointer transition-all duration-200 text-left select-none relative ${
          isSelected
            ? 'bg-base-200 border-l-4 border-l-primary'
            : 'hover:bg-base-200/40 bg-transparent'
        }`}
        id={`email-item-${email.id}`}
      >
        <div className="flex items-center justify-between gap-6 w-full">
          {/* 1. Leftmost column: unread dot + Sender */}
          <div className="w-[150px] shrink-0 overflow-hidden flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full shrink-0 ${isUnread ? 'bg-primary' : 'bg-transparent'}`} title={isUnread ? 'Unread' : 'Read'} />
            <div className="min-w-0">
              <span className={`text-xs truncate block ${
                isUnread ? 'text-base-content font-bold' : 'font-semibold text-base-content/80'
              }`} title={email.sender}>
                {email.sender.split('@')[0]}
              </span>
              <span className="text-[9px] text-base-content/60 font-mono block mt-0.5" suppressHydrationWarning>
                {formatTime(email.received_at)}
              </span>
            </div>
          </div>

          {/* 2. Middle column: Subject (+attachment) and snippet */}
          <div className="flex-1 min-w-0 pr-4">
            <h4 className={`text-xs truncate flex items-center gap-1.5 ${isUnread ? 'font-bold text-base-content' : 'font-semibold text-base-content'}`}>
              {email.hasAttachments && (
                <svg className="w-3 h-3 shrink-0 text-base-content/60" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-label="Has attachment">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
              <span className="truncate">{email.subject}</span>
            </h4>
            <p className="text-[11px] text-base-content/60 truncate mt-0.5 font-medium opacity-80">
              {email.body.replace(/\s+/g, ' ')}
            </p>
          </div>

          {/* 3. Rightmost column: Score, Priority, Star */}
          <div className="flex items-center gap-4 shrink-0">
            {isDone ? (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded font-mono bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" title="Done">✓ Done</span>
            ) : scorePending ? (
              <span className="w-7 h-4 rounded bg-base-200 animate-pulse" title="Scoring…" />
            ) : triageApplies && email.composite_score !== undefined && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${
                priority === 'CRITICAL' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
                priority === 'HIGH' ? 'bg-orange-500/10 text-orange-500 border border-orange-500/20' :
                priority === 'MEDIUM' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
                'bg-slate-500/10 text-slate-500 border border-slate-500/20'
              }`} title="Triage Score">
                {email.composite_score}
              </span>
            )}

            {!isDone && (scorePending ? (
              <span className="px-2 py-0.5 w-12 h-5 rounded bg-base-200 animate-pulse" title="Scoring…" />
            ) : triageApplies && (
              onOverridePriority ? (
                <PriorityOverrideMenu
                  current={priority}
                  onOverride={(p) => onOverridePriority(email.id, email.sender, p, priority)}
                >
                  <PriorityBadge priority={priority} />
                </PriorityOverrideMenu>
              ) : (
                <PriorityBadge priority={priority} />
              )
            ))}

            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleStar(email.id);
              }}
              className={`p-1 rounded-md hover:bg-base-200 transition-all cursor-pointer ${
                email.isStarred ? 'text-amber-400' : 'text-base-content/60 hover:text-base-content'
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

            {ReadButton}
            {DoneButton}
            {ArchiveButton}
            {SpamButton}
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
      className={`p-4 border-b border-base-200 cursor-pointer transition-all duration-200 text-left select-none relative ${
        isSelected
          ? 'bg-base-200 border-l-4 border-l-primary'
          : 'hover:bg-base-200/40 bg-transparent'
      }`}
      id={`email-item-${email.id}`}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className={`text-xs font-semibold truncate max-w-[150px] ${
          isSelected ? 'text-base-content font-bold' : 'text-base-content/80'
        }`}>
          {email.sender.split('@')[0]}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          {isDone ? (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded font-mono bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">✓</span>
          ) : scorePending ? (
            <span className="w-7 h-4 rounded bg-base-200 animate-pulse" title="Scoring…" />
          ) : triageApplies && email.composite_score !== undefined && (
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${
              priority === 'CRITICAL' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
              priority === 'HIGH' ? 'bg-orange-500/10 text-orange-500 border border-orange-500/20' :
              priority === 'MEDIUM' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
              'bg-slate-500/10 text-slate-500 border border-slate-500/20'
            }`}>
              {email.composite_score}
            </span>
          )}
          <span className="text-[10px] text-base-content/60 font-mono" suppressHydrationWarning>
            {formatTime(email.received_at)}
          </span>
        </div>
      </div>

      <h4 className="text-xs font-medium text-base-content truncate mb-2 pr-4">
        {email.subject}
      </h4>

      <div className="flex items-center justify-between gap-2">
        {isDone ? (
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded font-mono bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">✓ Done</span>
        ) : scorePending ? (
          <span className="px-2 py-0.5 w-12 h-5 rounded bg-base-200 animate-pulse" title="Scoring…" />
        ) : triageApplies ? (
          onOverridePriority ? (
            <PriorityOverrideMenu
              current={priority}
              onOverride={(p) => onOverridePriority(email.id, email.sender, p, priority)}
            >
              <PriorityBadge priority={priority} />
            </PriorityOverrideMenu>
          ) : (
            <PriorityBadge priority={priority} />
          )
        ) : null}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleStar(email.id);
          }}
          className={`p-1 rounded-md hover:bg-base-200 transition-all cursor-pointer ${
            email.isStarred ? 'text-amber-400' : 'text-base-content/60 hover:text-base-content'
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
        {DoneButton}
        {TrashButton}
        {RestoreButton}
      </div>
    </div>
  );
}
