'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BASE, apiFetch } from '@/lib/api';

interface IndexStats {
  indexedEmails: number;
  storageLabel: string;
  lastIndexed: string;
  dbStatus: 'healthy' | 'error' | 'loading';
}

interface ToneStats {
  status: 'built' | 'unbuilt' | 'loading';
  formality: number | null;
  sampleSize: number;
  lastBuilt: string;
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      className={`w-3.5 h-3.5 ${spinning ? 'animate-spin' : ''}`}
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M14 8A6 6 0 1 1 8 2" strokeLinecap="round" />
      <path d="M8 1l2 2-2 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MiniSpinner() {
  return (
    <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
  );
}

function StatusPill({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="text-[9px] font-bold text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">
      HEALTHY
    </span>
  ) : (
    <span className="text-[9px] font-bold text-red-500 bg-red-500/10 px-1.5 py-0.5 rounded">
      UNAVAILABLE
    </span>
  );
}

function formalityLabel(score: number): string {
  if (score >= 0.75) return 'Very formal';
  if (score >= 0.6) return 'Formal';
  if (score >= 0.45) return 'Balanced';
  if (score >= 0.3) return 'Casual';
  return 'Very casual';
}

function formalityColor(score: number): string {
  if (score >= 0.6) return 'text-blue-500';
  if (score >= 0.45) return 'text-[var(--accent-primary)]';
  return 'text-amber-500';
}

