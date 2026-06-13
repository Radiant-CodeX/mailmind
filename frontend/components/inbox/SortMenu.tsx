'use client';

import React, { useEffect, useRef, useState } from 'react';
import { SortKey } from '../../hooks/useEmails';

interface SortOption {
  key: SortKey;
  label: string;
}

const OPTIONS: SortOption[] = [
  { key: 'normal', label: 'Default order' },
  { key: 'date_desc', label: 'Newest first' },
  { key: 'date_asc', label: 'Oldest first' },
  { key: 'score_desc', label: 'Highest triage score' },
  { key: 'score_asc', label: 'Lowest triage score' },
];

interface SortMenuProps {
  value: SortKey;
  onChange: (key: SortKey) => void;
}

export function SortMenu({ value, onChange }: SortMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const active = OPTIONS.find((o) => o.key === value) ?? OPTIONS[0];
  const isCustom = value !== 'normal';

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1 p-1.5 rounded-md hover:bg-base-200 transition-all cursor-pointer ${
          isCustom ? 'text-primary' : 'text-base-content/60 hover:text-base-content'
        }`}
        title={`Sort: ${active.label}`}
        id="btn-sort-emails"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4 4m0 0l4-4m-4 4V4" />
        </svg>
        {isCustom && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
      </button>

      {open && (
        <div
          className="absolute right-0 mt-1.5 w-52 bg-base-100 border border-base-300 rounded-xl shadow-2xl py-1.5 z-50 animate-fade-in"
          role="listbox"
        >
          <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-base-content/60">
            Sort by
          </div>
          {OPTIONS.map((opt) => {
            const selected = opt.key === value;
            return (
              <button
                key={opt.key}
                onClick={() => {
                  onChange(opt.key);
                  setOpen(false);
                }}
                role="option"
                aria-selected={selected}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-xs font-medium text-left transition-all cursor-pointer ${
                  selected
                    ? 'bg-primary/10 text-primary'
                    : 'text-base-content hover:bg-base-200'
                }`}
              >
                <span>{opt.label}</span>
                {selected && (
                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
