import React from 'react';
import { BASE } from '../../lib/api';

interface HeaderProps {
  themeMode: 'light' | 'dark';
  onToggleTheme: () => void;
  isMockMode: boolean;
}

export function Header({ themeMode, onToggleTheme, isMockMode }: HeaderProps) {
  return (
    <header className="h-16 border-b border-[var(--border)] px-6 flex items-center justify-between bg-[var(--bg-surface)] w-full" id="header">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-bold text-[var(--text-primary)]">Triage Workspace</h1>
        <div className="h-4 w-[1px] bg-[var(--border)]"></div>
        {isMockMode ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 text-[10px] font-semibold tracking-wide uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 dark:bg-amber-400 animate-pulse"></span>
            Mock Mode Active
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold tracking-wide uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400 animate-pulse"></span>
            Live Account Connected
          </div>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
        {/* Dark / Light Mode Toggle Button */}
        <button
          onClick={onToggleTheme}
          className="p-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border)] hover:bg-[var(--border-subtle)] text-[var(--text-primary)] transition-all cursor-pointer flex items-center gap-1.5 font-semibold text-[10px] uppercase tracking-wide"
          title={themeMode === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          id="theme-toggle"
        >
          {themeMode === 'light' ? (
            <>
              {/* Moon Icon */}
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
              Dark Mode
            </>
          ) : (
            <>
              {/* Sun Icon */}
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
              Light Mode
            </>
          )}
        </button>

        <div className="h-4 w-[1px] bg-[var(--border)]"></div>
        
        <div className="flex items-center gap-2">
          <span>API Base:</span>
          <code className="px-2 py-1 rounded bg-[var(--bg-elevated)] border border-[var(--border)] text-[var(--text-primary)] font-mono text-[10px]">
            {BASE}
          </code>
        </div>
      </div>
    </header>
  );
}
