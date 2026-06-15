'use client';

import { useState } from 'react';
import { joinWaitlist } from '../../lib/api';

/**
 * Private-beta waitlist signup, styled for the dark landing page.
 * Collects email + name + use-case and posts to /api/waitlist.
 */
export function WaitlistForm() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [useCase, setUseCase] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'done' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [alreadyApproved, setAlreadyApproved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) {
      setStatus('error');
      setMessage('Please enter your email address.');
      return;
    }
    setStatus('submitting');
    setMessage(null);
    try {
      const res = await joinWaitlist({
        email: email.trim(),
        name: name.trim() || undefined,
        use_case: useCase.trim() || undefined,
      });
      setAlreadyApproved(res.status === 'approved');
      setStatus('done');
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    }
  }

  if (status === 'done') {
    return (
      <div className="relative mx-auto max-w-md rounded-2xl border border-emerald-400/20 bg-emerald-500/[0.06] p-8 text-center backdrop-blur">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 text-2xl text-emerald-300">
          ✓
        </div>
        {alreadyApproved ? (
          <>
            <h3 className="text-lg font-bold text-white">You&apos;re already approved</h3>
            <p className="mt-2 text-sm text-white/55">
              Your email is on the approved list — you can sign in right now.
            </p>
            <a
              href="/login"
              className="mt-5 inline-block rounded-full bg-white px-6 py-2.5 text-sm font-bold text-black transition-transform hover:scale-[1.03] active:scale-[0.98]"
            >
              Go to sign in →
            </a>
          </>
        ) : (
          <>
            <h3 className="text-lg font-bold text-white">You&apos;re on the list</h3>
            <p className="mt-2 text-sm text-white/55">
              Thanks for your interest in MailMind. We&apos;ll email you at{' '}
              <span className="font-medium text-white/80">{email.trim()}</span> when your spot opens up.
            </p>
          </>
        )}
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="relative mx-auto max-w-md rounded-2xl border border-white/10 bg-white/[0.03] p-6 text-left backdrop-blur sm:p-8"
    >
      <div className="space-y-3">
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-white/55">Email *</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/30 transition-colors focus:border-indigo-400/60 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-white/55">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/30 transition-colors focus:border-indigo-400/60 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-semibold text-white/55">
            How would you use MailMind?
          </label>
          <textarea
            value={useCase}
            onChange={(e) => setUseCase(e.target.value)}
            placeholder="Tell us about your inbox and what you're hoping it'll do for you…"
            rows={3}
            className="w-full resize-none rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder-white/30 transition-colors focus:border-indigo-400/60 focus:outline-none"
          />
        </div>
      </div>

      {status === 'error' && message && (
        <div className="mt-4 rounded-lg border border-rose-400/20 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-300">
          {message}
        </div>
      )}

      <button
        type="submit"
        disabled={status === 'submitting'}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 py-3 text-sm font-bold text-white shadow-xl shadow-indigo-500/30 transition-all hover:shadow-indigo-500/50 active:scale-[0.98] disabled:opacity-60"
      >
        {status === 'submitting' ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
        ) : (
          'Request early access'
        )}
      </button>
      <p className="mt-3 text-center text-[11px] text-white/30">
        Private beta · Invite-only · We&apos;ll never share your email
      </p>
    </form>
  );
}
