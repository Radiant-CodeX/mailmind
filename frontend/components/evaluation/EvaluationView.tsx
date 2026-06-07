'use client';

import React, { useState, useCallback } from 'react';
import { fetchEvaluation } from '../../lib/api';

interface EvalResult {
  subject: string;
  expected: string;
  predicted: string;
  is_correct: boolean;
}

interface EvalData {
  accuracy: number;
  total_samples: number;
  correct_predictions: number;
  results: EvalResult[];
}

const PRIORITY_COLORS: Record<string, string> = {
  Critical: 'text-red-500 bg-red-500/10 border-red-500/20',
  High:     'text-orange-500 bg-orange-500/10 border-orange-500/20',
  Normal:   'text-slate-400 bg-slate-500/10 border-slate-500/20',
  LOW:      'text-slate-400 bg-slate-500/10 border-slate-500/20',
};

function PriorityChip({ label }: { label: string }) {
  const cls = PRIORITY_COLORS[label] ?? 'text-[var(--text-muted)] bg-[var(--bg-elevated)] border-[var(--border)]';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold border ${cls}`}>
      {label}
    </span>
  );
}

export function EvaluationView() {
  const [data, setData] = useState<EvalData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'correct' | 'wrong'>('all');

  const runEval = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchEvaluation();
      if (result.error) { setError(result.error); return; }
      setData(result as EvalData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const filtered = data?.results.filter((r) => {
    if (filter === 'correct') return r.is_correct;
    if (filter === 'wrong') return !r.is_correct;
    return true;
  }) ?? [];

  const accuracyColor =
    !data ? 'text-[var(--text-muted)]'
    : data.accuracy >= 80 ? 'text-emerald-500'
    : data.accuracy >= 60 ? 'text-amber-500'
    : 'text-red-500';

  return (
    <div className="flex-1 h-full overflow-y-auto bg-[var(--bg-base)] p-6 custom-scrollbar" id="evaluation-view">
      {/* Header */}
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
              Model Evaluation
            </h1>
            <p className="text-xs text-[var(--text-muted)] mt-0.5 font-medium">
              Runs the triage classifier against the golden dataset and reports accuracy.
            </p>
          </div>
          <button
            onClick={runEval}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 disabled:opacity-50 text-[var(--bg-surface)] font-bold text-sm rounded-lg cursor-pointer transition-all active:scale-95 shadow"
            id="btn-run-eval"
          >
            {loading ? (
              <span className="w-4 h-4 rounded-full border-2 border-[var(--bg-surface)] border-t-transparent animate-spin" />
            ) : (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
            {loading ? 'Evaluating…' : 'Run Evaluation'}
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-xs font-semibold text-red-500">
            {error}
          </div>
        )}

        {!data && !loading && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-2xl bg-[var(--bg-elevated)] border border-[var(--border)] flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <p className="text-sm font-semibold text-[var(--text-primary)]">No results yet</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">Click Run Evaluation to benchmark the triage classifier.</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="w-10 h-10 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin mb-4" />
            <p className="text-xs text-[var(--text-muted)] font-medium">Running classifier against golden dataset…</p>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Metrics cards */}
            <div className="grid grid-cols-3 gap-4 mb-6">
              {/* Accuracy */}
              <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl p-4 text-center">
                <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-bold mb-1">Accuracy</p>
                <p className={`text-3xl font-black tabular-nums ${accuracyColor}`}>
                  {data.accuracy}%
                </p>
                <div className="mt-2 h-1.5 rounded-full bg-[var(--bg-elevated)] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      data.accuracy >= 80 ? 'bg-emerald-500' : data.accuracy >= 60 ? 'bg-amber-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${data.accuracy}%` }}
                  />
                </div>
              </div>

              {/* Correct */}
              <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl p-4 text-center">
                <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-bold mb-1">Correct</p>
                <p className="text-3xl font-black text-emerald-500 tabular-nums">{data.correct_predictions}</p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1 font-medium">out of {data.total_samples} samples</p>
              </div>

              {/* Wrong */}
              <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl p-4 text-center">
                <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-bold mb-1">Incorrect</p>
                <p className="text-3xl font-black text-red-500 tabular-nums">
                  {data.total_samples - data.correct_predictions}
                </p>
                <p className="text-[10px] text-[var(--text-muted)] mt-1 font-medium">misclassified</p>
              </div>
            </div>

            {/* Filter tabs */}
            <div className="flex items-center gap-2 mb-4">
              {(['all', 'correct', 'wrong'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    filter === f
                      ? 'bg-[var(--accent-primary)] text-[var(--bg-surface)]'
                      : 'bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }`}
                >
                  {f === 'all' ? `All (${data.total_samples})` : f === 'correct' ? `Correct (${data.correct_predictions})` : `Wrong (${data.total_samples - data.correct_predictions})`}
                </button>
              ))}
            </div>

            {/* Results table */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl overflow-hidden">
              <div className="grid grid-cols-[1fr_120px_120px_40px] gap-0 text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-widest border-b border-[var(--border)] px-4 py-2.5 bg-[var(--bg-elevated)]">
                <span>Subject</span>
                <span>Expected</span>
                <span>Predicted</span>
                <span className="text-center">✓</span>
              </div>

              {filtered.length === 0 && (
                <div className="py-8 text-center text-xs text-[var(--text-muted)] font-medium">
                  No results match this filter.
                </div>
              )}

              {filtered.map((r, i) => (
                <div
                  key={i}
                  className={`grid grid-cols-[1fr_120px_120px_40px] gap-0 items-center px-4 py-2.5 border-b border-[var(--border-subtle)] last:border-b-0 ${
                    r.is_correct ? '' : 'bg-red-500/5'
                  }`}
                >
                  <span className="text-xs text-[var(--text-primary)] font-medium truncate pr-4"
                    title={r.subject}>
                    {r.subject}
                  </span>
                  <PriorityChip label={r.expected} />
                  <PriorityChip label={r.predicted} />
                  <div className="flex justify-center">
                    {r.is_correct ? (
                      <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
