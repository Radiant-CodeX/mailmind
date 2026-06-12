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
const DEVICE_ID_KEY = 'mailmind_device_id';
const LAST_EMAIL_KEY = 'mailmind_last_login_email';

/** Generate a simple UUID v4 */
function generateDeviceId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Get or create the device ID for this device */
function getDeviceId(): string {
  if (typeof window === 'undefined') return '';
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = generateDeviceId();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

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

  const normalizedEmail = (email || 'Signed-in user').toLowerCase();
  const lastEmail = localStorage.getItem(LAST_EMAIL_KEY);

  // SECURITY: If a DIFFERENT user logs in on this device, clear the previous
  // user's quick login to prevent impersonation.
  // Example: User A logs in, logs out. User B logs in on the same device.
  // When User A returns and hard-reloads, they should NOT see User B's quick login.
  if (lastEmail && lastEmail !== normalizedEmail) {
    localStorage.removeItem(KEY);
  }

  const entry: RememberedLogin = {
    provider,
    email: email || 'Signed-in user',
  };
  localStorage.setItem(KEY, JSON.stringify(entry));
  localStorage.setItem(LAST_EMAIL_KEY, normalizedEmail);
}

export function clearRememberedLogin(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(KEY);
  localStorage.removeItem(LAST_EMAIL_KEY);
}

/** Initials for an avatar chip, e.g. "tarun@gmail.com" → "TA". */
export function initialsFor(email: string): string {
  const name = email.split('@')[0] || email;
  return name.slice(0, 2).toUpperCase();
}
