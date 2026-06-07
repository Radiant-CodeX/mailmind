'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  checkAuthStatus,
  loginInitiate,
  loginPoll,
  loginMock,
  quickLogin,
  googleLoginInitiate,
  googleLoginPoll,
} from '../lib/api';
import {
  getRememberedLogin,
  clearRememberedLogin,
  initialsFor,
  getRememberMe,
  setRememberMe as persistRememberMe,
  RememberedLogin,
  Provider,
} from '../lib/session';

/** Pick the provider for a typed email address. */
function providerForEmail(email: string): Provider {
  const domain = email.split('@')[1]?.toLowerCase() || '';
  if (domain.includes('gmail') || domain.includes('googlemail')) return 'google';
  return 'microsoft';
}

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [authStatus, setAuthStatus] = useState<string>('checking');
  const [remembered, setRemembered] = useState<RememberedLogin | null>(null);
  const [email, setEmail] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [deviceFlow, setDeviceFlow] = useState<{
    userCode: string;
    verificationUri: string;
    deviceCode: string;
    message: string;
  } | null>(null);
  const [googleWaiting, setGoogleWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const pollingIntervalRef = React.useRef<NodeJS.Timeout | null>(null);
  const googlePopupRef = React.useRef<Window | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const data = await checkAuthStatus();
        if (data.authenticated) {
          router.replace('/dashboard');
          return;
        }
        setRemembered(getRememberedLogin());
        setRememberMe(getRememberMe());
        setAuthStatus('ready');
      } catch (err) {
        console.error('Failed to query status', err);
        setRemembered(getRememberedLogin());
        setAuthStatus('ready');
      }
    }
    init();
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, [router]);

  const rememberPref = (val: boolean) => {
    setRememberMe(val);
    persistRememberMe(val);
  };

  // ── Microsoft (device-code flow) ───────────────────────────────────────────
  const handleMockLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      await loginMock();
      router.push('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Mock login failed');
      setLoading(false);
    }
  };

  const handleMicrosoft = async () => {
    persistRememberMe(rememberMe);
    setLoading(true);
    setError(null);
    try {
      const data = await loginInitiate();
      if (data.status === 'mock') {
        await handleMockLogin();
        return;
      }
      setDeviceFlow({
        userCode: data.user_code,
        verificationUri: data.verification_uri,
        deviceCode: data.device_code,
        message: data.message,
      });
      startMicrosoftPolling(data.device_code);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to initiate login flow');
      setLoading(false);
    }
  };

  const startMicrosoftPolling = (deviceCode: string) => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const data = await loginPoll(deviceCode);
        if (data.status === 'success') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          router.push('/dashboard');
        } else if (data.status !== 'pending') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          setLoading(false);
          setDeviceFlow(null);
          setError('Authentication flow expired or cancelled.');
        }
      } catch (err) {
        if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
        setLoading(false);
        setDeviceFlow(null);
        setError(err instanceof Error ? err.message : 'Connection lost during polling.');
      }
    }, 4000);
  };

  // ── Google (OAuth popup flow) ──────────────────────────────────────────────
  const handleGoogle = async (emailHint?: string) => {
    persistRememberMe(rememberMe);
    setError(null);
    // Open the popup SYNCHRONOUSLY (inside the click) so the browser keeps the
    // user-gesture and doesn't block it. We navigate it once we have the URL.
    googlePopupRef.current = window.open('', 'google-login', 'width=500,height=680');
    setLoading(true);
    try {
      const data = await googleLoginInitiate(emailHint);
      if (data.authenticated || data.status === 'mock') {
        googlePopupRef.current?.close();
        router.push('/dashboard');
        return;
      }
      if (googlePopupRef.current && data.auth_url) {
        // Live: point the already-open popup at Google's consent screen.
        googlePopupRef.current.location.replace(data.auth_url);
        setGoogleWaiting(true);
        startGooglePolling(data.state, googlePopupRef.current);
      } else if (data.auth_url) {
        // Popup was blocked — fall back to a full-page redirect to Google.
        window.location.assign(data.auth_url);
      }
    } catch (err: unknown) {
      googlePopupRef.current?.close();
      setError(err instanceof Error ? err.message : 'Google sign-in failed');
      setLoading(false);
      setGoogleWaiting(false);
    }
  };

  const startGooglePolling = (state: string, popup: Window | null) => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const data = await googleLoginPoll(state);
        if (data.status === 'success') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          popup?.close();
          router.push('/dashboard');
        }
      } catch (err) {
        if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
        setLoading(false);
        setGoogleWaiting(false);
        setError(err instanceof Error ? err.message : 'Google sign-in failed');
      }
    }, 2500);
  };

  const cancelGoogle = () => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    setGoogleWaiting(false);
    setLoading(false);
  };

  // ── Email-first "Next" → route to the right provider ───────────────────────
  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }
    if (providerForEmail(email) === 'google') {
      handleGoogle(email);
    } else {
      handleMicrosoft();
    }
  };

  // ── Quick login / forget ───────────────────────────────────────────────────
  const handleQuickLogin = async () => {
    if (!remembered) return;
    setLoading(true);
    setError(null);
    try {
      await quickLogin(remembered.email, remembered.provider);
      router.push('/dashboard');
    } catch {
      // Session can't be resumed silently (token expired/cleared) — fall back to
      // a full sign-in for the remembered provider instead of showing an error.
      setLoading(false);
      if (remembered.provider === 'google') {
        handleGoogle(remembered.email);
      } else {
        handleMicrosoft();
      }
    }
  };

  const handleForgetAccount = () => {
    clearRememberedLogin();
    setRemembered(null);
  };

  const handleCopyCode = async () => {
    if (!deviceFlow) return;
    try {
      await navigator.clipboard.writeText(deviceFlow.userCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('Copy failed', e);
    }
  };

  if (authStatus === 'checking') {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-bg-base text-text-primary" id="login-checking">
        <div className="text-center">
          <div className="w-8 h-8 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mx-auto mb-4" />
          <p className="text-xs text-[var(--text-muted)] font-medium">Checking authorization status...</p>
        </div>
      </div>
    );
  }

  const showMainForm = !deviceFlow && !googleWaiting;

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-bg-base text-text-primary px-4" id="login-workspace">
      <div className="relative w-full max-w-md bg-[var(--bg-surface)] border border-[var(--border)] rounded-2xl shadow-2xl p-8 overflow-hidden">
        <div className="absolute -right-16 -top-16 w-36 h-36 rounded-full bg-[var(--accent-primary)]/10 blur-2xl" />

        {/* Brand */}
        <div className="text-center mb-8 flex flex-col items-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/mailmind-logo.svg"
            alt="MailMind logo"
            width={48}
            height={48}
            className="w-12 h-12 rounded-xl shadow mb-4"
          />
          <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">MailMind</h1>
          <p className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-widest mt-0.5">Co-pilot Studio</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs font-semibold text-center max-h-32 overflow-y-auto">
            {error}
          </div>
        )}

        {/* ── Main email-first form ── */}
        {showMainForm && (
          <div className="space-y-4">
            {/* Quick Login (after sign-out, within 1 week) */}
            {remembered && (
              <div className="mb-5 animate-fade-in">
                <button
                  onClick={handleQuickLogin}
                  disabled={loading}
                  className="w-full flex items-center gap-3 p-3 bg-[var(--bg-elevated)] hover:bg-[var(--bg-elevated)]/70 border border-[var(--border)] hover:border-[var(--accent-primary)]/40 rounded-xl transition-all cursor-pointer disabled:opacity-50 active:scale-[0.98] text-left group"
                  id="btn-quick-login"
                >
                  <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)] flex items-center justify-center text-[var(--bg-surface)] font-extrabold text-sm shrink-0 shadow">
                    {initialsFor(remembered.email)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                      Quick Login · {remembered.provider === 'google' ? 'Google' : 'Microsoft'}
                    </p>
                    <p className="text-sm font-bold text-[var(--text-primary)] truncate" title={remembered.email}>
                      {remembered.email}
                    </p>
                  </div>
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-[var(--accent-primary)] border-t-transparent animate-spin rounded-full shrink-0" />
                  ) : (
                    <svg className="w-5 h-5 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)] transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                    </svg>
                  )}
                </button>
                <button
                  onClick={handleForgetAccount}
                  className="mt-2 w-full text-[11px] font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                  id="btn-forget-account"
                >
                  Use a different account
                </button>
                <div className="flex items-center gap-3 my-5">
                  <div className="flex-1 h-px bg-[var(--border-subtle)]" />
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">or</span>
                  <div className="flex-1 h-px bg-[var(--border-subtle)]" />
                </div>
              </div>
            )}

            {/* Email + Remember me + Next */}
            <form onSubmit={handleNext} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5">Email</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Your email (Gmail, Outlook, work…)"
                    className="w-full pl-10 pr-3 py-2.5 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent-primary)] transition-all"
                    id="login-email"
                  />
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer select-none w-fit">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => rememberPref(e.target.checked)}
                  className="w-4 h-4 accent-[var(--accent-primary)] cursor-pointer"
                  id="login-remember"
                />
                <span className="text-xs font-medium text-[var(--text-muted)]">Remember me</span>
              </label>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 disabled:opacity-50 text-[var(--bg-surface)] font-extrabold text-sm rounded-xl cursor-pointer shadow hover:shadow-lg transition-all duration-200 active:scale-95"
                id="btn-login-next"
              >
                {loading ? <div className="w-4 h-4 border-2 border-[var(--bg-surface)] border-t-transparent animate-spin rounded-full" /> : 'Next'}
              </button>
            </form>

            {/* OR divider */}
            <div className="flex items-center gap-3 py-1">
              <div className="flex-1 h-px bg-[var(--border-subtle)]" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">or</span>
              <div className="flex-1 h-px bg-[var(--border-subtle)]" />
            </div>

            {/* Provider buttons */}
            <button
              onClick={() => handleGoogle(email || undefined)}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2.5 py-2.5 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-800 font-bold text-sm rounded-xl cursor-pointer border border-[var(--border)] transition-all active:scale-95"
              id="btn-login-google"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Continue with Google
            </button>

            <button
              onClick={handleMicrosoft}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2.5 py-2.5 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-800 font-bold text-sm rounded-xl cursor-pointer border border-[var(--border)] transition-all active:scale-95"
              id="btn-login-microsoft"
            >
              <svg className="w-4 h-4" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
                <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
              </svg>
              Continue with Microsoft
            </button>
          </div>
        )}

        {/* ── Google waiting ── */}
        {googleWaiting && (
          <div className="space-y-6 animate-fade-in text-center">
            <div className="w-10 h-10 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mx-auto" />
            <div>
              <p className="text-sm font-bold text-[var(--text-primary)]">Waiting for Google sign-in…</p>
              <p className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed">
                Complete the sign-in in the popup window. If it didn’t open, check your popup blocker.
              </p>
            </div>
            <button
              onClick={cancelGoogle}
              className="w-full py-2.5 bg-[var(--bg-elevated)] hover:bg-red-500/10 border border-[var(--border)] hover:border-red-500/20 rounded-xl text-xs font-bold text-[var(--text-muted)] hover:text-red-500 transition-all cursor-pointer"
            >
              Cancel
            </button>
          </div>
        )}

        {/* ── Microsoft device-code ── */}
        {deviceFlow && (
          <div className="space-y-6 animate-fade-in">
            <p className="text-xs text-[var(--text-muted)] text-center leading-relaxed">
              Open the Microsoft device activation link and enter the one-time authentication code.
            </p>
            <div className="text-center">
              <a
                href={deviceFlow.verificationUri}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-[var(--bg-elevated)] hover:bg-[var(--bg-elevated)]/80 border border-[var(--border)] rounded-xl text-xs font-bold text-[var(--accent-primary)] transition-all cursor-pointer shadow-sm hover:shadow"
                id="login-auth-link"
              >
                1. Open Device Login Page
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
            <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-5 flex flex-col items-center justify-center gap-2">
              <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-extrabold">2. Copy and Enter this Code</span>
              <div className="flex items-center gap-4 mt-1">
                <span className="font-mono text-2xl font-black tracking-widest text-[var(--text-primary)] select-all" id="login-user-code">
                  {deviceFlow.userCode}
                </span>
                <button
                  onClick={handleCopyCode}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-bold transition-all cursor-pointer ${
                    copied
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500'
                      : 'bg-[var(--bg-surface)] hover:bg-[var(--bg-elevated)] border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                  id="btn-login-copy-code"
                >
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <div className="text-xs font-bold text-[var(--text-muted)] flex items-center justify-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] animate-ping shrink-0" />
              <span>Waiting for Microsoft approval…</span>
            </div>
            <button
              onClick={() => {
                if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                setLoading(false);
                setDeviceFlow(null);
              }}
              className="w-full py-2.5 bg-[var(--bg-elevated)] hover:bg-red-500/10 border border-[var(--border)] hover:border-red-500/20 rounded-xl text-xs font-bold text-[var(--text-muted)] hover:text-red-500 transition-all cursor-pointer text-center"
              id="btn-login-cancel"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
