/**
 * User-scoped localStorage
 * ========================
 * All cached data (emails, triage scores, draft cache) is stored under a key
 * that includes the signed-in user's identity. This guarantees full data
 * isolation between accounts — User B logging in after User A will never see
 * User A's emails, triage results, or drafts.
 *
 * Usage:
 *   import { userStorage } from '../lib/userStorage';
 *   userStorage.setItem('emails_Inbox', JSON.stringify(emails));
 *   userStorage.getItem('emails_Inbox');
 *   userStorage.clearUserData();   // call on logout
 */

const CURRENT_USER_KEY = 'mailmind_current_user';

/** Hash a string to a short stable identifier (no crypto dependency). */
function simpleHash(str: string): string {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(36);
}

/** Return a stable namespace prefix for the current user. */
function userPrefix(): string {
  if (typeof window === 'undefined') return 'anon';
  const u = localStorage.getItem(CURRENT_USER_KEY);
  return u ? simpleHash(u) : 'anon';
}

/** Prefix a storage key with the current user's namespace. */
function scopedKey(key: string): string {
  return `mm_${userPrefix()}_${key}`;
}

export const userStorage = {
  /** Set the active user identity (call immediately after successful login). */
  setUser(email: string): void {
    if (typeof window === 'undefined') return;
    const prev = localStorage.getItem(CURRENT_USER_KEY);
    if (prev && prev !== email) {
      // Different user — clear the previous user's scoped data before switching.
      userStorage.clearUserData(prev);
    }
    localStorage.setItem(CURRENT_USER_KEY, email);
  },

  /** Get the currently stored user identity. */
  getUser(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(CURRENT_USER_KEY);
  },

  /** Read a value scoped to the current user. */
  getItem(key: string): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(scopedKey(key));
  },

  /** Write a value scoped to the current user. */
  setItem(key: string, value: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(scopedKey(key), value);
  },

  /** Remove a single key scoped to the current user. */
  removeItem(key: string): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(scopedKey(key));
  },

  /**
   * Clear ALL scoped data for a given user (or the current user if omitted).
   * Call this on logout to prevent data leakage to the next user.
   */
  clearUserData(email?: string): void {
    if (typeof window === 'undefined') return;
    const prefix = email ? `mm_${simpleHash(email)}_` : `mm_${userPrefix()}_`;
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefix)) keysToRemove.push(k);
    }
    keysToRemove.forEach((k) => localStorage.removeItem(k));
  },

  /** Full logout: clear user data and remove the current-user marker. */
  logout(): void {
    if (typeof window === 'undefined') return;
    userStorage.clearUserData();
    localStorage.removeItem(CURRENT_USER_KEY);
  },
};
