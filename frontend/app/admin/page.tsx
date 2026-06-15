'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  adminListWaitlist,
  adminApproveEmail,
  adminRejectEmail,
  adminListFeedback,
  WaitlistEntry,
  AdminFeedbackEntry,
} from '../../lib/api';

const TOKEN_KEY = 'mm_admin_token';

type Tab = 'waitlist' | 'feedback';

export default function AdminPage() {
  const [token, setToken] = useState('');
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState<Tab>('waitlist');

  // On mount, restore a saved token (validation happens on first fetch).
  useEffect(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null;
    if (saved) {
      setToken(saved);
      setAuthed(true);
    }
  }, []);

  if (!authed) {
    return <TokenGate onSubmit={(t) => { localStorage.setItem(TOKEN_KEY, t); setToken(t); setAuthed(true); }} />;
  }

  const signOut = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken('');
    setAuthed(false);
  };

  return (
    <div className="min-h-screen bg-base-300 text-base-content">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight">MailMind Admin</h1>
            <p className="text-xs text-base-content/50">Waitlist approvals &amp; product feedback</p>
          </div>
          <button
            onClick={signOut}
            className="rounded-lg border border-base-300 bg-base-100 px-3 py-1.5 text-xs font-bold text-base-content/60 transition-colors hover:text-base-content"
          >
            Lock
          </button>
        </div>

        <div className="mb-5 flex gap-2">
          {(['waitlist', 'feedback'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-4 py-2 text-xs font-bold capitalize transition-all ${
                tab === t
                  ? 'bg-primary text-base-100'
                  : 'bg-base-100 text-base-content/60 hover:text-base-content'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === 'waitlist' ? (
          <WaitlistPanel token={token} onUnauthorized={signOut} />
        ) : (
          <FeedbackPanel token={token} onUnauthorized={signOut} />
        )}
      </div>
    </div>
  );
}

function TokenGate({ onSubmit }: { onSubmit: (t: string) => void }) {
  const [value, setValue] = useState('');
  return (
    <div className="flex min-h-screen items-center justify-center bg-base-300 px-4">
      <form
        onSubmit={(e) => { e.preventDefault(); if (value.trim()) onSubmit(value.trim()); }}
        className="w-full max-w-sm rounded-2xl border border-base-300 bg-base-100 p-8 shadow-2xl"
      >
        <h1 className="text-center text-lg font-bold text-base-content">Admin Access</h1>
        <p className="mb-6 mt-1 text-center text-xs text-base-content/50">
          Enter the admin token to manage the waitlist.
        </p>
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Admin token"
          autoFocus
          className="w-full rounded-xl border border-base-300 bg-base-200 px-4 py-2.5 text-sm text-base-content placeholder-base-content/40 focus:border-primary focus:outline-none"
        />
        <button
          type="submit"
          className="mt-4 w-full rounded-xl bg-primary py-2.5 text-sm font-bold text-base-100 transition-all hover:bg-primary/90 active:scale-95"
        >
          Unlock
        </button>
      </form>
    </div>
  );
}

function useUnauthorizedGuard(onUnauthorized: () => void) {
  return useCallback(
    (err: unknown) => {
      const status = (err as { status?: number })?.status;
      if (status === 401 || status === 403) onUnauthorized();
    },
    [onUnauthorized],
  );
}

function WaitlistPanel({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const guard = useUnauthorizedGuard(onUnauthorized);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminListWaitlist(token);
      setEntries(data.entries);
      setCounts(data.counts);
    } catch (err) {
      guard(err);
      setError(err instanceof Error ? err.message : 'Failed to load waitlist');
    } finally {
      setLoading(false);
    }
  }, [token, guard]);

  useEffect(() => { load(); }, [load]);

  const act = async (email: string, action: 'approve' | 'reject') => {
    setBusy(email);
    try {
      if (action === 'approve') await adminApproveEmail(token, email);
      else await adminRejectEmail(token, email);
      await load();
    } catch (err) {
      guard(err);
      setError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <Loader label="Loading waitlist…" />;
  if (error) return <ErrorBox message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex gap-3 text-xs">
        <Stat label="Pending" value={counts.pending || 0} color="text-amber-500" />
        <Stat label="Approved" value={counts.approved || 0} color="text-emerald-500" />
        <Stat label="Rejected" value={counts.rejected || 0} color="text-rose-500" />
      </div>

      {entries.length === 0 && (
        <p className="rounded-xl border border-base-300 bg-base-100 p-8 text-center text-sm text-base-content/50">
          No waitlist entries yet.
        </p>
      )}

      <div className="space-y-2">
        {entries.map((e) => (
          <div key={e.id} className="rounded-xl border border-base-300 bg-base-100 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-bold text-base-content">{e.name || e.email}</span>
                  <StatusBadge status={e.status} />
                  {e.source === 'login' && (
                    <span className="rounded bg-base-200 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-base-content/40">
                      tried login
                    </span>
                  )}
                </div>
                <p className="truncate text-xs text-base-content/50">{e.email}</p>
                {e.use_case && (
                  <p className="mt-2 max-w-2xl whitespace-pre-wrap text-xs leading-relaxed text-base-content/70">
                    {e.use_case}
                  </p>
                )}
                <p className="mt-1.5 text-[10px] text-base-content/30">
                  Joined {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                </p>
              </div>
              <div className="flex shrink-0 gap-2">
                {e.status !== 'approved' && (
                  <button
                    disabled={busy === e.email}
                    onClick={() => act(e.email, 'approve')}
                    className="rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-bold text-emerald-500 transition-colors hover:bg-emerald-500/25 disabled:opacity-50"
                  >
                    Approve
                  </button>
                )}
                {e.status !== 'rejected' && (
                  <button
                    disabled={busy === e.email}
                    onClick={() => act(e.email, 'reject')}
                    className="rounded-lg bg-rose-500/10 px-3 py-1.5 text-xs font-bold text-rose-500 transition-colors hover:bg-rose-500/20 disabled:opacity-50"
                  >
                    Reject
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeedbackPanel({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [entries, setEntries] = useState<AdminFeedbackEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const guard = useUnauthorizedGuard(onUnauthorized);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminListFeedback(token);
      setEntries(data.entries);
    } catch (err) {
      guard(err);
      setError(err instanceof Error ? err.message : 'Failed to load feedback');
    } finally {
      setLoading(false);
    }
  }, [token, guard]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Loader label="Loading feedback…" />;
  if (error) return <ErrorBox message={error} onRetry={load} />;
  if (entries.length === 0)
    return (
      <p className="rounded-xl border border-base-300 bg-base-100 p-8 text-center text-sm text-base-content/50">
        No feedback submitted yet.
      </p>
    );

  return (
    <div className="space-y-2">
      {entries.map((f) => (
        <div key={f.id} className="rounded-xl border border-base-300 bg-base-100 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-amber-500">{'★'.repeat(f.rating)}<span className="text-base-content/20">{'★'.repeat(5 - f.rating)}</span></span>
              <span className="rounded bg-base-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-base-content/60">
                {f.category}
              </span>
            </div>
            <span className="text-[10px] text-base-content/30">
              {f.timestamp ? new Date(f.timestamp).toLocaleString() : '—'}
            </span>
          </div>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-base-content/80">{f.message}</p>
          <p className="mt-2 text-[10px] text-base-content/40">
            {f.user_email || 'anonymous'}{f.role ? ` · ${f.role}` : ''}
          </p>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-base-300 bg-base-100 px-3 py-1.5">
      <span className={`text-sm font-black tabular-nums ${color}`}>{value}</span>
      <span className="text-[10px] font-bold uppercase tracking-wide text-base-content/40">{label}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: 'bg-amber-500/15 text-amber-500',
    approved: 'bg-emerald-500/15 text-emerald-500',
    rejected: 'bg-rose-500/15 text-rose-500',
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${map[status] || 'bg-base-200 text-base-content/50'}`}>
      {status}
    </span>
  );
}

function Loader({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="mb-3 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <p className="text-xs text-base-content/50">{label}</p>
    </div>
  );
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-5 text-center">
      <p className="text-sm font-semibold text-rose-500">{message}</p>
      <button onClick={onRetry} className="mt-3 rounded-lg bg-base-100 px-4 py-1.5 text-xs font-bold text-base-content/70 hover:text-base-content">
        Retry
      </button>
    </div>
  );
}
