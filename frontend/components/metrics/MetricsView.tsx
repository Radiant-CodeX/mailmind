'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fetchLiveMetrics, LiveMetrics } from '../../lib/api';

const STAGE_LABELS: Record<string, string> = {
  ingest: 'Ingest',
  triage: 'Triage',
  commitments: 'Commitments',
  calendar: 'Calendar',
  rag: 'RAG',
  draft: 'Draft',
};

const REFRESH_MS = 4000;

function clsForRate(rate: number, goodBelow: number, warnBelow: number): string {
  if (rate < goodBelow) return 'text-emerald-500';
  if (rate < warnBelow) return 'text-amber-500';
  return 'text-red-500';
}

/** Circular gauge for a 0-100 percentage. */
function Gauge({ value, label, color }: { value: number; label: string; color: string }) {
  const r = 42;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-28 h-28">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={r} fill="none" strokeWidth="8" className="stroke-base-300" />
          <circle
            cx="50"
            cy="50"
            r={r}
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            stroke={color}
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.7s cubic-bezier(0.16,1,0.3,1)' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-black tabular-nums text-base-content">{value.toFixed(1)}</span>
          <span className="text-[10px] text-base-content/50 font-bold">%</span>
        </div>
      </div>
      <span className="mt-2 text-[11px] font-bold uppercase tracking-widest text-base-content/60">{label}</span>
    </div>
  );
}

