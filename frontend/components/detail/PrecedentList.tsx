import React from 'react';
import { PrecedentItem } from '../../lib/types';

interface PrecedentListProps {
  precedents: PrecedentItem[];
}

export function PrecedentList({ precedents }: PrecedentListProps) {
  if (precedents.length === 0) return null;

  return (
    <div className="mt-6 text-left" id="precedent-list">
      <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider mb-3 flex items-center gap-1.5">
        <svg
          className="w-4 h-4 text-[var(--accent-primary)]"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
          />
        </svg>
        RAG Precedents (Tone & Context)
      </h4>
      <div className="space-y-3">
        {precedents.slice(0, 3).map((item, idx) => (
          <div
            key={item.email_id || idx}
            className="p-3 bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-lg hover:border-[var(--border)] transition-all"
          >
            <div className="flex justify-between items-start mb-1 gap-2">
              <span className="text-xs font-semibold text-[var(--text-primary)] truncate">
                {item.subject}
              </span>
              <span className="px-1.5 py-0.5 rounded bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] font-mono text-[9px] font-bold">
                {Math.round(item.similarity_score * 100)}% match
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)] line-clamp-2 leading-relaxed">
              {item.snippet}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
