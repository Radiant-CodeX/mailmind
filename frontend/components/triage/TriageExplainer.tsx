import React from 'react';
import { TriageResult, ClassificationResult } from '../../lib/types';

interface TriageExplainerProps {
  triage: TriageResult;
  classification: ClassificationResult | null;
}

export function TriageExplainer({ triage, classification }: TriageExplainerProps) {
  const getBarColor = (name: string) => {
    switch (name.toLowerCase()) {
      case 'deadline': return 'bg-red-500';
      case 'authority': return 'bg-sky-500';
      case 'sentiment': return 'bg-pink-500';
      case 'decay': return 'bg-amber-500';
      case 'action': return 'bg-emerald-500';
      default: return 'bg-slate-500';
    }
  };

  const formatAxisName = (name: string) => {
    return name.replace('_', ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  return (
    <div className="text-left space-y-4" id="triage-explainer">
      {/* Header Info */}
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] pb-2.5">
        <div>
          <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">Triage Breakdown</h4>
          <p className="text-[9px] text-[var(--text-muted)] mt-0.5">NLP priority dimension metrics</p>
        </div>
        {classification && (
          <div className="text-right">
            <span className="text-[9px] text-[var(--text-muted)] block font-semibold">Category / Confidence</span>
            <span className="text-xs font-bold text-[var(--text-primary)]">
              {classification.category.toUpperCase()} ({Math.round(classification.confidence * 100)}%)
            </span>
          </div>
        )}
      </div>

      {/* Axis Scores List */}
      <div className="space-y-3.5">
        {triage.axes.map((axis) => {
          const pct = Math.round(axis.raw_score * 100);
          return (
            <div key={axis.axis} className="space-y-1" id={`axis-row-${axis.axis}`}>
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-[var(--text-primary)]">
                  {formatAxisName(axis.axis)}
                </span>
                <span className="font-mono font-bold text-[var(--text-primary)]">{pct}%</span>
              </div>
              <div className="w-full h-1.5 bg-[var(--bg-base)] rounded-full overflow-hidden relative">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${getBarColor(axis.axis)}`}
                  style={{ width: `${pct}%` }}
                ></div>
              </div>
              {axis.explanation && (
                <p className="text-[9px] text-[var(--text-muted)] leading-tight pl-0.5">
                  {axis.explanation}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Composite priority summary */}
      <div className="p-3 rounded-lg bg-[var(--bg-elevated)]/60 border border-[var(--border-subtle)] space-y-2.5">
        <div>
          <div className="flex justify-between text-xs font-medium mb-1">
            <span className="text-[var(--text-muted)]">Composite Priority Index</span>
            <span className="text-[var(--text-primary)] font-bold">{Math.round(triage.composite_score)} / 100</span>
          </div>
          <div className="w-full h-2 bg-[var(--bg-base)] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700 bg-gradient-to-r from-sky-400 via-amber-400 to-rose-500"
              style={{ width: `${triage.composite_score}%` }}
            ></div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-[var(--border-subtle)]">
          <span className="text-[9px] text-[var(--text-muted)] uppercase font-bold tracking-wider">Gate Status</span>
          <span className={`text-[9px] font-black tracking-wider px-2 py-0.5 rounded ${
            triage.approval_mode === 'GATE'
              ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
              : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
          }`}>
            {triage.approval_mode === 'GATE' ? 'APPROVAL REQUIRED' : 'SUGGEST ONLY'}
          </span>
        </div>
      </div>
    </div>
  );
}
