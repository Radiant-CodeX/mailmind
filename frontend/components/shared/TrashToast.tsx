'use client';

import React, { useEffect, useState } from 'react';
import { Email } from '../../lib/types';

const DURATION = 5000; // ms

interface TrashToastProps {
  email: Email;
  startedAt: number;
  onUndo: () => void;
  onDismiss: () => void;
}

export function TrashToast({ email, startedAt, onUndo, onDismiss }: TrashToastProps) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    const tick = () => {
      const elapsed = Date.now() - startedAt;
      const pct = Math.max(0, 100 - (elapsed / DURATION) * 100);
      setProgress(pct);
      if (pct <= 0) onDismiss();
    };

    const id = setInterval(tick, 50);
    return () => clearInterval(id);
  }, [startedAt, onDismiss]);

  const subject = email.subject.length > 42
    ? email.subject.slice(0, 42) + '…'
    : email.subject;

  return (
    <div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[380px] animate-fade-in"
      role="status"
      aria-live="polite"
    >
      <div className="bg-base-200 border border-base-300 rounded-xl shadow-2xl overflow-hidden">
        {/* Content row */}
        <div className="flex items-center gap-3 px-4 py-3">
          {/* Trash icon */}
          <div className="shrink-0 w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </div>

          {/* Text */}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-base-content truncate">{subject}</p>
            <p className="text-[10px] text-base-content/60 font-medium mt-0.5">Moved to Trash</p>
          </div>

          {/* Undo button */}
          <button
            onClick={onUndo}
            className="shrink-0 px-3 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-base-100 text-xs font-bold cursor-pointer transition-all active:scale-95"
          >
            Undo
          </button>

          {/* Close */}
          <button
            onClick={onDismiss}
            className="shrink-0 p-1 rounded-md text-base-content/60 hover:text-base-content hover:bg-base-100 transition-all cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Progress bar */}
        <div className="h-0.5 bg-base-300">
          <div
            className="h-full bg-primary transition-none"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}
