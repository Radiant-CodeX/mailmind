'use client';

import React, { useState, useEffect } from 'react';
import { LoadingSpinner } from '../shared/LoadingSpinner';

export function RAGSettingsView() {
  const [similarityThreshold, setSimilarityThreshold] = useState(0.78);
  const [maxIndexSize, setMaxIndexSize] = useState(1000);
  const [useChroma, setUseChroma] = useState(true);
  const [indexing, setIndexing] = useState(false);
  const [indexStats, setIndexStats] = useState({
    indexedEmails: 54,
    lastIndexed: new Date(Date.now() - 4 * 3600000).toLocaleString(),
    storageUsed: '14.2 MB',
  });
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Load settings from localStorage on mount to prevent reset when tab is switched
  useEffect(() => {
    const savedThreshold = localStorage.getItem('rag_similarity_threshold');
    if (savedThreshold !== null) {
      setSimilarityThreshold(parseFloat(savedThreshold));
    }

    const savedMaxIndexSize = localStorage.getItem('rag_max_index_size');
    if (savedMaxIndexSize !== null) {
      setMaxIndexSize(parseInt(savedMaxIndexSize));
    }

    const savedUseChroma = localStorage.getItem('rag_use_chroma');
    if (savedUseChroma !== null) {
      setUseChroma(savedUseChroma === 'true');
    }
  }, []);

  const updateSimilarityThreshold = (val: number) => {
    setSimilarityThreshold(val);
    localStorage.setItem('rag_similarity_threshold', val.toString());
  };

  const updateMaxIndexSize = (val: number) => {
    setMaxIndexSize(val);
    localStorage.setItem('rag_max_index_size', val.toString());
  };

  const updateUseChroma = (val: boolean) => {
    setUseChroma(val);
    localStorage.setItem('rag_use_chroma', val.toString());
  };

  const handleReindex = async () => {
    setIndexing(true);
    setSuccessMsg(null);
    try {
      // Simulate indexing latency
      await new Promise((resolve) => setTimeout(resolve, 2000));
      setIndexStats({
        indexedEmails: 54 + Math.floor(Math.random() * 5) + 1,
        lastIndexed: new Date().toLocaleString(),
        storageUsed: '14.8 MB',
      });
      setSuccessMsg('RAG knowledge base successfully re-indexed and synchronized with MS Graph!');
    } catch (e) {
      console.error(e);
    } finally {
      setIndexing(false);
    }
  };

  return (
    <div className="flex-1 bg-[var(--bg-base)] flex flex-col h-full overflow-hidden text-left p-6" id="rag-settings-view">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-[var(--text-primary)]">RAG Knowledge Base Settings</h2>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Configure retrieval parameters, mask personally identifiable data, and index historical client correspondence.
        </p>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        {/* RAG Parameter Settings */}
        <div className="lg:col-span-2 bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg flex flex-col h-full overflow-hidden shadow-sm">
          <div className="p-4 border-b border-[var(--border-subtle)]">
            <h3 className="text-sm font-bold text-[var(--text-primary)]">Retrieval & Embedding Parameters</h3>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
            {/* Threshold Slider */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-[var(--text-primary)]">Similarity Match Threshold</span>
                <span className="font-mono font-bold text-[var(--accent-primary)]">{similarityThreshold}</span>
              </div>
              <input
                type="range"
                min="0.50"
                max="0.95"
                step="0.01"
                value={similarityThreshold}
                onChange={(e) => updateSimilarityThreshold(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-red-500 rounded-lg appearance-none cursor-pointer accent-[var(--accent-primary)] focus:outline-none"
              />
              <p className="text-[10px] text-[var(--text-muted)]">
                Higher values return only exact matches; lower values return broader, tone-aligned results.
              </p>
            </div>

            {/* Chroma storage config */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs font-semibold text-[var(--text-primary)] block">Vector Indexing Storage</label>
                <select
                  value={useChroma ? 'chroma' : 'azure'}
                  onChange={(e) => updateUseChroma(e.target.value === 'chroma')}
                  className="w-full p-2 rounded bg-[var(--bg-elevated)] border border-[var(--border)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] font-medium"
                >
                  <option value="chroma">ChromaDB Local Fallback (use_chroma=true)</option>
                  <option value="azure">Azure AI Search (Enterprise)</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-[var(--text-primary)] block">Max Documents Cached</label>
                <input
                  type="number"
                  value={maxIndexSize}
                  onChange={(e) => updateMaxIndexSize(parseInt(e.target.value) || 0)}
                  className="w-full p-2 rounded bg-[var(--bg-elevated)] border border-[var(--border)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] font-mono font-medium"
                />
              </div>
            </div>

            {/* PII Masking demonstration */}
            <div className="p-4 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] space-y-3">
              <h4 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider">PII Masking Preview</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block mb-1">Incoming Email Text</span>
                  <div className="p-2.5 rounded bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--text-primary)]/80 text-[11px] leading-relaxed">
                    Contact john@acme.com or call +1-555-0199.
                  </div>
                </div>
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] block mb-1">Masked Reference (Saved in VectorDB)</span>
                  <div className="p-2.5 rounded bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--accent-success)] text-[11px] font-mono leading-relaxed">
                    Contact [EMAIL] or call [PHONE].
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Index Status Panel */}
        <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-lg p-5 flex flex-col justify-between shadow-sm">
          <div className="space-y-6">
            <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider border-b border-[var(--border-subtle)] pb-2">
              Knowledge Status
            </h3>

            {indexing ? (
              <LoadingSpinner message="Scanning folders & masking database indexes..." />
            ) : (
              <div className="space-y-4">
                {successMsg && (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 rounded text-[11px] font-medium leading-normal animate-fade-in">
                    {successMsg}
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4 text-left">
                  <div className="p-3 bg-[var(--bg-elevated)] rounded border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-muted)] block">Indexed Emails</span>
                    <span className="text-lg font-bold text-[var(--text-primary)] font-mono">{indexStats.indexedEmails}</span>
                  </div>
                  <div className="p-3 bg-[var(--bg-elevated)] rounded border border-[var(--border-subtle)]">
                    <span className="text-[10px] text-[var(--text-muted)] block">Storage Size</span>
                    <span className="text-lg font-bold text-[var(--text-primary)] font-mono">{indexStats.storageUsed}</span>
                  </div>
                </div>

                <div className="text-xs space-y-2 pt-2 text-[var(--text-muted)] font-medium">
                  <div className="flex justify-between">
                    <span>Database Status:</span>
                    <span className="text-[var(--accent-success)] font-bold">ACTIVE (HEALTHY)</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Last Synced:</span>
                    <span className="font-mono text-[var(--text-primary)]">{indexStats.lastIndexed}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-[var(--border-subtle)]">
            <button
              onClick={handleReindex}
              disabled={indexing}
              className="w-full py-2.5 bg-[var(--accent-primary)] hover:opacity-90 text-[var(--bg-surface)] rounded text-xs font-bold transition-all disabled:opacity-50 cursor-pointer shadow-sm"
            >
              Re-index Sent Emails
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
