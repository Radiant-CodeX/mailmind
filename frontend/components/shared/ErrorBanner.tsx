import React from 'react';

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      className="p-4 bg-red-950/30 border border-[var(--accent-critical)]/40 rounded-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-left w-full max-w-xl mx-auto my-4 animate-fade-in"
      id="error-banner"
    >
      <div className="flex items-start gap-3">
        <div className="text-[var(--accent-critical)] shrink-0 mt-0.5">
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-[var(--text-primary)]">Operational Error</h4>
          <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1.5 text-xs font-medium bg-[var(--bg-elevated)] border border-[var(--border)] hover:bg-[var(--border-subtle)] text-[var(--text-primary)] rounded transition-all shrink-0 cursor-pointer"
        >
          Try Again
        </button>
      )}
    </div>
  );
}
