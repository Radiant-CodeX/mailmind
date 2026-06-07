'use client';

import React from 'react';
import { reportError } from '../../lib/monitoring';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Optional custom fallback renderer */
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * App-level error boundary. Catches render-time errors anywhere below it,
 * reports them to the monitoring sink, and shows a recoverable fallback
 * instead of a blank white screen.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    reportError(error, { componentStack: info.componentStack });
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) return this.props.fallback(error, this.reset);

    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[var(--bg-base)] text-[var(--text-primary)] px-4">
        <div className="max-w-md w-full bg-[var(--bg-surface)] border border-[var(--border)] rounded-2xl shadow-2xl p-8 text-center">
          <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-lg font-bold text-[var(--text-primary)]">Something went wrong</h1>
          <p className="text-xs text-[var(--text-muted)] mt-2 leading-relaxed">
            An unexpected error occurred. You can try again — if it keeps happening, reload the page.
          </p>
          <pre className="mt-4 text-[10px] text-left text-[var(--text-muted)] bg-[var(--bg-elevated)] rounded-lg p-3 overflow-x-auto max-h-24">
            {error.message}
          </pre>
          <button
            onClick={this.reset}
            className="mt-5 w-full py-2.5 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 text-[var(--bg-surface)] font-bold text-sm rounded-xl cursor-pointer transition-all active:scale-95"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }
}
