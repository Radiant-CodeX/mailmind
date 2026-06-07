/**
 * Remembered-login helper for the Quick Login feature.
 *
 * Stores only a non-sensitive hint of the last successful sign-in (mode +
 * display email) so returning users get a one-tap login. No tokens or secrets
 * are persisted here — the actual session lives server-side.
 */

export type LoginMode = 'mock' | 'live';

export interface RememberedLogin {
  mode: LoginMode;
  email: string;
  /** ms timestamp of the last successful login */
  ts: number;
}

const KEY = 'mailmind_last_login';

/** Quick Login stays available for one week after sign-out, then expires. */
export const QUICK_LOGIN_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export function getRememberedLogin(): RememberedLogin | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as RememberedLogin;
    if (!parsed || !parsed.mode || !parsed.email) return null;
    // Expire entries older than the TTL so the card disappears after a week.
    if (typeof parsed.ts === 'number' && Date.now() - parsed.ts > QUICK_LOGIN_TTL_MS) {
      localStorage.removeItem(KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function rememberLogin(mode: LoginMode, email: string | null | undefined): void {
  if (typeof window === 'undefined') return;
  const entry: RememberedLogin = { mode, email: email || 'Signed-in user', ts: Date.now() };
  localStorage.setItem(KEY, JSON.stringify(entry));
}

export function clearRememberedLogin(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(KEY);
}

/** Initials for an avatar chip, e.g. "mock.user@x.com" → "MO". */
export function initialsFor(email: string): string {
  const name = email.split('@')[0] || email;
  return name.slice(0, 2).toUpperCase();
}
