'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { checkAuthStatus, loginInitiate, loginPoll, loginMock, quickLogin } from '../lib/api';
import {
  getRememberedLogin,
  clearRememberedLogin,
  initialsFor,
  RememberedLogin,
} from '../lib/session';

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'idle' | 'mock' | 'live'>('idle');
  const [authStatus, setAuthStatus] = useState<string>('checking');
  const [remembered, setRemembered] = useState<RememberedLogin | null>(null);
  const [deviceFlow, setDeviceFlow] = useState<{
    userCode: string;
    verificationUri: string;
    deviceCode: string;
    message: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const pollingIntervalRef = React.useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const data = await checkAuthStatus();
        // Quick resume: a live/mock session is already active — go straight in.
        if (data.authenticated) {
          router.replace('/dashboard');
          return;
        }
        setMode((data.status === 'mock' || data.status === 'mock_unauthenticated') ? 'mock' : 'live');
        setRemembered(getRememberedLogin());
        setAuthStatus('ready');
      } catch (err) {
        console.error('Failed to query status', err);
        setMode('live');
        setRemembered(getRememberedLogin());
        setAuthStatus('ready');
      }
    }
    init();
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [router]);

  const handleMockLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      await loginMock();
      router.push('/dashboard');
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Mock login failed';
      setError(errorMessage);
      setLoading(false);
    }
  };

  // One-tap login using the remembered account — goes straight into MailMind
  // with no device code / password prompt.
  const handleQuickLogin = async () => {
    if (!remembered) return;
    setLoading(true);
    setError(null);
    try {
      await quickLogin(remembered.email);
      router.push('/dashboard');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Quick login failed';
      setError(msg);
      setLoading(false);
    }
  };

  const handleForgetAccount = () => {
    clearRememberedLogin();
    setRemembered(null);
  };

  const handleInitiateLogin = async () => {
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

      startPolling(data.device_code);
    } catch (err: unknown) {
      console.error(err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to initiate login flow';
      setError(errorMessage);
      setLoading(false);
    }
  };

  const startPolling = (deviceCode: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    const interval = setInterval(async () => {
      try {
        const data = await loginPoll(deviceCode);
        if (data.status === 'success') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          router.push('/dashboard');
        } else if (data.status === 'pending') {
          // keep polling
        } else {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          setLoading(false);
          setDeviceFlow(null);
          setError('Authentication flow expired or cancelled.');
        }
      } catch (err) {
        console.error('Poll error', err);
        if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
        setLoading(false);
        setDeviceFlow(null);
        const errMsg = err instanceof Error ? err.message : 'Connection lost during polling.';
        setError(errMsg);
      }
    }, 4000);
    pollingIntervalRef.current = interval;
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
          <div className="w-8 h-8 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mx-auto mb-4"></div>
          <p className="text-xs text-[var(--text-muted)] font-medium">Checking authorization status...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-bg-base text-text-primary px-4" id="login-workspace">
      <div className="relative w-full max-w-md bg-[var(--bg-surface)] border border-[var(--border)] rounded-2xl shadow-2xl p-8 overflow-hidden">
        {/* Glow decoration */}
        <div className="absolute -right-16 -top-16 w-36 h-36 rounded-full bg-[var(--accent-primary)]/10 blur-2xl"></div>

        {/* Brand Header */}
        <div className="text-center mb-8 flex flex-col items-center">
          <div className="w-12 h-12 rounded-xl bg-[var(--accent-primary)] flex items-center justify-center text-[var(--bg-surface)] font-extrabold text-xl shadow mb-4">
            MM
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">MailMind</h1>
          <p className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-widest mt-0.5">
            Co-pilot Studio
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs font-semibold text-center">
            {error}
          </div>
        )}

        {!deviceFlow ? (
          <div className="space-y-4">
            {/* Quick Login — one-tap continue with the last-used account */}
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
                      Quick Login
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

            {!remembered && (
              <p className="text-xs text-[var(--text-muted)] text-center leading-relaxed mb-6">
                Welcome back. Sign in to analyze, score, and draft calendar-aware actions on your Outlook inbox.
              </p>
            )}

            {mode === 'mock' ? (
              <div className="space-y-3">
                <div className="p-3.5 bg-amber-500/10 border border-amber-500/20 text-amber-500 rounded-xl text-xs font-semibold flex items-center gap-2 mb-4 leading-relaxed">
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>Mock Mode Enabled. Outlook sign-in is bypassed.</span>
                </div>
                
                <button
                  onClick={handleMockLogin}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 py-3 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 disabled:opacity-50 text-[var(--bg-surface)] font-extrabold text-sm rounded-xl cursor-pointer shadow hover:shadow-lg transition-all duration-200 active:scale-95"
                  id="btn-login-demo"
                >
                  {loading ? 'Entering...' : 'Enter Demo Studio'}
                </button>
              </div>
            ) : (
              <button
                onClick={handleInitiateLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 disabled:opacity-50 text-[var(--bg-surface)] font-extrabold text-sm rounded-xl cursor-pointer shadow hover:shadow-lg transition-all duration-200 active:scale-95"
                id="btn-login-microsoft"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-[var(--bg-surface)] border-t-transparent animate-spin rounded-full"></div>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                  </svg>
                )}
                {loading ? 'Initializing Flow...' : 'Sign In with Microsoft'}
              </button>
            )}
          </div>
        ) : (
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
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>

            <div className="bg-[var(--bg-elevated)] border border-[var(--border)] rounded-xl p-5 flex flex-col items-center justify-center gap-2">
              <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-extrabold">
                2. Copy and Enter this Code
              </span>
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
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-primary)] animate-ping shrink-0"></span>
              <span>Waiting for Microsoft approval...</span>
            </div>

            <button
              onClick={() => {
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
