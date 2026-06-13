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
      <div className="relative w-full max-w-sm bg-base-100 border border-base-300 rounded-2xl shadow-2xl overflow-hidden animate-fade-in">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-base-200">
          <h2 className="text-base font-bold text-base-content">Sign Out</h2>
          <p className="text-xs text-base-content/60 mt-1">Choose how you want to sign out.</p>
        </div>

        {/* Options */}
        <div className="p-4 space-y-3">
          {/* Option 1: Session only */}
          <div className="rounded-xl border border-base-300 bg-base-200 p-4 space-y-3">
            <div className="space-y-1.5">
              <p className="text-xs font-bold text-base-content">Sign out of this session</p>
              <ul className="space-y-1">
                {[
                  'Removes the current session',
                  'Keeps Quick Login enabled',
                  "You'll be signed back in automatically on this device",
                ].map((point) => (
                  <li key={point} className="flex items-start gap-1.5 text-[11px] text-base-content/60">
                    <span className="text-emerald-500 mt-0.5 shrink-0">✓</span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
            <button
              onClick={onSignOutSession}
              disabled={loading}
              className="w-full py-2 bg-primary hover:opacity-90 text-base-100 text-xs font-bold rounded-lg transition-all disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : 'Sign Out'}
            </button>
          </div>

          {/* Option 2: Full logout */}
          <div className="rounded-xl border border-base-300 bg-base-200 p-4 space-y-3">
            <div className="space-y-1.5">
              <p className="text-xs font-bold text-base-content">Sign out completely</p>
              <ul className="space-y-1">
                {[
                  'Removes current session',
                  'Disables Quick Login',
                  'Requires Google/Microsoft login next time',
                ].map((point) => (
                  <li key={point} className="flex items-start gap-1.5 text-[11px] text-base-content/60">
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
            className="w-full py-2 text-xs font-semibold text-base-content/60 hover:text-base-content transition-colors cursor-pointer disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
