/**
 * Remembered-login helper for the Quick Login feature.
 *
 * Stores only a non-sensitive hint of the last successful sign-in (mode +
 * display email) so returning users get a one-tap login. No tokens or secrets
 * are persisted here — the actual session lives server-side.
 *
 * DEVICE-SCOPED: Quick login is tied to a specific device via a unique device ID.
 * This prevents cross-device account leakage (e.g., shared computers, public terminals).
 */

export type LoginMode = 'mock' | 'live';
export type Provider = 'microsoft' | 'google';

export interface RememberedLogin {
  mode: LoginMode;
  provider: Provider;
  email: string;
  /** ms timestamp of the last successful login */
  ts: number;
  /** Device ID to ensure quick login only works on the same device */
  deviceId: string;
}

const KEY = 'mailmind_last_login';
const REMEMBER_KEY = 'mailmind_remember_me';
const DEVICE_ID_KEY = 'mailmind_device_id';

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

    // DEVICE-SCOPED: Only return quick login if device ID matches.
    // This prevents User B from seeing User A's quick login on a shared device.
    const currentDeviceId = getDeviceId();
    if (!parsed.deviceId || parsed.deviceId !== currentDeviceId) {
      return null;
    }

    // Backward-compat: default provider for entries saved before multi-provider.
    if (!parsed.provider) parsed.provider = 'microsoft';
    return parsed;
  } catch {
    return null;
  }
}

export function rememberLogin(
  mode: LoginMode,
  email: string | null | undefined,
  provider: Provider = 'microsoft'
): void {
  if (typeof window === 'undefined') return;
  const entry: RememberedLogin = {
    mode,
    provider,
    email: email || 'Signed-in user',
    ts: Date.now(),
    deviceId: getDeviceId(),
  };
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
