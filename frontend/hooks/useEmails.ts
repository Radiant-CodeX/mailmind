'use client';

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { Email } from '../lib/types';
import {
  fetchMailbox,
  triageEmailsBatch,
  triagePageBatch,
  pollNewEmail,
  moveEmailToTrash,
  restoreEmailFromTrash,
  markEmailRead,
  archiveEmail as apiArchiveEmail,
  reportSpam as apiReportSpam,
} from '../lib/api';
import { userStorage } from '../lib/userStorage';

// Persistent triage-score cache (by email id) so refreshes/page revisits don't
// re-run the NLP classifier. Capped to avoid unbounded growth.
// Keys are SCOPED to the current user via userStorage to prevent cross-account leaks.
//
// Cache versioning: bump TRIAGE_CACHE_VERSION to invalidate all clients and
// force a fresh triage + DB write on next load. Do this after backend changes
// that affect triage scoring.
const TRIAGE_CACHE_VERSION = 'v3'; // v3 = fixed 0-score bug (max_tokens + prompt template)
const TRIAGE_CACHE_KEY = `triage_cache_${TRIAGE_CACHE_VERSION}`;
type TriageLite = NonNullable<Email['triage']>;

function readTriageCache(): Record<string, TriageLite> {
  if (typeof window === 'undefined') return {};
  try { return JSON.parse(userStorage.getItem(TRIAGE_CACHE_KEY) || '{}'); } catch { return {}; }
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
    userStorage.setItem(TRIAGE_CACHE_KEY, JSON.stringify(trimmed));
  } catch {}
}

/** Clear localStorage triage cache — forces re-triage + DB writes on next load. */
export function clearTriageCache(): void {
  if (typeof window === 'undefined') return;
  userStorage.removeItem(TRIAGE_CACHE_KEY);
}

// Email cache TTL — how long to trust cached emails before re-fetching from API.
// On reload within this window, emails are shown from cache instantly with zero
// Gmail/Graph API calls. The SSE poll still runs and will notify if a new email
// arrives, at which point only that one email is prepended (no full re-fetch).
const EMAIL_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// Bump this when the Email shape changes (e.g. added html_body).
// Old cache entries with a different version are silently discarded,
// forcing a fresh API fetch on next load.
const EMAIL_CACHE_VERSION = 'v3'; // v3 = added html_body + attachments fields

type EmailCacheEntry = {
  v: string;
  emails: Email[];
  cachedAt: number;
  nextPageToken: string | null;
};

function _cacheKey(folder: string) { return `emails_${EMAIL_CACHE_VERSION}_${folder}`; }

function readEmailCache(folder: string): EmailCacheEntry | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = userStorage.getItem(_cacheKey(folder));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Discard old plain-array format or wrong version — forces fresh fetch
    if (Array.isArray(parsed) || parsed.v !== EMAIL_CACHE_VERSION) return null;
    return parsed as EmailCacheEntry;
  } catch { return null; }
}

function writeEmailCache(folder: string, emails: Email[], nextPageToken: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    const entry: EmailCacheEntry = { v: EMAIL_CACHE_VERSION, emails, cachedAt: Date.now(), nextPageToken };
    userStorage.setItem(_cacheKey(folder), JSON.stringify(entry));
  } catch {}
}

function clearEmailCache(folder: string): void {
  if (typeof window === 'undefined') return;
  try {
    userStorage.removeItem(_cacheKey(folder));
  } catch {}
}

function isCacheFresh(entry: EmailCacheEntry): boolean {
  return Date.now() - entry.cachedAt < EMAIL_CACHE_TTL_MS;
}

