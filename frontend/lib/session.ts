/**
 * Remembered-login helper — stores a UI hint for the Quick Login card.
 *
 * v3: session management is fully server-side (mm_session + mm_quick cookies).
 * This module only persists a display hint (email + provider) so the login page
 * can show "Continue as tarun@gmail.com" without asking the user to re-type.
 *
 * No tokens, no mode, no TTL management here — all of that is the backend's job.
 */

export type Provider = 'microsoft' | 'google';

export interface RememberedLogin {
  provider: Provider;
  email: string;
}

const KEY = 'mailmind_last_login';
const REMEMBER_KEY = 'mailmind_remember_me';

/** The "Remember me" checkbox preference (defaults to true). */
export function getRememberMe(): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(REMEMBER_KEY) !== 'false';
}

export function setRememberMe(value: boolean): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(REMEMBER_KEY, String(value));
}

export function getRememberedLogin(): RememberedLogin | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<RememberedLogin> & { mode?: string; ts?: number };
    if (!parsed || !parsed.email) return null;
    return {
      provider: parsed.provider || 'microsoft',
      email: parsed.email,
    };
  } catch {
    return null;
  }
}

export function rememberLogin(email: string | null | undefined, provider: Provider = 'microsoft'): void {
  if (typeof window === 'undefined') return;
  const entry: RememberedLogin = {
    provider,
    email: email || 'Signed-in user',
  };
  localStorage.setItem(KEY, JSON.stringify(entry));
}

export function clearRememberedLogin(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(KEY);
}

/** Initials for an avatar chip, e.g. "tarun@gmail.com" → "TA". */
export function initialsFor(email: string): string {
  const name = email.split('@')[0] || email;
  return name.slice(0, 2).toUpperCase();
}
