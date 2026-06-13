'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Priority } from '../../lib/types';

export type OverridePriority = Priority | 'DONE';

interface PriorityOverrideMenuProps {
  current: Priority;
  /** Renders the clickable trigger (usually the priority badge). */
  children: React.ReactNode;
  onOverride: (priority: OverridePriority) => void;
}

const OPTIONS: { value: OverridePriority; label: string; dot: string }[] = [
  { value: 'CRITICAL', label: 'Critical', dot: 'bg-red-500' },
  { value: 'HIGH', label: 'High', dot: 'bg-orange-500' },
  { value: 'MEDIUM', label: 'Medium', dot: 'bg-amber-500' },
  { value: 'LOW', label: 'Low', dot: 'bg-slate-500' },
  { value: 'DONE', label: 'Mark Done', dot: 'bg-emerald-500' },
];

/**
 * A deliberate, two-step popup for correcting an email's triage priority.
 * Opening the popup then picking an option (which then asks to confirm)
 * guards against accidental changes, and the choice feeds the triage loop.
 */
export function PriorityOverrideMenu({ current, children, onOverride }: PriorityOverrideMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [pending, setPending] = useState<OverridePriority | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
        setPending(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  const apply = (p: OverridePriority) => {
    onOverride(p);
    setIsOpen(false);
    setPending(null);
  };

  return (
    <div ref={ref} className="relative inline-flex" id="priority-override">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setIsOpen((v) => !v); setPending(null); }}
        className="inline-flex items-center gap-0.5 cursor-pointer group/po"
        title="Override priority"
      >
        {children}
        <svg className="w-3 h-3 text-base-content/40 group-hover/po:text-base-content/70 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute right-0 top-full mt-1.5 z-50 w-48 rounded-xl bg-base-100 border border-base-300 shadow-xl p-1.5 animate-fade-in"
        >
          {pending === null ? (
            <>
              <div className="px-2 py-1.5 text-[9px] font-bold uppercase tracking-widest text-base-content/50">
                Override priority
              </div>
              {OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setPending(opt.value)}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-bold text-left transition-colors hover:bg-base-200 ${
                    opt.value === current ? 'text-base-content/40' : 'text-base-content'
                  }`}
                  disabled={opt.value === current}
                >
                  <span className={`w-2 h-2 rounded-full ${opt.dot}`} />
                  {opt.label}
                  {opt.value === current && <span className="ml-auto text-[9px] font-normal">current</span>}
                </button>
              ))}
            </>
          ) : (
            <div className="p-1.5">
              <p className="text-[11px] font-semibold text-base-content px-1 mb-2.5 leading-snug">
                Change to <span className="font-black">{OPTIONS.find((o) => o.value === pending)?.label}</span>?
                <span className="block text-[9px] font-normal text-base-content/50 mt-1">
                  Teaches MailMind how to triage this sender.
                </span>
              </p>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => apply(pending)}
                  className="flex-1 px-2 py-1.5 rounded-lg bg-primary text-base-100 text-[10px] font-bold hover:opacity-90 cursor-pointer"
                >
                  Confirm
                </button>
                <button
                  type="button"
                  onClick={() => setPending(null)}
                  className="px-2 py-1.5 rounded-lg bg-base-200 text-base-content/70 text-[10px] font-bold hover:bg-base-300 cursor-pointer"
                >
                  Back
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
