'use client';

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { Email } from '../lib/types';
import {
  fetchEmails,
  triageEmail,
  fetchSentEmails,
  fetchDraftEmails,
  fetchSpamEmails,
  fetchTrashEmails,
  moveEmailToTrash,
  restoreEmailFromTrash,
} from '../lib/api';

function readCachedEmails(folder: string): Email[] | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(`mailmind_emails_${folder}`);
  if (!raw) return null;
  try { return JSON.parse(raw) as Email[]; } catch { return null; }
}

interface RawEmail {
  id?: string;
  email_id?: string;
  sender: string;
  subject: string;
  body: string;
  received_at: string;
  composite_score?: number;
  triage?: Email['triage'];
}

export interface PendingTrash {
  email: Email;
  /** ms timestamp when the trash was initiated — used by the toast countdown */
  startedAt: number;
}

/**
 * Email ordering modes surfaced in the list's sort menu.
 *  - normal      → backend order (Inbox = newest-received, as Outlook returns it)
 *  - date_*      → by received date/time
 *  - score_*     → by triage composite score
 */
export type SortKey = 'normal' | 'date_desc' | 'date_asc' | 'score_desc' | 'score_asc';

const SORT_STORAGE_KEY = 'mailmind_sort';

export function useEmails(activeFolder: string = 'Inbox', enabled: boolean = true) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [pendingTrash, setPendingTrash] = useState<PendingTrash | null>(null);
  // Lazy-init from the persisted preference (guarded for SSR).
  const [sortKey, setSortKeyState] = useState<SortKey>(() => {
    if (typeof window === 'undefined') return 'normal';
    return (localStorage.getItem(SORT_STORAGE_KEY) as SortKey) || 'normal';
  });

  const setSortKey = useCallback((key: SortKey) => {
    setSortKeyState(key);
    localStorage.setItem(SORT_STORAGE_KEY, key);
  }, []);

  // --------------------------------------------------------------------------
  // emails state — dual-write to a ref so trashEmail can read the current list
  // synchronously inside a callback without capturing a stale closure.
  // --------------------------------------------------------------------------
  const emailsRef = useRef<Email[]>([]);
  const [emails, setEmailsRaw] = useState<Email[]>([]);
  const setEmails = useCallback((updater: Email[] | ((prev: Email[]) => Email[])) => {
    setEmailsRaw((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      emailsRef.current = next;
      return next;
    });
  }, []);

  // --------------------------------------------------------------------------
  // Tracks the folder we last loaded, so we can clear the open detail view only
  // when the folder actually changes (not on a same-folder manual refresh).
  const lastFolderRef = useRef<string | null>(null);

  const loadEmails = useCallback(async () => {
    // Don't hit the API until the user is authenticated — avoids the
    // "Failed to fetch" / 401 error cascade on first paint.
    if (!enabled) return;
    if (lastFolderRef.current !== activeFolder) {
      lastFolderRef.current = activeFolder;
      setSelectedEmailId(null);
    }
    // Instant switch: show cached emails immediately, then refresh from network.
    const cached = readCachedEmails(activeFolder);
    if (cached) {
      setEmails(cached);
      setLoading(false);
    } else {
      setEmails([]);
      setLoading(true);
    }
    setError(null);

    try {
      let fetched: RawEmail[] = [];
      if (['Inbox', 'Starred', 'Important'].includes(activeFolder)) {
        fetched = await fetchEmails(10) as RawEmail[];
      } else if (activeFolder === 'Sent') {
        fetched = await fetchSentEmails(10) as RawEmail[];
      } else if (activeFolder === 'Drafts') {
        fetched = await fetchDraftEmails(10) as RawEmail[];
      } else if (activeFolder === 'Spam') {
        fetched = await fetchSpamEmails(10) as RawEmail[];
      } else if (activeFolder === 'Trash') {
        fetched = await fetchTrashEmails(10) as RawEmail[];
      }

      const cachedStr = localStorage.getItem(`mailmind_emails_${activeFolder}`);
      const cachedMap = new Map<string, Email>();
      if (cachedStr) {
        try {
          (JSON.parse(cachedStr) as Email[]).forEach((e) => cachedMap.set(e.id, e));
        } catch {}
      }

      const mapped: Email[] = fetched.map((e: RawEmail) => {
        const id = e.email_id || e.id || '';
        const hit = cachedMap.get(id);
        return {
          id,
          sender: e.sender,
          subject: e.subject,
          body: e.body,
          received_at: e.received_at,
          composite_score: e.composite_score || hit?.composite_score || 0,
          triage: e.triage || hit?.triage,
        };
      });

      setEmails(mapped);
      localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(mapped));
      setSelectedEmailId((prev) =>
        prev && mapped.some((e) => e.id === prev) ? prev : null
      );

      // Background triage for inbox-like folders
      if (['Inbox', 'Starred', 'Important'].includes(activeFolder)) {
        mapped.forEach(async (email) => {
          if (email.triage) return;
          try {
            const res = await triageEmail({
              email_id: email.id,
              sender: email.sender,
              subject: email.subject,
              body: email.body,
              received_at: email.received_at,
            });
            setEmails((prev) => {
              const updated = prev.map((e) =>
                e.id === email.id
                  ? { ...e, composite_score: Math.round(res.composite_score), triage: res }
                  : e
              );
              localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(updated));
              return updated;
            });
          } catch (e) {
            console.warn(`Failed to triage email ${email.id}`, e);
          }
        });
      }
    } catch (err: unknown) {
      console.error('Failed to sync emails from backend', err);
      setError(err instanceof Error ? err.message : 'Failed to sync emails');
    } finally {
      setLoading(false);
    }
  }, [activeFolder, enabled, setEmails]);

  // Reload whenever the folder changes (loadEmails handles clearing selection).
  // Deferred a tick so the state updates happen outside the effect body; the
  // cached paint inside loadEmails still lands before the browser paints.
  useEffect(() => {
    const id = setTimeout(loadEmails, 0);
    return () => clearTimeout(id);
  }, [loadEmails]);

  // --------------------------------------------------------------------------
  // Starred
  // --------------------------------------------------------------------------
  const [starredIds, setStarredIds] = useState<Set<string>>(new Set());
  const toggleStar = useCallback((emailId: string) => {
    setStarredIds((prev) => {
      const next = new Set(prev);
      if (next.has(emailId)) {
        next.delete(emailId);
      } else {
        next.add(emailId);
      }
      return next;
    });
  }, []);

  // --------------------------------------------------------------------------
  // Trash with 5-second undo window
  // API call is deferred; clicking Undo cancels it entirely.
  // --------------------------------------------------------------------------
  const trashTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear any pending trash timer on unmount so it never fires against a
  // dead component (avoids a stray API call + React state-update warning).
  useEffect(() => () => {
    if (trashTimerRef.current) clearTimeout(trashTimerRef.current);
  }, []);

  const trashEmail = useCallback(
    (emailId: string) => {
      const snapshot = emailsRef.current.find((e) => e.id === emailId);
      if (!snapshot) return;

      // Cancel any previous pending trash first (edge case: rapid clicks)
      if (trashTimerRef.current) {
        clearTimeout(trashTimerRef.current);
        trashTimerRef.current = null;
      }

      // Optimistic remove
      setEmails((prev) => {
        const next = prev.filter((e) => e.id !== emailId);
        localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(next));
        return next;
      });
      setSelectedEmailId((prev) => (prev === emailId ? null : prev));
      localStorage.removeItem('mailmind_emails_Trash');

      // Show toast with undo window
      setPendingTrash({ email: snapshot, startedAt: Date.now() });

      // Fire API after 5 s — cancelled if user hits Undo
      trashTimerRef.current = setTimeout(async () => {
        trashTimerRef.current = null;
        setPendingTrash(null);
        try {
          await moveEmailToTrash(emailId);
        } catch (err) {
          console.error(`Failed to move email ${emailId} to trash`, err);
          loadEmails();
        }
      }, 5000);
    },
    [activeFolder, setEmails, loadEmails]
  );

  const undoTrash = useCallback(() => {
    if (!pendingTrash) return;
    if (trashTimerRef.current) {
      clearTimeout(trashTimerRef.current);
      trashTimerRef.current = null;
    }
    const { email } = pendingTrash;
    setPendingTrash(null);
    // Re-insert the email into the current list
    setEmails((prev) => {
      const next = [...prev, email];
      localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(next));
      return next;
    });
  }, [pendingTrash, activeFolder, setEmails]);

  const dismissTrashToast = useCallback(() => {
    // Toast expired naturally — API call was already scheduled; just clear UI
    setPendingTrash(null);
  }, []);

  // --------------------------------------------------------------------------
  // Restore from Trash (for the Trash folder)
  // --------------------------------------------------------------------------
  const restoreEmail = useCallback(
    async (emailId: string) => {
      setEmails((prev) => {
        const next = prev.filter((e) => e.id !== emailId);
        localStorage.setItem('mailmind_emails_Trash', JSON.stringify(next));
        return next;
      });
      setSelectedEmailId((prev) => (prev === emailId ? null : prev));
      localStorage.removeItem('mailmind_emails_Inbox');
      try {
        await restoreEmailFromTrash(emailId);
      } catch (err) {
        console.error(`Failed to restore email ${emailId}`, err);
        loadEmails();
      }
    },
    [setEmails, loadEmails]
  );

  // --------------------------------------------------------------------------
  // Derived lists
  // --------------------------------------------------------------------------
  const filteredAndSortedEmails = useMemo(() => {
    let list = emails.map((e) => ({ ...e, isStarred: starredIds.has(e.id) }));
    if (activeFolder === 'Starred') list = list.filter((e) => e.isStarred);
    else if (activeFolder === 'Important') list = list.filter((e) => (e.composite_score || 0) >= 50);

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (e) =>
          e.sender.toLowerCase().includes(q) ||
          e.subject.toLowerCase().includes(q) ||
          e.body.toLowerCase().includes(q)
      );
    }

    const ts = (e: Email) => {
      const t = new Date(e.received_at).getTime();
      return Number.isNaN(t) ? 0 : t;
    };
    const score = (e: Email) => e.composite_score || 0;

    switch (sortKey) {
      case 'date_desc':
        return list.sort((a, b) => ts(b) - ts(a));
      case 'date_asc':
        return list.sort((a, b) => ts(a) - ts(b));
      case 'score_desc':
        return list.sort((a, b) => score(b) - score(a));
      case 'score_asc':
        return list.sort((a, b) => score(a) - score(b));
      case 'normal':
      default:
        // Preserve the backend's native ordering.
        return list;
    }
  }, [emails, searchQuery, activeFolder, starredIds, sortKey]);

  const selectedEmail = useMemo(() => {
    const list = emails.map((e) => ({ ...e, isStarred: starredIds.has(e.id) }));
    return list.find((e) => e.id === selectedEmailId) || null;
  }, [emails, selectedEmailId, starredIds]);

  return {
    emails: filteredAndSortedEmails,
    totalCount: emails.length,
    selectedEmail,
    selectedEmailId,
    setSelectedEmailId,
    searchQuery,
    setSearchQuery,
    sortKey,
    setSortKey,
    loading,
    error,
    refresh: loadEmails,
    toggleStar,
    trashEmail,
    undoTrash,
    dismissTrashToast,
    pendingTrash,
    restoreEmail,
  };
}