export function MetricsView() {
  const [data, setData] = useState<LiveMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const m = await fetchLiveMetrics();
      setData(m);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load metrics');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (live) {
      timer.current = setInterval(load, REFRESH_MS);
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [live, load]);

  const maxStageP95 = data
    ? Math.max(
        1,
        ...Object.values(data.latency.per_stage).map((s) => s.p95),
      )
    : 1;

  return (
    <div className="flex-1 h-full overflow-y-auto bg-base-300 p-6 custom-scrollbar" id="metrics-view">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold text-base-content tracking-tight flex items-center gap-2">
              Live Metrics
              {live && <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />}
            </h1>
            <p className="text-xs text-base-content/60 mt-0.5 font-medium">
              Real-time production telemetry · cache, latency, LLM reliability, pipeline speedup
            </p>
          </div>
          <div className="flex items-center gap-2">
            {lastUpdated && (
              <span className="text-[10px] text-base-content/40 font-mono">
                updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={() => setLive((v) => !v)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                live ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30' : 'bg-base-200 text-base-content/60 border border-base-300'
              }`}
            >
              {live ? '● Live' : '○ Paused'}
            </button>
            <button
              onClick={load}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-primary text-base-100 hover:bg-primary/90 transition-all active:scale-95 cursor-pointer"
            >
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-xs font-semibold text-red-500">
            {error} — is the backend running?
          </div>
        )}

        {!data && !error && (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin mb-4" />
            <p className="text-xs text-base-content/60 font-medium">Connecting to telemetry…</p>
          </div>
        )}

        {data && (
          <div className="space-y-5">
            {/* ── Speedup hero card ── */}
            <div className="relative bg-gradient-to-br from-primary/10 via-base-100 to-base-100 border border-primary/20 rounded-2xl p-6 overflow-hidden">
              <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-[10px] uppercase tracking-widest font-bold text-primary mb-1">
                    Parallel Pipeline Speedup
                  </p>
                  <h2 className="text-base font-bold text-base-content">
                    Concurrent enrichment vs. running stages one-by-one
                  </h2>
                </div>
                <span className={`text-[10px] font-bold px-2 py-1 rounded-full border ${
                  data.speedup.measured
                    ? 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20'
                    : 'text-amber-500 bg-amber-500/10 border-amber-500/20'
                }`}>
                  {data.speedup.measured ? `MEASURED · ${data.speedup.runs} runs` : 'REFERENCE'}
                </span>
              </div>

              {/* Comparison bars */}
              <div className="space-y-3">
                {/* Sequential */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-base-content/70">Sequential</span>
                    <span className="font-mono font-bold text-base-content/70 tabular-nums">{data.speedup.sequential_s}s</span>
                  </div>
                  <div className="h-7 rounded-lg bg-base-200 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-slate-400 to-slate-500 rounded-lg flex items-center justify-end pr-2" style={{ width: '100%' }}>
                      <span className="text-[10px] font-bold text-white/90">{data.speedup.sequential_ms}ms</span>
                    </div>
                  </div>
                </div>
                {/* Parallel */}
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-primary">Parallel (MailMind)</span>
                    <span className="font-mono font-bold text-primary tabular-nums">{data.speedup.parallel_s}s</span>
                  </div>
                  <div className="h-7 rounded-lg bg-base-200 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-lg flex items-center justify-end pr-2"
                      style={{
                        width: `${Math.max(8, (data.speedup.parallel_ms / data.speedup.sequential_ms) * 100)}%`,
                        transition: 'width 0.7s cubic-bezier(0.16,1,0.3,1)',
                      }}
                    >
                      <span className="text-[10px] font-bold text-white/90">{data.speedup.parallel_ms}ms</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-6 mt-5 pt-4 border-t border-base-300">
                <div>
                  <span className="text-3xl font-black text-primary tabular-nums">{data.speedup.speedup_x}×</span>
                  <span className="text-[10px] text-base-content/50 font-bold ml-1">FASTER</span>
                </div>
                <div>
                  <span className="text-3xl font-black text-emerald-500 tabular-nums">{data.speedup.time_saved_pct}%</span>
                  <span className="text-[10px] text-base-content/50 font-bold ml-1">TIME SAVED</span>
                </div>
              </div>
            </div>

            {/* ── Gauges row ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-base-100 border border-base-300 rounded-xl p-4 flex justify-center">
                <Gauge value={data.cache.hit_rate} label="Cache Hit Rate" color="#10b981" />
              </div>
              <div className="bg-base-100 border border-base-300 rounded-xl p-4 flex justify-center">
                <Gauge
                  value={data.llm.error_rate}
                  label="LLM Error Rate"
                  color={data.llm.error_rate < 1 ? '#10b981' : data.llm.error_rate < 5 ? '#f59e0b' : '#ef4444'}
                />
              </div>
              {/* p50 / p95 stat cards */}
              <div className="bg-base-100 border border-base-300 rounded-xl p-4 flex flex-col items-center justify-center">
                <span className="text-[11px] font-bold uppercase tracking-widest text-base-content/60 mb-1">Overall p50</span>
                <span className="text-3xl font-black text-base-content tabular-nums">{data.latency.overall.p50}</span>
                <span className="text-[10px] text-base-content/40 font-bold">ms</span>
              </div>
              <div className="bg-base-100 border border-base-300 rounded-xl p-4 flex flex-col items-center justify-center">
                <span className="text-[11px] font-bold uppercase tracking-widest text-base-content/60 mb-1">Overall p95</span>
                <span className="text-3xl font-black text-base-content tabular-nums">{data.latency.overall.p95}</span>
                <span className="text-[10px] text-base-content/40 font-bold">ms</span>
              </div>
            </div>

            {/* ── Latency per stage ── */}
            <div className="bg-base-100 border border-base-300 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-base-content">Latency by Pipeline Stage</h3>
                <div className="flex items-center gap-4 text-[10px] font-bold">
                  <span className="flex items-center gap-1.5 text-base-content/60">
                    <span className="w-3 h-2 rounded-sm bg-indigo-500" /> p50
                  </span>
                  <span className="flex items-center gap-1.5 text-base-content/60">
                    <span className="w-3 h-2 rounded-sm bg-violet-400/50" /> p95
                  </span>
                </div>
              </div>
              <div className="space-y-3">
                {Object.entries(data.latency.per_stage).map(([stage, s]) => (
                  <div key={stage}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-semibold text-base-content/80">
                        {STAGE_LABELS[stage] ?? stage}
                        <span className="text-base-content/40 font-normal ml-2">({s.count} samples)</span>
                      </span>
                      <span className="font-mono text-base-content/60 tabular-nums">
                        p50 {s.p50}ms · p95 {s.p95}ms
                      </span>
                    </div>
                    <div className="relative h-2.5 rounded-full bg-base-200 overflow-hidden">
                      {/* p95 (back) */}
                      <div
                        className="absolute inset-y-0 left-0 bg-violet-400/40 rounded-full"
                        style={{ width: `${(s.p95 / maxStageP95) * 100}%`, transition: 'width 0.6s ease' }}
                      />
                      {/* p50 (front) */}
                      <div
                        className="absolute inset-y-0 left-0 bg-indigo-500 rounded-full"
                        style={{ width: `${(s.p50 / maxStageP95) * 100}%`, transition: 'width 0.6s ease' }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Cache breakdown + footer stats ── */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="bg-base-100 border border-base-300 rounded-xl p-5">
                <h3 className="text-sm font-bold text-base-content mb-3">Cache Breakdown</h3>
                <div className="space-y-2">
                  {Object.entries(data.cache.per_cache).map(([name, c]) => {
                    const total = c.hits + c.misses;
                    const rate = total ? (c.hits / total) * 100 : 0;
                    return (
                      <div key={name} className="flex items-center gap-3">
                        <span className="text-xs font-semibold text-base-content/70 capitalize w-24 shrink-0">{name}</span>
                        <div className="flex-1 h-2 rounded-full bg-base-200 overflow-hidden">
                          <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${rate}%`, transition: 'width 0.6s ease' }} />
                        </div>
                        <span className="text-[10px] font-mono text-base-content/50 tabular-nums w-28 text-right shrink-0">
                          {c.hits}h / {c.misses}m · {c.entries}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 pt-3 border-t border-base-300 flex justify-between text-xs">
                  <span className="text-base-content/60 font-semibold">Total lookups</span>
                  <span className="font-mono font-bold text-base-content tabular-nums">{data.cache.total_lookups}</span>
                </div>
              </div>

              <div className="bg-base-100 border border-base-300 rounded-xl p-5">
                <h3 className="text-sm font-bold text-base-content mb-3">System</h3>
                <div className="space-y-2.5 text-xs">
                  <Row label="LLM calls (ok / total)" value={`${data.llm.ok} / ${data.llm.total}`} />
                  <Row label="LLM error rate" value={`${data.llm.error_rate}%`} valueClass={clsForRate(data.llm.error_rate, 1, 5)} />
                  <Row label="Queue depth" value={String(data.queue_depth)} />
                  <Row label="Triage SLA target" value={`${data.sla_targets_seconds.triage}s`} />
                  <Row label="Enrichment SLA target" value={`${data.sla_targets_seconds.enrichment}s`} />
                  <Row label="Uptime" value={formatUptime(data.uptime_seconds)} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-base-content/60 font-semibold">{label}</span>
      <span className={`font-mono font-bold tabular-nums ${valueClass ?? 'text-base-content'}`}>{value}</span>
    </div>
  );
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}
