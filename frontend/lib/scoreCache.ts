/**
 * IndexedDB triage score cache (replaces the localStorage triage cache).
 *
 * localStorage has a 5-10 MB quota shared across all keys. With 500+ emails
 * each carrying body text + triage axes, JSON.stringify easily exceeds the
 * limit — the write fails silently (try/catch {}) and the next reload sees a
 * cache miss, triggering a full 9-second triage run.
 *
 * IndexedDB has no practical size limit (browser gives ≥60% of disk on Chrome,
 * ≥10 GB on Firefox) and stores entries individually — no monolithic JSON blob.
 *
 * Schema: one "scores" table keyed by `{userId}:{emailId}`. Storing scores
 * separately from email bodies means we never evict scores due to body size.
 *
 * All methods are async and safe to call from SSR (they no-op server-side).
 */

import Dexie, { type Table } from 'dexie';
import type { Email } from './types';

// Bump when the shape of TriageLite changes — old rows will be ignored (not
// deleted; they just won't match the version check) until they expire or are
// overwritten by a fresh triage result.
const SCORE_CACHE_VERSION = 4;

type TriageLite = NonNullable<Email['triage']>;

interface ScoreRow {
  /** `{userId}:{emailId}` — composite primary key for user isolation */
  key: string;
  emailId: string;
  userId: string;
  score: TriageLite;
  /** Unix ms — used for TTL eviction of very stale rows */
  savedAt: number;
  /** Schema version — rows with a different version are ignored as stale */
  v: number;
}

class ScoreCacheDB extends Dexie {
  scores!: Table<ScoreRow, string>;

  constructor() {
    super('mailmind_score_cache');
    this.version(1).stores({
      // Only index what we query by. `key` is the primary key.
      scores: 'key, userId, savedAt',
    });
  }
}

// Lazy singleton — created only in the browser, never during SSR.
let _db: ScoreCacheDB | null = null;
function getDB(): ScoreCacheDB | null {
  if (typeof window === 'undefined') return null;
  if (!_db) _db = new ScoreCacheDB();
  return _db;
}

/** 30 days — scores don't go stale unless the scoring model changes (bump SCORE_CACHE_VERSION). */
const TTL_MS = 30 * 24 * 60 * 60 * 1000;

function rowKey(userId: string, emailId: string): string {
  return `${userId}:${emailId}`;
}

/**
 * Load all cached scores for the given user.
 * Returns a map of emailId → TriageLite (only valid-version, non-expired rows).
 * Falls back to {} on any error so the caller always gets a usable map.
 */
export async function loadScores(userId: string): Promise<Record<string, TriageLite>> {
  const db = getDB();
  if (!db || !userId) return {};
  try {
    const now = Date.now();
    const rows = await db.scores
      .where('userId')
      .equals(userId)
      .filter((r) => r.v === SCORE_CACHE_VERSION && now - r.savedAt < TTL_MS)
      .toArray();
    return Object.fromEntries(rows.map((r) => [r.emailId, r.score]));
  } catch {
    return {};
  }
}

/**
 * Persist a batch of triage results.
 * Called after the triage SSE stream completes with fresh LLM results.
 */
export async function saveScores(
  userId: string,
  scores: Record<string, TriageLite>,
): Promise<void> {
  const db = getDB();
  if (!db || !userId) return;
  const now = Date.now();
  const rows: ScoreRow[] = Object.entries(scores).map(([emailId, score]) => ({
    key: rowKey(userId, emailId),
    emailId,
    userId,
    score,
    savedAt: now,
    v: SCORE_CACHE_VERSION,
  }));
  try {
    await db.scores.bulkPut(rows);
  } catch {
    // Never throw — cache failures must not break triage results.
  }
}

/**
 * Remove all cached scores for a user (call on logout / account switch).
 */
export async function clearScores(userId: string): Promise<void> {
  const db = getDB();
  if (!db || !userId) return;
  try {
    await db.scores.where('userId').equals(userId).delete();
  } catch {}
}

/**
 * Evict rows older than TTL for all users. Call periodically (e.g. on app mount)
 * to prevent unbounded growth. Low-priority — safe to fire-and-forget.
 */
export async function evictStaleScores(): Promise<void> {
  const db = getDB();
  if (!db) return;
  try {
    const cutoff = Date.now() - TTL_MS;
    await db.scores.where('savedAt').below(cutoff).delete();
  } catch {}
}