interface RawEmail {
  id?: string;
  email_id?: string;
  sender: string;
  subject: string;
  body: string;
  html_body?: string;
  attachments?: Email['attachments'];
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
    return (userStorage.getItem(SORT_STORAGE_KEY) as SortKey) || 'normal';
  });

  const setSortKey = useCallback((key: SortKey) => {
    setSortKeyState(key);
    userStorage.setItem(SORT_STORAGE_KEY, key);
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
  // Pagination — fetch exactly 10 emails per page directly from Graph/Gmail.
  // Triage fires only for the current page's emails using the 3-level cache
  // (localStorage → Redis → DB → LLM). Previous pages stay in allEmails so
  // navigating back is instant with no extra API calls.
  // --------------------------------------------------------------------------
  const PAGE_SIZE = 10;

  const [allEmails, setAllEmails] = useState<Email[]>([]);
  const [total, setTotal] = useState(0);
  const [pageIndex, setPageIndex] = useState(0);
  const [fetchOffset, setFetchOffset] = useState(0);
  const [hasMoreOnServer, setHasMoreOnServer] = useState(true);
  // nextPageTokenRef: stores the actual cursor token returned by the API.
  // For Microsoft Graph: a numeric skip string e.g. "10"
  // For Gmail: an opaque cursor string e.g. "AqBCdef..."
  // MUST use this instead of a computed offset — Gmail ignores numeric offsets.
  const nextPageTokenRef = useRef<string | null>(null);
  const lastFolderRef = useRef<string | null>(null);
  const searchRef = useRef('');
  useEffect(() => { searchRef.current = searchQuery; }, [searchQuery]);

  const folderParam = (f: string) =>
    (['Inbox', 'Starred', 'Important'].includes(f) ? 'inbox' : f.toLowerCase());

  // Map raw API response to Email objects, reusing localStorage triage cache.
  const mapRaw = useCallback((raw: RawEmail[]): Email[] => {
    const tcache = readTriageCache();
    return raw.map((e) => {
      const id = e.email_id || e.id || '';
      const cachedT = tcache[id];
      return {
        id,
        sender: e.sender,
        subject: e.subject,
        body: e.body,
        received_at: e.received_at,
        composite_score: cachedT ? Math.round(cachedT.composite_score) : (e.composite_score || 0),
        triage: e.triage || cachedT || null,
        html_body: e.html_body || undefined,
        attachments: e.attachments || undefined,
        isRead: e.is_read ?? true,
        hasAttachments: e.has_attachments ?? false,
      };
    });
  }, []);

  // Stable refs so triage/load callbacks never go stale without triggering re-renders.
  const activeFolderRef = useRef(activeFolder);
  const enabledRef = useRef(enabled);
  const allEmailsRef = useRef<Email[]>([]);
  const fetchOffsetRef = useRef(0);
  const hasMoreOnServerRef = useRef(true);
  const pageIndexRef = useRef(0);
  useEffect(() => { activeFolderRef.current = activeFolder; }, [activeFolder]);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);

  // Triage a slice of emails — uses stable refs, no state in deps.
  // This avoids triageSlice changing on every pageIndex change which would
  // cascade into loadEmails re-creating → useEffects firing → repeated GETs.
  const triageSlice = useCallback(async (slice: Email[]) => {
    if (!['Inbox', 'Starred', 'Important'].includes(activeFolderRef.current)) return;
    const todo = slice.filter((e) => !e.triage);
    if (todo.length === 0) return;

    console.info(`[triage] Scoring ${todo.length} emails`);
    try {
      const scores = (await triagePageBatch(todo.map((e) => ({
        email_id: e.id, sender: e.sender, subject: e.subject,
        body: e.body, received_at: e.received_at,
      })))) as TriageLite[];

      const byId: Record<string, TriageLite> = {};
      todo.forEach((e, i) => { if (scores[i]) byId[e.id] = scores[i]; });
      writeTriageCache(byId);

      const apply = (e: Email) =>
        byId[e.id] ? { ...e, composite_score: Math.round(byId[e.id].composite_score), triage: byId[e.id] } : e;

      allEmailsRef.current = allEmailsRef.current.map(apply);
      emailsRef.current = emailsRef.current.map(apply);
      setAllEmails((prev) => prev.map(apply));
      setEmailsRaw((prev) => prev.map(apply));
    } catch (err) {
      console.warn('[triage] Page triage failed', err);
    }
  }, []); // stable — zero deps, reads only from refs

  const mapRawEmails = (rawList: RawEmail[]): Email[] => {
    const tcache = readTriageCache();
    return rawList.map((e) => {
      const id = e.email_id || e.id || '';
      const cachedT = tcache[id];
      return {
        id, sender: e.sender, subject: e.subject, body: e.body,
        received_at: e.received_at,
        composite_score: cachedT ? Math.round(cachedT.composite_score) : (e.composite_score || 0),
        triage: e.triage || cachedT || null,
        html_body: e.html_body || undefined,
        attachments: e.attachments || undefined,
        isRead: e.is_read ?? true,
        hasAttachments: e.has_attachments ?? false,
      };
    });
  };

  // loadEmails — ZERO deps, reads everything from refs.
  //
  // Cache-first strategy:
  //   1. On reload within EMAIL_CACHE_TTL_MS (5 min): show cached emails instantly,
  //      skip all Gmail/Graph API calls. SSE poll still runs for new emails.
  //   2. On cache miss OR stale cache: fetch from API, update cache.
  //   3. On explicit refresh (refresh button): always re-fetch (silent=false, force=true).
  const loadEmails = useCallback(async (silent = false, force = false) => {
    if (!enabledRef.current) return;
    setError(null);

    const folder = activeFolderRef.current;
    const folderChanged = lastFolderRef.current !== folder;

    if (folderChanged) {
      lastFolderRef.current = folder;
      pageIndexRef.current = 0;
      fetchOffsetRef.current = 0;
      hasMoreOnServerRef.current = true;
      nextPageTokenRef.current = null;
      setPageIndex(0);
      setSelectedEmailId(null);
    }

    // ── Cache-first: serve from localStorage if fresh and not forced ─────────
    const cached = readEmailCache(folder);
    if (!force && cached && isCacheFresh(cached) && cached.emails.length > 0) {
      console.info('[inbox] Serving %s from cache (%ds old) — skipping API call',
        folder, Math.round((Date.now() - cached.cachedAt) / 1000));

      // Restore pagination cursor from cache
      nextPageTokenRef.current = cached.nextPageToken;
      const hasMore = !!cached.nextPageToken;

      allEmailsRef.current = cached.emails;
      emailsRef.current = cached.emails.slice(0, PAGE_SIZE);
      fetchOffsetRef.current = cached.emails.length;
      hasMoreOnServerRef.current = hasMore;
      pageIndexRef.current = 0;

      setAllEmails(cached.emails);
      setTotal(cached.emails.length);
      setFetchOffset(cached.emails.length);
      setHasMoreOnServer(hasMore);
      setPageIndex(0);
      setEmailsRaw(cached.emails.slice(0, PAGE_SIZE));
      // Triage only un-scored emails (likely already scored and in cache)
      triageSlice(cached.emails.slice(0, PAGE_SIZE));
      return;
    }

    // ── Cache miss or stale — fetch from API ──────────────────────────────────
    if (!silent) setLoading(true);

    // Show stale cache instantly while fresh data loads in background
    if (cached && cached.emails.length > 0) {
      allEmailsRef.current = cached.emails;
      setAllEmails(cached.emails);
      setEmailsRaw(cached.emails.slice(0, PAGE_SIZE));
      emailsRef.current = cached.emails.slice(0, PAGE_SIZE);
    }

    try {
      const page = await fetchMailbox(
        folderParam(folder), PAGE_SIZE, null, searchRef.current,
      );
      const mapped = mapRawEmails((page.emails || []) as unknown as RawEmail[]);
      const newToken = page.next_page_token || null;
      const hasMore = !!newToken;

      // Write refs before setState
      nextPageTokenRef.current = newToken;
      allEmailsRef.current = mapped;
      emailsRef.current = mapped;
      fetchOffsetRef.current = mapped.length;
      hasMoreOnServerRef.current = hasMore;
      pageIndexRef.current = 0;

      // Persist with timestamp + cursor so next reload is instant
      writeEmailCache(folder, mapped, newToken);

      setAllEmails(mapped);
      setTotal(page.total || mapped.length);
      setFetchOffset(mapped.length);
      setHasMoreOnServer(hasMore);
      setPageIndex(0);
      setEmailsRaw(mapped);
      setSelectedEmailId((prev) => (prev && mapped.some((e) => e.id === prev) ? prev : null));
      triageSlice(mapped);
    } catch (err: unknown) {
      console.error('Failed to load emails', err);
      setError(err instanceof Error ? err.message : 'Failed to load emails');
    } finally {
      if (!silent) setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // nextPage — reads/writes refs first, then flushes to React state in one batch.
  // Doing ref writes before setState prevents any intermediate re-render from
  // reading stale ref values and overwriting the new page.
  const nextPage = useCallback(async () => {
    const next = pageIndexRef.current + 1;

    // ── Cached page (already fetched) ──────────────────────────────────────
    if (next * PAGE_SIZE < allEmailsRef.current.length) {
      const slice = allEmailsRef.current.slice(next * PAGE_SIZE, (next + 1) * PAGE_SIZE);
      pageIndexRef.current = next;
      emailsRef.current = slice;
      setPageIndex(next);
      setEmailsRaw(slice);   // direct set — no functional updater, no stale-prev risk
      setSelectedEmailId(null);
      triageSlice(slice);
      return;
    }

    // ── Fetch next 10 from server ───────────────────────────────────────────
    if (!hasMoreOnServerRef.current) return;
    // Must have a valid cursor token — Gmail needs its own opaque cursor,
    // Graph uses numeric skip. Never compute "10", "20" manually.
    const token = nextPageTokenRef.current;
    if (!token) {
      hasMoreOnServerRef.current = false;
      setHasMoreOnServer(false);
      return;
    }
    setLoading(true);
    try {
      const page = await fetchMailbox(
        folderParam(activeFolderRef.current), PAGE_SIZE, token, searchRef.current,
      );
      const newEmails = mapRaw((page.emails || []) as unknown as RawEmail[]);
      if (newEmails.length === 0) {
        hasMoreOnServerRef.current = false;
        nextPageTokenRef.current = null;
        setHasMoreOnServer(false);
        return;
      }

      const combined = [...allEmailsRef.current, ...newEmails];
      const newOffset = fetchOffsetRef.current + newEmails.length;
      const newToken = page.next_page_token || null;
      const hasMore = !!newToken;

      // Write refs before any setState
      nextPageTokenRef.current = newToken;
      allEmailsRef.current = combined;
      fetchOffsetRef.current = newOffset;
      hasMoreOnServerRef.current = hasMore;
      pageIndexRef.current = next;

      // Persist combined list with updated cursor so next reload restores full state
      writeEmailCache(activeFolderRef.current, combined, newToken);

      emailsRef.current = newEmails;
      setAllEmails(combined);
      setFetchOffset(newOffset);
      setHasMoreOnServer(hasMore);
      setPageIndex(next);
      setEmailsRaw(newEmails);
      setSelectedEmailId(null);

      triageSlice(newEmails);
    } catch (err) {
      console.error('Failed to fetch next page', err);
    } finally {
      setLoading(false);
    }
  }, [mapRaw, triageSlice]);

  const prevPage = useCallback(() => {
    if (pageIndexRef.current === 0) return;
    const prev = pageIndexRef.current - 1;
    const slice = allEmailsRef.current.slice(prev * PAGE_SIZE, (prev + 1) * PAGE_SIZE);
    pageIndexRef.current = prev;
    emailsRef.current = slice;
    setPageIndex(prev);
    setEmailsRaw(slice);   // direct set — no functional updater
    setSelectedEmailId(null);
    triageSlice(slice);
  }, [triageSlice]);

  const hasNextPage = (pageIndex + 1) * PAGE_SIZE < allEmails.length || hasMoreOnServer;
  const hasPrevPage = pageIndex > 0;

  // Single effect that owns ALL loadEmails triggers.
  // Tracks folder + enabled + searchQuery together so exactly one load fires
  // per change — no double-fire, no stale-closure reset after nextPage.
  const prevTriggerRef = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const trigger = `${activeFolder}|${searchQuery}`;
    const isSearch = prevTriggerRef.current !== null &&
      prevTriggerRef.current.split('|')[0] === activeFolder &&
      prevTriggerRef.current.split('|')[1] !== searchQuery;

    prevTriggerRef.current = trigger;

    // Debounce search changes by 400ms; folder changes and initial load are immediate.
    const delay = isSearch ? 400 : 0;
    const id = setTimeout(() => loadEmails(), delay);
    return () => clearTimeout(id);
  }, [activeFolder, enabled, searchQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  // Smart new-email polling — uses lightweight /api/inbox/poll (1 API call,
  // no body fetching). Only triggers a full reload when a new email arrives.
  // Uses refs only so this interval never restarts on re-renders.
  const latestEmailIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (allEmails.length > 0) latestEmailIdRef.current = allEmails[0]?.id || null;
  }, [allEmails]);

  useEffect(() => {
    const id = setInterval(async () => {
      if (!enabledRef.current || !['Inbox', 'Starred', 'Important'].includes(activeFolderRef.current)) return;
      const result = await pollNewEmail();
      if (!result.latest_id || result.latest_id === latestEmailIdRef.current) return;

      console.info('[inbox] New email detected (%s) — fetching and prepending', result.latest_id);
      latestEmailIdRef.current = result.latest_id;

      // Fetch only the 1 newest email and prepend it — no full reload needed.
      // This keeps the cache valid and avoids re-fetching all 10+ emails.
      try {
        const { fetchMailbox: fm } = await import('../lib/api');
        const page = await fm(folderParam(activeFolderRef.current), 1, null, '');
        const newOnes = mapRawEmails((page.emails || []).slice(0, 1) as unknown as RawEmail[]);
        if (newOnes.length === 0 || newOnes[0].id === allEmailsRef.current[0]?.id) return;

        // Prepend new email at top, keep existing list
        const updated = [newOnes[0], ...allEmailsRef.current];
        const currentToken = nextPageTokenRef.current;
        allEmailsRef.current = updated;

        // Update cache with new email prepended
        writeEmailCache(activeFolderRef.current, updated, currentToken);

        // If on page 0, show it at the top immediately
        if (pageIndexRef.current === 0) {
          const newPage0 = updated.slice(0, PAGE_SIZE);
          emailsRef.current = newPage0;
          setAllEmails(updated);
          setEmailsRaw(newPage0);
          setTotal((prev) => prev + 1);
          triageSlice([newOnes[0]]);
        } else {
          // User is on a later page — just update allEmails silently
          setAllEmails(updated);
          setTotal((prev) => prev + 1);
        }
      } catch (err) {
        console.warn('[inbox] Failed to fetch new email, falling back to full reload', err);
        loadEmails(true, true); // force=true bypasses cache
      }
    }, 60000);
    return () => clearInterval(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
      let newListLength = 0;
      setEmails((prev) => {
        const next = prev.filter((e) => e.id !== emailId);
        newListLength = next.length;
        return next;
      });
      setSelectedEmailId((prev) => (prev === emailId ? null : prev));

      // Show toast with undo window (3 seconds)
      setPendingTrash({ email: snapshot, startedAt: Date.now() });

      // Fire API after 3 s — cancelled if user hits Undo
      trashTimerRef.current = setTimeout(async () => {
        trashTimerRef.current = null;
        setPendingTrash(null);
        try {
          await moveEmailToTrash(emailId);
          // Clear cache on success so refresh loads fresh data from API
          clearEmailCache(activeFolder);
          clearEmailCache('Trash'); // Email was moved to Trash

          // Auto-fetch next email in background (don't await — non-blocking)
          // Only fetch if page dropped below half size and more exist on server
          if (newListLength < PAGE_SIZE / 2 && hasMoreOnServerRef.current) {
            nextPage().catch((err) => console.error('Failed to fetch next page', err));
          }
        } catch (err) {
          console.error(`Failed to move email ${emailId} to trash`, err);
          // Clear cache and reload on failure to ensure consistency
          clearEmailCache(activeFolder);
          await loadEmails();
        }
      }, 3000);
    },
    [activeFolder, setEmails, loadEmails, nextPage]
  );

  const undoTrash = useCallback(() => {
    if (!pendingTrash) return;
    if (trashTimerRef.current) {
      clearTimeout(trashTimerRef.current);
      trashTimerRef.current = null;
    }
    const { email } = pendingTrash;
    setPendingTrash(null);
    // Re-insert the email into the current list and clear cache
    setEmails((prev) => {
      const next = [...prev, email];
      return next;
    });
    // Clear cache so next load reflects the restored email
    clearEmailCache(activeFolder);
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
      let newListLength = 0;
      setEmails((prev) => {
        const next = prev.filter((e) => e.id !== emailId);
        newListLength = next.length;
        return next;
      });
      setSelectedEmailId((prev) => (prev === emailId ? null : prev));
      try {
        await restoreEmailFromTrash(emailId);
        // Clear caches on success
        clearEmailCache('Trash');
        clearEmailCache('Inbox');

        // Auto-fetch next email in background (non-blocking)
        if (newListLength < PAGE_SIZE / 2 && hasMoreOnServerRef.current) {
          nextPage().catch((err) => console.error('Failed to fetch next page', err));
        }
      } catch (err) {
        console.error(`Failed to restore email ${emailId}`, err);
        // Clear cache and reload on failure
        clearEmailCache('Trash');
        await loadEmails();
      }
    },
    [setEmails, loadEmails, nextPage]
  );

  // --------------------------------------------------------------------------
  // Mark read / unread, archive, report spam
  // --------------------------------------------------------------------------
  const persist = useCallback((list: Email[]) => {
    userStorage.setItem(`emails_${activeFolder}`, JSON.stringify(list));
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
    let newListLength = 0;
    setEmails((prev) => {
      const next = prev.filter((e) => e.id !== emailId);
      newListLength = next.length;
      persist(next);
      return next;
    });
    setSelectedEmailId((prev) => (prev === emailId ? null : prev));
    try {
      await apiArchiveEmail(emailId);
      // Clear caches on success
      clearEmailCache(activeFolder);
      clearEmailCache('Archive');

      // Auto-fetch next email in background (non-blocking)
      if (newListLength < PAGE_SIZE / 2 && hasMoreOnServerRef.current) {
        nextPage().catch((err) => console.error('Failed to fetch next page', err));
      }
    } catch (err) {
      console.error(`Failed to archive ${emailId}`, err);
      // Clear cache and reload on failure
      clearEmailCache(activeFolder);
      await loadEmails();
    }
  }, [activeFolder, setEmails, persist, loadEmails, nextPage]);

  const reportSpam = useCallback(async (emailId: string) => {
    let newListLength = 0;
    setEmails((prev) => {
      const next = prev.filter((e) => e.id !== emailId);
      newListLength = next.length;
      persist(next);
      return next;
    });
    setSelectedEmailId((prev) => (prev === emailId ? null : prev));
    try {
      await apiReportSpam(emailId);
      // Clear caches on success
      clearEmailCache(activeFolder);
      clearEmailCache('Spam');

      // Auto-fetch next email in background (non-blocking)
      if (newListLength < PAGE_SIZE / 2 && hasMoreOnServerRef.current) {
        nextPage().catch((err) => console.error('Failed to fetch next page', err));
      }
    } catch (err) {
      console.error(`Failed to report spam ${emailId}`, err);
      // Clear cache and reload on failure
      clearEmailCache(activeFolder);
      await loadEmails();
    }
  }, [activeFolder, setEmails, persist, loadEmails, nextPage]);

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
    refresh: () => loadEmails(false, false), // manual refresh respects cache
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
