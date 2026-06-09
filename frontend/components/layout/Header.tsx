import React from 'react';

interface HeaderProps {
  themeMode: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function Header({ themeMode, onToggleTheme }: HeaderProps) {
  return (
    <header className="h-16 border-b border-[var(--border)] px-6 flex items-center justify-between bg-[var(--bg-surface)] w-full" id="header">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-bold text-[var(--text-primary)]">Triage Workspace</h1>
      </div>

      <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
        <button
          onClick={onToggleTheme}
          className="p-1.5 rounded-md bg-[var(--bg-elevated)] border border-[var(--border)] hover:bg-[var(--border-subtle)] text-[var(--text-primary)] transition-all cursor-pointer flex items-center gap-1.5 font-semibold text-[10px] uppercase tracking-wide"
          title={themeMode === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          id="theme-toggle"
        >
          {themeMode === 'light' ? (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
              Dark Mode
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
              </svg>
              Light Mode
            </>
          )}
        </button>
      </div>
    </header>
  );
}
