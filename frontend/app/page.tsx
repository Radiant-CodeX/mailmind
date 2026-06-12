"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  checkAuthStatus,
  quickLogin,
  googleLoginInitiate,
  googleLoginPoll,
  microsoftLoginInitiate,
  microsoftLoginPoll,
} from "../lib/api";
import {
  getRememberedLogin,
  clearRememberedLogin,
  initialsFor,
  getRememberMe,
  rememberLogin,
  setRememberMe as persistRememberMe,
  RememberedLogin,
  Provider,
} from "../lib/session";

/** Pick the provider for a typed email address. */
function providerForEmail(email: string): Provider {
  const domain = email.split("@")[1]?.toLowerCase() || "";
  if (domain.includes("gmail") || domain.includes("googlemail"))
    return "google";
  return "microsoft";
}

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [authStatus, setAuthStatus] = useState<string>("checking");
  const [remembered, setRemembered] = useState<RememberedLogin | null>(null);
  const [email, setEmail] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [googleWaiting, setGoogleWaiting] = useState(false);
  const [msWaiting, setMsWaiting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signedOutNotice, setSignedOutNotice] = useState<"session" | "full" | null>(null);
  const pollingIntervalRef = React.useRef<NodeJS.Timeout | null>(null);
  const googlePopupRef = React.useRef<Window | null>(null);
  const msPopupRef = React.useRef<Window | null>(null);

  useEffect(() => {
    async function init() {
      const params = new URLSearchParams(window.location.search);
      const signedOut = params.get("signedOut");

      if (signedOut === "full") {
        // Full logout: clear remembered login, skip auth check, show plain login
        clearRememberedLogin();
        setRemembered(null);
        setSignedOutNotice("full");
        setAuthStatus("ready");
        return;
      }

      if (signedOut === "session") {
        // Session-only logout: keep remembered login for Quick Login card,
        // but DON'T auto-redirect even if mm_quick restores a session
        setRemembered(getRememberedLogin());
        setRememberMe(getRememberMe());
        setSignedOutNotice("session");
        setAuthStatus("ready");
        return;
      }

      try {
        const data = await checkAuthStatus();
        if (data.authenticated) {
          router.replace("/dashboard");
          return;
        }
        setRemembered(getRememberedLogin());
        setRememberMe(getRememberMe());
        setAuthStatus("ready");
      } catch (err) {
        console.error("Failed to query status", err);
        setRemembered(getRememberedLogin());
        setAuthStatus("ready");
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

  // ── Microsoft (OAuth popup flow) ───────────────────────────────────────────
  const handleMicrosoft = async (forceOAuth = false) => {
    persistRememberMe(rememberMe);
    setError(null);
    // Open the popup SYNCHRONOUSLY to preserve the click gesture.
    msPopupRef.current = window.open("", "ms-login", "width=520,height=680");
    setLoading(true);
    try {
      const data = await microsoftLoginInitiate();
      if (data.authenticated) {
        msPopupRef.current?.close();
        router.push("/dashboard");
        return;
      }
      if (msPopupRef.current && data.auth_url) {
        msPopupRef.current.location.replace(data.auth_url);
        setMsWaiting(true);
        startMicrosoftPolling(data.state, msPopupRef.current);
      } else if (data.auth_url) {
        window.location.assign(data.auth_url);
      }
    } catch (err: unknown) {
      msPopupRef.current?.close();
      setError(err instanceof Error ? err.message : "Microsoft sign-in failed");
      setLoading(false);
      setMsWaiting(false);
    }
  };

  const startMicrosoftPolling = (state: string, popup: Window | null) => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const data = await microsoftLoginPoll(state);
        if (data.status === "success") {
          if (pollingIntervalRef.current)
            clearInterval(pollingIntervalRef.current);
          popup?.close();
          if (data.user_principal_name && getRememberMe()) {
            rememberLogin(data.user_principal_name, "microsoft");
          }
          router.push("/dashboard");
        }
      } catch (err) {
        if (pollingIntervalRef.current)
          clearInterval(pollingIntervalRef.current);
        setLoading(false);
        setMsWaiting(false);
        setError(
          err instanceof Error ? err.message : "Microsoft sign-in failed",
        );
      }
    }, 2500);
  };

  // ── Google (OAuth popup flow) ──────────────────────────────────────────────
  const handleGoogle = async (emailHint?: string, forceOAuth = false) => {
    persistRememberMe(rememberMe);
    setError(null);
    // Open the popup SYNCHRONOUSLY (inside the click) so the browser keeps the
    // user-gesture and doesn't block it. We navigate it once we have the URL.
    googlePopupRef.current = window.open(
      "",
      "google-login",
      "width=500,height=680",
    );
    setLoading(true);
    try {
      const data = await googleLoginInitiate(emailHint);
      if (data.authenticated) {
        googlePopupRef.current?.close();
        router.push("/dashboard");
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
      setError(err instanceof Error ? err.message : "Google sign-in failed");
      setLoading(false);
      setGoogleWaiting(false);
    }
  };

  const startGooglePolling = (state: string, popup: Window | null) => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const data = await googleLoginPoll(state);
        if (data.status === "success") {
          if (pollingIntervalRef.current)
            clearInterval(pollingIntervalRef.current);
          popup?.close();
          if (data.user_principal_name && getRememberMe()) {
            rememberLogin(data.user_principal_name, "google");
          }
          router.push("/dashboard");
        }
      } catch (err) {
        if (pollingIntervalRef.current)
          clearInterval(pollingIntervalRef.current);
        setLoading(false);
        setGoogleWaiting(false);
        setError(err instanceof Error ? err.message : "Google sign-in failed");
      }
    }, 2500);
  };

  const cancelWaiting = () => {
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    googlePopupRef.current?.close();
    msPopupRef.current?.close();
    setGoogleWaiting(false);
    setMsWaiting(false);
    setLoading(false);
  };

  // ── Email-first "Next" → route to the right provider ───────────────────────
  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }
    // Email-first sign-in respects the typed address → force a fresh OAuth.
    if (providerForEmail(email) === "google") {
      handleGoogle(email, true);
    } else {
      handleMicrosoft(true);
    }
  };

  // ── Quick login / forget ───────────────────────────────────────────────────
  const handleQuickLogin = async () => {
    if (!remembered) return;
    setLoading(true);
    setError(null);
    try {
      // Explicitly activate quick login — validates mm_quick and issues a new session.
      const data = await quickLogin();
      if (data.authenticated) {
        router.push("/dashboard");
        return;
      }
      // mm_quick expired or missing — fall back to full OAuth for the remembered provider.
      setLoading(false);
      if (remembered.provider === "google") {
        handleGoogle(remembered.email, true);
      } else {
        handleMicrosoft(true);
      }
    } catch {
      setLoading(false);
      if (remembered.provider === "google") {
        handleGoogle(remembered.email, true);
      } else {
        handleMicrosoft(true);
      }
    }
  };

  const handleForgetAccount = async () => {
    try {
      const { logoutUser } = await import("../lib/api");
      await logoutUser();
    } catch (err) {
      console.error("Failed to forget account:", err);
    }
    clearRememberedLogin();
    setRemembered(null);
  };

  if (authStatus === "checking") {
    return (
      <div
        className="flex h-screen w-screen items-center justify-center bg-bg-base text-text-primary"
        id="login-checking"
      >
        <div className="text-center">
          <div className="w-8 h-8 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mx-auto mb-4" />
          <p className="text-xs text-[var(--text-muted)] font-medium">
            Checking authorization status...
          </p>
        </div>
      </div>
    );
  }

  const showMainForm = !googleWaiting && !msWaiting;

  return (
    <div
      className="flex h-screen w-screen items-center justify-center bg-bg-base text-text-primary px-4"
      id="login-workspace"
    >
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
          <h1 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
            MailMind
          </h1>
          <p className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-widest mt-0.5">
            Co-pilot Studio
          </p>
        </div>

        {signedOutNotice === "session" && (
          <div className="mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 rounded-lg text-xs font-semibold text-center">
            Signed out of this session. Quick Login is still active.
          </div>
        )}
        {signedOutNotice === "full" && (
          <div className="mb-4 p-3 bg-[var(--bg-elevated)] border border-[var(--border)] text-[var(--text-muted)] rounded-lg text-xs font-semibold text-center">
            Signed out completely. Please sign in again.
          </div>
        )}

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
                      Quick Login ·{" "}
                      {remembered.provider === "google"
                        ? "Google"
                        : "Microsoft"}
                    </p>
                    <p
                      className="text-sm font-bold text-[var(--text-primary)] truncate"
                      title={remembered.email}
                    >
                      {remembered.email}
                    </p>
                  </div>
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-[var(--accent-primary)] border-t-transparent animate-spin rounded-full shrink-0" />
                  ) : (
                    <svg
                      className="w-5 h-5 text-[var(--text-muted)] group-hover:text-[var(--accent-primary)] transition-colors shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.5}
                        d="M9 5l7 7-7 7"
                      />
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
                  <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                    or
                  </span>
                  <div className="flex-1 h-px bg-[var(--border-subtle)]" />
                </div>
              </div>
            )}

            {/* Email + Remember me + Next */}
            <form onSubmit={handleNext} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-muted)] mb-1.5">
                  Email
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
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
                <span className="text-xs font-medium text-[var(--text-muted)]">
                  Remember me
                </span>
              </label>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 disabled:opacity-50 text-[var(--bg-surface)] font-extrabold text-sm rounded-xl cursor-pointer shadow hover:shadow-lg transition-all duration-200 active:scale-95"
                id="btn-login-next"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-[var(--bg-surface)] border-t-transparent animate-spin rounded-full" />
                ) : (
                  "Next"
                )}
              </button>
            </form>

            {/* OR divider */}
            <div className="flex items-center gap-3 py-1">
              <div className="flex-1 h-px bg-[var(--border-subtle)]" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                or
              </span>
              <div className="flex-1 h-px bg-[var(--border-subtle)]" />
            </div>

            {/* Provider buttons */}
            <button
              onClick={() => handleGoogle(email || undefined)}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2.5 py-2.5 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-800 font-bold text-sm rounded-xl cursor-pointer border border-[var(--border)] transition-all active:scale-95"
              id="btn-login-google"
            >
              <svg
                className="w-4 h-4"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </button>

            <button
              onClick={() => handleMicrosoft()}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2.5 py-2.5 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-800 font-bold text-sm rounded-xl cursor-pointer border border-[var(--border)] transition-all active:scale-95"
              id="btn-login-microsoft"
            >
              <svg
                className="w-4 h-4"
                viewBox="0 0 21 21"
                xmlns="http://www.w3.org/2000/svg"
              >
                <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
              </svg>
              Continue with Microsoft
            </button>
          </div>
        )}

        {/* ── Waiting for Microsoft sign-in (popup) ── */}
        {msWaiting && (
          <div className="space-y-5 animate-fade-in text-center">
            <div className="w-14 h-14 rounded-2xl bg-white flex items-center justify-center mx-auto shadow-md border border-[var(--border)]">
              <svg className="w-7 h-7" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
                <rect x="1" y="1" width="9" height="9" fill="#F25022" />
                <rect x="11" y="1" width="9" height="9" fill="#7FBA00" />
                <rect x="1" y="11" width="9" height="9" fill="#00A4EF" />
                <rect x="11" y="11" width="9" height="9" fill="#FFB900" />
              </svg>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-1">
                Sign-in in progress
              </p>
              <p className="text-sm font-bold text-[var(--text-primary)]">
                Microsoft Account
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-2 leading-relaxed">
                Complete the sign-in in the popup window.
                <br />
                If it didn&apos;t open, check your popup blocker.
              </p>
            </div>
            <div className="flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-[#F25022] animate-bounce [animation-delay:-0.3s]" />
              <div className="w-2 h-2 rounded-full bg-[#7FBA00] animate-bounce [animation-delay:-0.15s]" />
              <div className="w-2 h-2 rounded-full bg-[#00A4EF] animate-bounce [animation-delay:0s]" />
              <div className="w-2 h-2 rounded-full bg-[#FFB900] animate-bounce [animation-delay:0.15s]" />
            </div>
            <button
              onClick={cancelWaiting}
              className="w-full py-2.5 bg-[var(--bg-elevated)] hover:bg-red-500/10 border border-[var(--border)] hover:border-red-500/20 rounded-xl text-xs font-bold text-[var(--text-muted)] hover:text-red-500 transition-all cursor-pointer"
            >
              Cancel
            </button>
          </div>
        )}

        {/* ── Waiting for Google sign-in (popup) ── */}
        {googleWaiting && (
          <div className="space-y-5 animate-fade-in text-center">
            <div className="w-14 h-14 rounded-2xl bg-white flex items-center justify-center mx-auto shadow-md border border-[var(--border)]">
              <svg className="w-7 h-7" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] mb-1">
                Sign-in in progress
              </p>
              <p className="text-sm font-bold text-[var(--text-primary)]">
                Google Account
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-2 leading-relaxed">
                Complete the sign-in in the popup window.
                <br />
                If it didn&apos;t open, check your popup blocker.
              </p>
            </div>
            <div className="flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-[#4285F4] animate-bounce [animation-delay:-0.3s]" />
              <div className="w-2 h-2 rounded-full bg-[#EA4335] animate-bounce [animation-delay:-0.15s]" />
              <div className="w-2 h-2 rounded-full bg-[#FBBC05] animate-bounce [animation-delay:0s]" />
              <div className="w-2 h-2 rounded-full bg-[#34A853] animate-bounce [animation-delay:0.15s]" />
            </div>
            <button
              onClick={cancelWaiting}
              className="w-full py-2.5 bg-[var(--bg-elevated)] hover:bg-red-500/10 border border-[var(--border)] hover:border-red-500/20 rounded-xl text-xs font-bold text-[var(--text-muted)] hover:text-red-500 transition-all cursor-pointer"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
