'use client';

import { useId, useState } from 'react';
import { joinWaitlist } from '../../lib/api';

type Status = 'idle' | 'submitting' | 'done' | 'error';

/**
 * Private-beta waitlist signup for the landing page. Posts to /api/waitlist.
 * `inline` is the single-field hero version; `full` also asks for name + use-case.
 */
export function WaitlistForm({ variant = 'full' }: { variant?: 'inline' | 'full' }) {
  const id = useId();
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [useCase, setUseCase] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState<string | null>(null);
  const [alreadyApproved, setAlreadyApproved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) {
      setStatus('error');
      setMessage('Enter your email address to join.');
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
      <div className="lp-done" role="status">
        {alreadyApproved ? (
          <>
            <p className="lp-done-title">You&apos;re already in.</p>
            <p className="lp-done-body">
              This email is on the approved list. <a href="/login">Sign in now</a>.
            </p>
          </>
        ) : (
          <>
            <p className="lp-done-title">You&apos;re on the list.</p>
            <p className="lp-done-body">
              We&apos;ll write to <strong>{email.trim()}</strong> when your spot opens.
            </p>
          </>
        )}
      </div>
    );
  }

  const busy = status === 'submitting';
  const error =
    status === 'error' && message ? (
      <p id={`${id}-err`} className="lp-error" role="alert">
        {message}
      </p>
    ) : null;

  if (variant === 'inline') {
    return (
      <form onSubmit={handleSubmit} className="lp-inline" noValidate>
        <label htmlFor={`${id}-email`} className="sr-only">
          Email address
        </label>
        <div className="lp-inline-row">
          <input
            id={`${id}-email`}
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            aria-invalid={status === 'error'}
            aria-describedby={error ? `${id}-err` : undefined}
            className="lp-input"
          />
          <button type="submit" disabled={busy} className="lp-btn">
            {busy ? 'Joining…' : 'Join the waitlist'}
          </button>
        </div>
        {error}
      </form>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="lp-form" noValidate>
      <div className="lp-field">
        <label htmlFor={`${id}-email`}>Email</label>
        <input
          id={`${id}-email`}
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-invalid={status === 'error'}
          aria-describedby={error ? `${id}-err` : undefined}
          className="lp-input"
        />
      </div>
      <div className="lp-field">
        <label htmlFor={`${id}-name`}>
          Name <span>optional</span>
        </label>
        <input
          id={`${id}-name`}
          type="text"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="lp-input"
        />
      </div>
      <div className="lp-field">
        <label htmlFor={`${id}-use`}>
          What&apos;s your inbox like? <span>optional</span>
        </label>
        <textarea
          id={`${id}-use`}
          rows={3}
          value={useCase}
          onChange={(e) => setUseCase(e.target.value)}
          placeholder="Final-year student drowning in placement mail, a faculty advisor, a freelancer…"
          className="lp-input"
        />
      </div>
      {error}
      <button type="submit" disabled={busy} className="lp-btn lp-btn-block">
        {busy ? 'Joining…' : 'Request early access'}
      </button>
      <p className="lp-fine">Private beta. We only use your email to invite you.</p>
    </form>
  );
}
