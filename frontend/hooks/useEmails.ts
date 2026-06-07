'use client';

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { Email } from '../lib/types';
import {
  fetchMailbox,
  triageEmailsBatch,
  moveEmailToTrash,
  restoreEmailFromTrash,
  markEmailRead,
  archiveEmail as apiArchiveEmail,
  reportSpam as apiReportSpam,
} from '../lib/api';

// Persistent triage-score cache (by email id) so refreshes/page revisits don't
// re-run the NLP classifier. Capped to avoid unbounded growth.
const TRIAGE_CACHE_KEY = 'mailmind_triage_cache';
type TriageLite = NonNullable<Email['triage']>;

function readTriageCache(): Record<string, TriageLite> {
  if (typeof window === 'undefined') return {};
  try { return JSON.parse(localStorage.getItem(TRIAGE_CACHE_KEY) || '{}'); } catch { return {}; }
}

function writeTriageCache(entries: Record<string, { composite_score: number }>): void {
  if (typeof window === 'undefined') return;
  try {
    const merged = { ...readTriageCache(), ...entries } as Record<string, TriageLite>;
    const keys = Object.keys(merged);
    // Keep the cache bounded (most-recent ~1000 entries).
    const trimmed = keys.length > 1000
      ? Object.fromEntries(keys.slice(keys.length - 1000).map((k) => [k, merged[k]]))
      : merged;
    localStorage.setItem(TRIAGE_CACHE_KEY, JSON.stringify(trimmed));
  } catch {}
}

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
  is_read?: boolean;
  has_attachments?: boolean;
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
export type DateRange = 'all' | 'today' | 'week' | 'month';

export interface MailFilters {
  dateRange: DateRange;
  unreadOnly: boolean;
  attachmentsOnly: boolean;
}

