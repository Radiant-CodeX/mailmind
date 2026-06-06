/**
 * Lightweight client-side monitoring sink.
 *
 * If NEXT_PUBLIC_SENTRY_DSN is set and @sentry/nextjs is installed, errors are
 * forwarded to Sentry. Otherwise it degrades to console logging — so the app
 * works with zero monitoring config in dev, and lights up in production.
 */

type Extra = Record<string, unknown>;

let sentry: { captureException: (e: unknown, ctx?: unknown) => void } | null = null;
let initialized = false;

async function ensureInit(): Promise<void> {
  if (initialized) return;
  initialized = true;
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;
  try {
    // Dynamic import via a non-literal specifier so the optional dependency is
    // resolved only at runtime (and TS doesn't require it to be installed).
    const moduleName = '@sentry/nextjs';
    const mod = await import(/* webpackIgnore: true */ moduleName).catch(() => null);
    if (mod && typeof mod.init === 'function') {
      mod.init({ dsn, tracesSampleRate: 0.1, environment: process.env.NODE_ENV });
      sentry = mod;
    }
  } catch {
    // Sentry not installed — stay in console-only mode.
  }
}

export function reportError(error: unknown, extra?: Extra): void {
  void ensureInit().then(() => {
    if (sentry) {
      sentry.captureException(error, extra ? { extra } : undefined);
    } else if (process.env.NODE_ENV !== 'test') {
      console.error('[monitoring]', error, extra ?? '');
    }
  });
}
