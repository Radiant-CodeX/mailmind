'use client';

import React, { useEffect, useRef, useState } from 'react';
import { MailFilters, DateRange, DEFAULT_FILTERS } from '../../hooks/useEmails';

interface FilterMenuProps {
  value: MailFilters;
  onChange: (f: MailFilters) => void;
}

const DATE_OPTIONS: { key: DateRange; label: string }[] = [
  { key: 'all', label: 'Any time' },
  { key: 'today', label: 'Last 24 hours' },
  { key: 'week', label: 'Last 7 days' },
  { key: 'month', label: 'Last 30 days' },
];

export function FilterMenu({ value, onChange }: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const activeCount =
    (value.dateRange !== 'all' ? 1 : 0) + (value.unreadOnly ? 1 : 0) + (value.attachmentsOnly ? 1 : 0);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1 p-1.5 rounded-md hover:bg-base-200 transition-all cursor-pointer ${
          activeCount ? 'text-primary' : 'text-base-content/60 hover:text-base-content'
        }`}
        title="Filters"
        id="btn-filter-emails"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L15 12.414V19a1 1 0 01-.553.894l-4 2A1 1 0 019 21v-8.586L3.293 6.707A1 1 0 013 6V4z" />
        </svg>
        {activeCount > 0 && (
          <span className="text-[9px] font-bold bg-primary text-base-100 rounded-full w-4 h-4 flex items-center justify-center">
            {activeCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 w-60 bg-base-100 border border-base-300 rounded-xl shadow-2xl p-3 z-50 animate-fade-in">
          <div className="text-[10px] font-bold uppercase tracking-widest text-base-content/60 mb-2">Date</div>
          <div className="grid grid-cols-2 gap-1.5 mb-3">
            {DATE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => onChange({ ...value, dateRange: opt.key })}
                className={`px-2 py-1.5 rounded-lg text-[11px] font-semibold transition-all cursor-pointer ${
                  value.dateRange === opt.key
                    ? 'bg-primary text-base-100'
                    : 'bg-base-200 text-base-content hover:bg-base-200/70'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <div className="text-[10px] font-bold uppercase tracking-widest text-base-content/60 mb-2">Show only</div>
          <label className="flex items-center gap-2 px-1 py-1.5 cursor-pointer text-xs text-base-content">
            <input type="checkbox" checked={value.unreadOnly}
              onChange={(e) => onChange({ ...value, unreadOnly: e.target.checked })}
              className="w-4 h-4 accent-primary cursor-pointer" />
            Unread
          </label>
          <label className="flex items-center gap-2 px-1 py-1.5 cursor-pointer text-xs text-base-content">
            <input type="checkbox" checked={value.attachmentsOnly}
              onChange={(e) => onChange({ ...value, attachmentsOnly: e.target.checked })}
              className="w-4 h-4 accent-primary cursor-pointer" />
            Has attachments
          </label>

          {activeCount > 0 && (
            <button
              onClick={() => onChange(DEFAULT_FILTERS)}
              className="mt-2 w-full text-[11px] font-bold text-base-content/60 hover:text-red-500 transition-colors cursor-pointer py-1"
            >
              Clear filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