export const DEFAULT_FILTERS: MailFilters = { dateRange: 'all', unreadOnly: false, attachmentsOnly: false };

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

  const [filters, setFilters] = useState<MailFilters>(DEFAULT_FILTERS);

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
  // Pagination state (50 per page, cursor-based via next_page_token).
  // --------------------------------------------------------------------------
  const PAGE_SIZE = 50;
  const [total, setTotal] = useState(0);
  const [pageIndex, setPageIndex] = useState(0); // 0-based
  const nextTokenRef = useRef<string | null>(null);
  const tokenStackRef = useRef<(string | null)[]>([null]);
  const lastFolderRef = useRef<string | null>(null);
  const searchRef = useRef('');
  useEffect(() => { searchRef.current = searchQuery; }, [searchQuery]);

  const folderParam = (f: string) =>
    (['Inbox', 'Starred', 'Important'].includes(f) ? 'inbox' : f.toLowerCase());

  // Fetch a single page (token=null → first page). `silent` skips the spinner
  // for background auto-refresh.
  const loadPage = useCallback(async (token: string | null, silent = false) => {
    if (!enabled) return;
    if (!silent) setLoading(true);
    setError(null);
    try {
      const page = await fetchMailbox(folderParam(activeFolder), PAGE_SIZE, token, searchRef.current);
      const raw = (page.emails || []) as unknown as RawEmail[];
      // Reuse any triage scores we've already computed (avoids re-scoring on
      // every refresh / page revisit).
      const tcache = readTriageCache();
      const mapped: Email[] = raw.map((e) => {
        const id = e.email_id || e.id || '';
        const cachedT = tcache[id];
        return {
          id,
          sender: e.sender,
          subject: e.subject,
          body: e.body,
          received_at: e.received_at,
          composite_score: cachedT ? Math.round(cachedT.composite_score) : (e.composite_score || 0),
          triage: e.triage || cachedT,
          isRead: e.is_read ?? true,
          hasAttachments: e.has_attachments ?? false,
        };
      });
      setEmails(mapped);
      setTotal(page.total || mapped.length);
      nextTokenRef.current = page.next_page_token;
      if (token === null) {
        localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(mapped));
      }
      setSelectedEmailId((prev) => (prev && mapped.some((e) => e.id === prev) ? prev : null));

      // Triage only the un-scored emails — in ONE batch request, not N.
      if (['Inbox', 'Starred', 'Important'].includes(activeFolder)) {
        const todo = mapped.filter((e) => !e.triage);
        if (todo.length > 0) {
          try {
            const scores = (await triageEmailsBatch(todo.map((e) => ({
              email_id: e.id, sender: e.sender, subject: e.subject,
              body: e.body, received_at: e.received_at,
            })))) as TriageLite[];
            const byId: Record<string, TriageLite> = {};
            todo.forEach((e, i) => { if (scores[i]) byId[e.id] = scores[i]; });
            writeTriageCache(byId);
            setEmails((prev) => prev.map((e) =>
              byId[e.id] ? { ...e, composite_score: Math.round(byId[e.id].composite_score), triage: byId[e.id] } : e));
          } catch (e) {
            console.warn('Batch triage failed', e);
          }
        }
      }
    } catch (err: unknown) {
      console.error('Failed to sync emails from backend', err);
      setError(err instanceof Error ? err.message : 'Failed to sync emails');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [activeFolder, enabled, setEmails]);

  // Reload from page 0 (used on folder switch, refresh, and search).
  const loadEmails = useCallback(async () => {
    if (!enabled) return;
    if (lastFolderRef.current !== activeFolder) {
      lastFolderRef.current = activeFolder;
      setSelectedEmailId(null);
      const cached = readCachedEmails(activeFolder);
      if (cached) setEmails(cached); // instant paint while page loads
    }
    tokenStackRef.current = [null];
    setPageIndex(0);
    await loadPage(null);
  }, [activeFolder, enabled, loadPage, setEmails]);

  const nextPage = useCallback(() => {
    const t = nextTokenRef.current;
    if (!t) return;
    tokenStackRef.current.push(t);
    setPageIndex((i) => i + 1);
    loadPage(t);
  }, [loadPage]);

  const prevPage = useCallback(() => {
    if (tokenStackRef.current.length <= 1) return;
    tokenStackRef.current.pop();
    const t = tokenStackRef.current[tokenStackRef.current.length - 1];
    setPageIndex((i) => Math.max(0, i - 1));
    loadPage(t);
  }, [loadPage]);

  const hasNextPage = (pageIndex + 1) * PAGE_SIZE < total;
  const hasPrevPage = pageIndex > 0;

  // Reload on folder change.
  useEffect(() => {
    const id = setTimeout(loadEmails, 0);
    return () => clearTimeout(id);
  }, [loadEmails]);

  // Debounced server-side search: reload page 0 when the query changes.
  useEffect(() => {
    const id = setTimeout(() => { if (enabled) loadEmails(); }, 400);
    return () => clearTimeout(id);
  }, [searchQuery, enabled, loadEmails]);

  // Auto-refresh the CURRENT page every 30s (silent — no spinner, no page jump).
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => {
      const token = tokenStackRef.current[tokenStackRef.current.length - 1];
      loadPage(token, true);
    }, 30000);
    return () => clearInterval(id);
  }, [enabled, loadPage]);

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
  // Mark read / unread, archive, report spam
  // --------------------------------------------------------------------------
  const persist = useCallback((list: Email[]) => {
    localStorage.setItem(`mailmind_emails_${activeFolder}`, JSON.stringify(list));
  }, [activeFolder]);

  const markRead = useCallback(async (emailId: string, read: boolean) => {
    setEmails((prev) => {
      const next = prev.map((e) => (e.id === emailId ? { ...e, isRead: read } : e));
      persist(next);
      return next;
    });
    try {
      await markEmailRead(emailId, read);
    } catch (err) {
      console.error(`Failed to mark ${read ? 'read' : 'unread'}`, err);
    }
  }, [setEmails, persist]);

  const removeFrom = useCallback((emailId: string) => {
    setEmails((prev) => {
      const next = prev.filter((e) => e.id !== emailId);
      persist(next);
      return next;
    });
    setSelectedEmailId((prev) => (prev === emailId ? null : prev));
  }, [setEmails, persist]);

  const archiveEmail = useCallback(async (emailId: string) => {
    removeFrom(emailId);
    localStorage.removeItem('mailmind_emails_Archive');
    try {
      await apiArchiveEmail(emailId);
    } catch (err) {
      console.error(`Failed to archive ${emailId}`, err);
      loadEmails();
    }
  }, [removeFrom, loadEmails]);

  const reportSpam = useCallback(async (emailId: string) => {
    removeFrom(emailId);
    localStorage.removeItem('mailmind_emails_Spam');
    try {
      await apiReportSpam(emailId);
    } catch (err) {
      console.error(`Failed to report spam ${emailId}`, err);
      loadEmails();
    }
  }, [removeFrom, loadEmails]);

  // --------------------------------------------------------------------------
  // Derived lists
  // --------------------------------------------------------------------------
  const filteredAndSortedEmails = useMemo(() => {
    let list = emails.map((e) => ({ ...e, isStarred: starredIds.has(e.id) }));
    if (activeFolder === 'Starred') list = list.filter((e) => e.isStarred);
    else if (activeFolder === 'Important') list = list.filter((e) => (e.composite_score || 0) >= 50);

    // Note: text search is handled server-side (server-wide), so no client
    // text filter here — only the structured filters below.

    // Advanced filters: read-status, attachments, date range.
    if (filters.unreadOnly) list = list.filter((e) => e.isRead === false);
    if (filters.attachmentsOnly) list = list.filter((e) => e.hasAttachments === true);
    if (filters.dateRange !== 'all') {
      // Date filtering inherently needs the current time; safe to read here.
      // eslint-disable-next-line react-hooks/purity
      const now = Date.now();
      const windows: Record<DateRange, number> = {
        all: Infinity,
        today: 24 * 60 * 60 * 1000,
        week: 7 * 24 * 60 * 60 * 1000,
        month: 30 * 24 * 60 * 60 * 1000,
      };
      const cutoff = now - windows[filters.dateRange];
      list = list.filter((e) => {
        const t = new Date(e.received_at).getTime();
        return Number.isNaN(t) ? true : t >= cutoff;
      });
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
  }, [emails, activeFolder, starredIds, sortKey, filters]);

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
    filters,
    setFilters,
    // Pagination
    total,
    pageIndex,
    pageSize: PAGE_SIZE,
    hasNextPage,
    hasPrevPage,
    nextPage,
    prevPage,
    loading,
    error,
    refresh: loadEmails,
    toggleStar,
    trashEmail,
    undoTrash,
    dismissTrashToast,
    pendingTrash,
    restoreEmail,
    markRead,
    archiveEmail,
    reportSpam,
  };
}