export function RAGSettingsView() {
  const [similarityThreshold, setSimilarityThreshold] = useState(0.78);
  const [maxIndexSize, setMaxIndexSize] = useState(1000);
  const [syncing, setSyncing] = useState(false);
  const [statsLoading, setStatsLoading] = useState(true);
  const [indexStats, setIndexStats] = useState<IndexStats>({
    indexedEmails: 0,
    storageLabel: '—',
    lastIndexed: '—',
    dbStatus: 'loading',
  });
  const [toneStats, setToneStats] = useState<ToneStats>({
    status: 'loading',
    formality: null,
    sampleSize: 0,
    lastBuilt: '—',
  });
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const thresholdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const maxSizeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    const [ragRes, toneRes] = await Promise.allSettled([
      apiFetch(`${BASE}/api/rag/stats`),
      apiFetch(`${BASE}/api/tone-dna/profile`),
    ]);

    if (ragRes.status === 'fulfilled' && ragRes.value.ok) {
      const d = await ragRes.value.json();
      setSimilarityThreshold(d.similarity_threshold ?? 0.78);
      setMaxIndexSize(d.max_index_size ?? 1000);
      setIndexStats({
        indexedEmails: d.indexed_emails ?? 0,
        storageLabel: d.storage_label ?? '—',
        lastIndexed: d.last_indexed ? new Date(d.last_indexed).toLocaleString() : 'Never',
        dbStatus: 'healthy',
      });
    } else {
      setIndexStats((p) => ({ ...p, dbStatus: 'error' }));
    }

    if (toneRes.status === 'fulfilled' && toneRes.value.ok) {
      const p = await toneRes.value.json();
      setToneStats({
        status: 'built',
        formality: p.features?.formality_score ?? null,
        sampleSize: p.sample_size ?? 0,
        lastBuilt: p.generated_at ? new Date(p.generated_at).toLocaleString() : '—',
      });
    } else {
      setToneStats({ status: 'unbuilt', formality: null, sampleSize: 0, lastBuilt: '—' });
    }

    setStatsLoading(false);
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const pushSettings = (patch: Record<string, unknown>) => {
    apiFetch(`${BASE}/api/rag/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).catch((e) => console.error('[RAG settings]', e));
  };

  const updateSimilarityThreshold = (val: number) => {
    setSimilarityThreshold(val);
    if (thresholdTimer.current) clearTimeout(thresholdTimer.current);
    thresholdTimer.current = setTimeout(() => pushSettings({ similarity_threshold: val }), 500);
  };

  const updateMaxIndexSize = (val: number) => {
    setMaxIndexSize(val);
    if (maxSizeTimer.current) clearTimeout(maxSizeTimer.current);
    maxSizeTimer.current = setTimeout(() => pushSettings({ max_index_size: val }), 500);
  };

  const handleSync = async () => {
    setSyncing(true);
    setSuccessMsg(null);
    setErrorMsg(null);
    try {
      const res = await apiFetch(`${BASE}/api/tone-dna/build`, { method: 'POST' });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      await loadStats();
      setSuccessMsg(
        `Synced ${data.sample_size ?? 0} emails — Tone DNA profile and RAG index are up to date.`
      );
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Sync failed. Try again.');
    } finally {
      setSyncing(false);
    }
  };

  const busy = syncing || statsLoading;

  return (
    <div
      className="flex-1 bg-[var(--bg-base)] flex flex-col h-full overflow-hidden text-left p-6"
      id="rag-settings-view"
    >
      {/* ── Page header ────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <h2 className="text-xl font-bold text-[var(--text-primary)]">AI Knowledge Base</h2>
          <p className="text-xs text-[var(--text-muted)] mt-1 max-w-md">
            MailMind analyses your last 30 days of sent mail to build a writing-style profile and a
            vector index. Both are used when generating draft replies.
          </p>
        </div>

        {/* Primary fetch button */}
        <button
          onClick={handleSync}
          disabled={busy}
          className="shrink-0 flex items-center gap-2 px-4 py-2.5 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] rounded-lg text-xs font-bold transition-all disabled:opacity-50 cursor-pointer shadow-sm"
        >
          {syncing ? <><MiniSpinner /> Syncing…</> : <><RefreshIcon spinning={false} /> Sync Knowledge Base</>}
        </button>
      </div>

      {/* ── Feedback banner ─────────────────────────────────────────── */}
      {(successMsg || errorMsg) && (
        <div
          className={`mb-4 p-3 rounded-lg border text-[11px] font-medium leading-normal ${
            successMsg
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400'
              : 'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400'
          }`}
        >
          {successMsg || errorMsg}
        </div>
      )}

      {/* ── Main grid ───────────────────────────────────────────────── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden min-h-0">

        {/* ── Left: Retrieval settings ─────────────────────────────── */}
        <div className="lg:col-span-2 bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg flex flex-col overflow-hidden shadow-sm">
          <div className="p-4 border-b border-[var(--border-subtle)]">
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Retrieval Settings</h3>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
              Changes apply immediately — no restart needed.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">

            {/* Threshold slider */}
            <div className="space-y-3">
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="text-xs font-semibold text-[var(--text-primary)]">Match Threshold</span>
                  <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                    Minimum cosine similarity required for a past email to be surfaced as a precedent.
                  </p>
                </div>
                <span className="font-mono text-base font-bold text-[var(--accent-primary)] ml-4 shrink-0">
                  {similarityThreshold.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="0.50"
                max="0.95"
                step="0.01"
                value={similarityThreshold}
                onChange={(e) => updateSimilarityThreshold(parseFloat(e.target.value))}
                className="w-full h-1.5 rounded-lg appearance-none cursor-pointer accent-[var(--accent-primary)] focus:outline-none"
              />
              <div className="flex justify-between text-[10px] text-[var(--text-muted)]">
                <span>← Broader matches (0.50)</span>
                <span>Exact matches only (0.95) →</span>
              </div>
            </div>

            {/* Max docs */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-[var(--text-primary)] block">
                Max Indexed Documents
              </label>
              <p className="text-[10px] text-[var(--text-muted)]">
                The vector index keeps at most this many emails. Older entries are evicted when the
                limit is reached.
              </p>
              <input
                type="number"
                min={100}
                max={5000}
                step={100}
                value={maxIndexSize}
                onChange={(e) => updateMaxIndexSize(parseInt(e.target.value) || 0)}
                className="w-36 p-2 rounded bg-[var(--bg-elevated)] border border-[var(--border)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] font-mono font-medium"
              />
            </div>

            {/* PII masking demo */}
            <div className="p-4 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
              <div>
                <h4 className="text-xs font-bold text-[var(--text-primary)]">PII Masking</h4>
                <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                  Emails are scrubbed before they enter the vector store — no raw contact data is ever persisted.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block mb-1">Original text</span>
                  <div className="p-2.5 rounded bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--text-primary)]/80 text-[11px] leading-relaxed font-mono">
                    Contact john@acme.com or call +1-555-0199.
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block mb-1">Stored in vector DB</span>
                  <div className="p-2.5 rounded bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--accent-success)] text-[11px] font-mono leading-relaxed">
                    Contact [EMAIL] or call [PHONE].
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>

        {/* ── Right: Status panel ──────────────────────────────────── */}
        <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg flex flex-col overflow-hidden shadow-sm">
          <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
            <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">
              Status
            </h3>
            <button
              onClick={loadStats}
              disabled={busy}
              title="Refresh stats"
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-40 transition-colors cursor-pointer"
            >
              <RefreshIcon spinning={statsLoading && !syncing} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">

            {syncing ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <span className="inline-block w-7 h-7 border-2 border-[var(--border)] border-t-[var(--accent-primary)] rounded-full animate-spin" />
                <p className="text-[11px] text-[var(--text-muted)] text-center leading-relaxed">
                  Fetching sent mail<br />and rebuilding knowledge base…
                </p>
              </div>
            ) : statsLoading ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <span className="inline-block w-7 h-7 border-2 border-[var(--border)] border-t-[var(--accent-primary)] rounded-full animate-spin" />
                <p className="text-[11px] text-[var(--text-muted)]">Loading…</p>
              </div>
            ) : (
              <>
                {/* Tone DNA card */}
                <div className="rounded-lg border border-[var(--border-subtle)] overflow-hidden">
                  <div className="px-3 py-2 bg-[var(--bg-elevated)] flex items-center justify-between">
                    <span className="text-[10px] font-bold text-[var(--text-primary)] uppercase tracking-wider">
                      Tone DNA
                    </span>
                    {toneStats.status === 'built' ? (
                      <span className="text-[9px] font-bold text-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                        BUILT
                      </span>
                    ) : (
                      <span className="text-[9px] font-bold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
                        NOT BUILT
                      </span>
                    )}
                  </div>

                  {toneStats.status === 'built' && toneStats.formality !== null ? (
                    <div className="p-3 space-y-2.5">
                      <div className="flex justify-between text-xs">
                        <span className="text-[var(--text-muted)]">Writing style</span>
                        <span className={`font-semibold ${formalityColor(toneStats.formality)}`}>
                          {formalityLabel(toneStats.formality)}
                          <span className="text-[var(--text-muted)] font-normal ml-1">
                            ({toneStats.formality.toFixed(2)})
                          </span>
                        </span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-[var(--text-muted)]">Emails analysed</span>
                        <span className="font-mono font-semibold text-[var(--text-primary)]">
                          {toneStats.sampleSize}
                        </span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-[var(--text-muted)]">Last built</span>
                        <span className="font-mono text-[10px] text-[var(--text-primary)]">
                          {toneStats.lastBuilt}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="p-3 text-[11px] text-[var(--text-muted)] leading-relaxed">
                      No profile yet. Click{' '}
                      <span className="font-semibold text-[var(--text-primary)]">
                        Sync Knowledge Base
                      </span>{' '}
                      to build one.
                    </p>
                  )}
                </div>

                {/* RAG index card */}
                <div className="rounded-lg border border-[var(--border-subtle)] overflow-hidden">
                  <div className="px-3 py-2 bg-[var(--bg-elevated)] flex items-center justify-between">
                    <span className="text-[10px] font-bold text-[var(--text-primary)] uppercase tracking-wider">
                      RAG Index
                    </span>
                    <StatusPill ok={indexStats.dbStatus === 'healthy'} />
                  </div>
                  <div className="p-3 space-y-2.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--text-muted)]">Indexed emails</span>
                      <span className="font-mono font-semibold text-[var(--text-primary)]">
                        {indexStats.indexedEmails}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--text-muted)]">Storage</span>
                      <span className="font-mono font-semibold text-[var(--text-primary)]">
                        {indexStats.storageLabel}
                      </span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-[var(--text-muted)]">Last synced</span>
                      <span className="font-mono text-[10px] text-[var(--text-primary)]">
                        {indexStats.lastIndexed}
                      </span>
                    </div>
                  </div>
                </div>

                {/* How it works blurb */}
                <div className="p-3 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-1">
                  <p className="text-[10px] font-semibold text-[var(--text-primary)]">How sync works</p>
                  <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
                    Fetches 30 days of sent mail once. The same emails feed both the Tone DNA stylometric
                    profile and the RAG vector index — no duplicate network calls.
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Secondary sync button */}
          <div className="p-4 border-t border-[var(--border-subtle)]">
            <button
              onClick={handleSync}
              disabled={busy}
              className="w-full py-2.5 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] rounded-lg text-xs font-bold transition-all disabled:opacity-50 cursor-pointer shadow-sm flex items-center justify-center gap-2"
            >
              {syncing ? <><MiniSpinner /> Syncing…</> : 'Sync Knowledge Base'}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
