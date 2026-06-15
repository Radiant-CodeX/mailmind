'use client';

import React, { useMemo, useState } from 'react';
import { previewPII, PIIPreviewResult, PIIEntitySpan } from '../../lib/api';

// A deliberately PII-rich sample so judges see every category light up at once.
const SAMPLE_EMAIL = `Hi Priya Sharma,

Following up on our call — please wire the refund to account 50100234567890
(IFSC HDFC0001234). My PAN is ABCDE1234F and Aadhaar 4521 8896 1234 for the
KYC form.

You can reach me on +91 98765 43210 or at rohan.mehta@gmail.com. The signed
contract is at 221B Baker Street, Mumbai.

Card on file: 4111 1111 1111 1111. Internal API key: sk-abcdef1234567890abcdef.

Thanks,
Rohan Mehta`;

// Tailwind classes per PII category (highlight chip + label colour).
const CATEGORY_STYLE: Record<string, { mark: string; chip: string; label: string }> = {
  PERSON_NAME: { mark: 'bg-violet-500/25 text-violet-200', chip: 'bg-violet-500/15 text-violet-300 border-violet-400/30', label: 'Name' },
  EMAIL: { mark: 'bg-sky-500/25 text-sky-200', chip: 'bg-sky-500/15 text-sky-300 border-sky-400/30', label: 'Email' },
  PHONE: { mark: 'bg-emerald-500/25 text-emerald-200', chip: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/30', label: 'Phone' },
  ADDRESS: { mark: 'bg-amber-500/25 text-amber-200', chip: 'bg-amber-500/15 text-amber-300 border-amber-400/30', label: 'Address' },
  FINANCIAL_ID: { mark: 'bg-rose-500/25 text-rose-200', chip: 'bg-rose-500/15 text-rose-300 border-rose-400/30', label: 'Financial ID' },
  GOVERNMENT_ID: { mark: 'bg-orange-500/25 text-orange-200', chip: 'bg-orange-500/15 text-orange-300 border-orange-400/30', label: 'Government ID' },
  HEALTH_INFO: { mark: 'bg-pink-500/25 text-pink-200', chip: 'bg-pink-500/15 text-pink-300 border-pink-400/30', label: 'Health' },
  SECRET: { mark: 'bg-red-500/30 text-red-200', chip: 'bg-red-500/15 text-red-300 border-red-400/30', label: 'Secret' },
  PERSONAL_OBJECT_ID: { mark: 'bg-cyan-500/25 text-cyan-200', chip: 'bg-cyan-500/15 text-cyan-300 border-cyan-400/30', label: 'Device ID' },
};

function styleFor(type: string) {
  return CATEGORY_STYLE[type] || { mark: 'bg-base-300 text-base-content', chip: 'bg-base-200 text-base-content/70 border-base-300', label: type };
}

/** Render the original text with detected PII spans highlighted. */
function HighlightedOriginal({ text, entities }: { text: string; entities: PIIEntitySpan[] }) {
  const segments = useMemo(() => {
    const sorted = [...entities].sort((a, b) => a.start - b.start);
    const out: React.ReactNode[] = [];
    let cursor = 0;
    sorted.forEach((e, i) => {
      if (e.start < cursor) return; // skip overlaps defensively
      if (e.start > cursor) out.push(<span key={`t${i}`}>{text.slice(cursor, e.start)}</span>);
      const s = styleFor(e.type);
      out.push(
        <mark key={`m${i}`} className={`rounded px-0.5 ${s.mark}`} title={s.label}>
          {text.slice(e.start, e.end)}
        </mark>,
      );
      cursor = e.end;
    });
    if (cursor < text.length) out.push(<span key="tail">{text.slice(cursor)}</span>);
    return out;
  }, [text, entities]);

  return <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-base-content/80">{segments}</pre>;
}

/** Render masked text with the placeholder tokens visually emphasised. */
function MaskedOutput({ masked }: { masked: string }) {
  const parts = masked.split(/(\[[A-Z_]+_\d+\])/g);
  return (
    <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-base-content/80">
      {parts.map((p, i) =>
        /^\[[A-Z_]+_\d+\]$/.test(p) ? (
          <span key={i} className="rounded bg-emerald-500/20 px-1 font-bold text-emerald-300">{p}</span>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </pre>
  );
}

export function PrivacyView() {
  const [text, setText] = useState(SAMPLE_EMAIL);
  const [result, setResult] = useState<PIIPreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runMask = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await previewPII(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run masking');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 h-full overflow-y-auto bg-base-300 p-6 custom-scrollbar" id="privacy-view">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <div className="mb-6">
          <h1 className="flex items-center gap-2 text-lg font-bold tracking-tight text-base-content">
            <svg className="h-5 w-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Privacy &amp; PII Masking
          </h1>
          <p className="mt-0.5 text-xs font-medium text-base-content/60">
            Reversible PII scrubbing runs on every email <em>before</em> any LLM call. This is the exact
            text the model receives — raw personal data never leaves our backend.
          </p>
        </div>

        {/* Input */}
        <div className="rounded-xl border border-base-300 bg-base-100 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-widest text-base-content/50">Email content</span>
            <button
              onClick={() => { setText(SAMPLE_EMAIL); setResult(null); }}
              className="text-[11px] font-bold text-base-content/50 hover:text-base-content"
            >
              Reset sample
            </button>
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="w-full resize-y rounded-lg border border-base-300 bg-base-200 p-3 font-mono text-xs leading-relaxed text-base-content focus:border-primary focus:outline-none"
          />
          <button
            onClick={runMask}
            disabled={loading || !text.trim()}
            className="mt-3 flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-base-100 transition-all hover:bg-primary/90 active:scale-95 disabled:opacity-50"
          >
            {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-base-100/40 border-t-base-100" /> : '🔒 Mask PII'}
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs font-semibold text-red-500">{error}</div>
        )}

        {result && (
          <div className="mt-5 space-y-5 animate-fade-in">
            {/* Summary bar */}
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-bold text-emerald-400">
                {result.total} item{result.total === 1 ? '' : 's'} masked
              </span>
              <span className="rounded-lg border border-base-300 bg-base-100 px-3 py-1.5 text-xs font-bold text-base-content/70">
                Engine: {result.engine === 'presidio' ? 'Presidio + spaCy NER' : 'Regex fallback'}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(result.counts).map(([type, n]) => {
                  const s = styleFor(type);
                  return (
                    <span key={type} className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${s.chip}`}>
                      {s.label} ×{n}
                    </span>
                  );
                })}
              </div>
            </div>

            {/* Before / After */}
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-base-300 bg-base-100 p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-rose-500" />
                  <span className="text-xs font-bold uppercase tracking-widest text-base-content/50">Original (highlighted)</span>
                </div>
                <HighlightedOriginal text={text} entities={result.entities} />
              </div>
              <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/[0.04] p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span className="text-xs font-bold uppercase tracking-widest text-emerald-400/70">Sent to the LLM (masked)</span>
                </div>
                <MaskedOutput masked={result.masked} />
              </div>
            </div>

            <p className="text-center text-[11px] text-base-content/40">
              Masking is <span className="font-semibold text-base-content/60">reversible</span> — tokens like{' '}
              <code className="rounded bg-base-200 px-1">[PERSON_1]</code> are restored to the real values
              only <em>after</em> the model responds, so drafts read naturally while the LLM never sees raw PII.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
