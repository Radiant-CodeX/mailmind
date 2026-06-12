'use client';

import React from 'react';

interface SignOutModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSignOutSession: () => void;
  onSignOutEverywhere: () => void;
  loading?: boolean;
}

export function SignOutModal({
  isOpen,
  onClose,
  onSignOutSession,
  onSignOutEverywhere,
  loading = false,
}: SignOutModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative w-full max-w-sm bg-[var(--bg-surface)] border border-[var(--border)] rounded-2xl shadow-2xl overflow-hidden animate-fade-in">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-[var(--border-subtle)]">
          <h2 className="text-base font-bold text-[var(--text-primary)]">Sign Out</h2>
          <p className="text-xs text-[var(--text-muted)] mt-1">Choose how you want to sign out.</p>
        </div>

        {/* Options */}
        <div className="p-4 space-y-3">
          {/* Option 1: Session only */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] p-4 space-y-3">
            <div className="space-y-1.5">
              <p className="text-xs font-bold text-[var(--text-primary)]">Sign out of this session</p>
              <ul className="space-y-1">
                {[
                  'Removes the current session',
                  'Keeps Quick Login enabled',
                  "You'll be signed back in automatically on this device",
                ].map((point) => (
                  <li key={point} className="flex items-start gap-1.5 text-[11px] text-[var(--text-muted)]">
                    <span className="text-emerald-500 mt-0.5 shrink-0">✓</span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
            <button
              onClick={onSignOutSession}
              disabled={loading}
              className="w-full py-2 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] text-xs font-bold rounded-lg transition-all disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : 'Sign Out'}
            </button>
          </div>

          {/* Option 2: Full logout */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] p-4 space-y-3">
            <div className="space-y-1.5">
              <p className="text-xs font-bold text-[var(--text-primary)]">Sign out completely</p>
              <ul className="space-y-1">
                {[
                  'Removes current session',
                  'Disables Quick Login',
                  'Requires Google/Microsoft login next time',
                ].map((point) => (
                  <li key={point} className="flex items-start gap-1.5 text-[11px] text-[var(--text-muted)]">
                    <span className="text-amber-500 mt-0.5 shrink-0">✕</span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
            <button
              onClick={onSignOutEverywhere}
              disabled={loading}
              className="w-full py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-500 text-xs font-bold rounded-lg transition-all disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <span className="inline-block w-3 h-3 border-2 border-red-500/30 border-t-red-500 rounded-full animate-spin" />
              ) : 'Sign Out Everywhere'}
            </button>
          </div>
        </div>

        {/* Cancel */}
        <div className="px-4 pb-4">
          <button
            onClick={onClose}
            disabled={loading}
            className="w-full py-2 text-xs font-semibold text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
