'use client';

import { useState, useEffect } from 'react';
import { Attachment, Email, ClassificationResult, TriageResult, PrecedentItem, CommitmentItem } from '../lib/types';
import { enrichEmail, fetchAttachments, processEmailFull, generateEmailDraft, sendEmailReply } from '../lib/api';
import { userStorage } from '../lib/userStorage';

/**
 * Two-phase email detail loading:
 *
 * Phase 1 — INSTANT (0ms):
 *   The inbox batch already scored every email with /api/agent/triage.
 *   We read email.triage directly from the email object and show it immediately.
 *   No network call needed.
 *
 * Phase 2 — BACKGROUND (~5-8s):
 *   Call /api/agent/enrich which runs commitment + rag IN PARALLEL (not sequential).
 *   This skips the triage node entirely (already done) and halves total latency.
 *   Results (commitments + draft) appear when ready without blocking the UI.
 *
 * Cache: both phases persist to user-scoped localStorage so re-opening an email
 * is always instant — the pipeline never re-runs for already-processed emails.
 */

type EnrichCacheEntry = {
  commitments: CommitmentItem[];
  precedents: PrecedentItem[];
  draft_reply: string | null;
};

const ENRICH_CACHE_KEY = 'enrich_cache';

function readEnrichCache(): Record<string, EnrichCacheEntry> {
  if (typeof window === 'undefined') return {};
  try { return JSON.parse(userStorage.getItem(ENRICH_CACHE_KEY) || '{}'); } catch { return {}; }
}

function writeEnrichCache(emailId: string, entry: EnrichCacheEntry): void {
  if (typeof window === 'undefined') return;
  enrichCache[emailId] = entry;
  try {
    const merged = { ...readEnrichCache(), [emailId]: entry };
    const keys = Object.keys(merged);
    const trimmed = keys.length > 300
      ? Object.fromEntries(keys.slice(keys.length - 300).map((k) => [k, merged[k]]))
      : merged;
    userStorage.setItem(ENRICH_CACHE_KEY, JSON.stringify(trimmed));
  } catch {}
}

const enrichCache: Record<string, EnrichCacheEntry> = {};

function toClassification(triage: TriageResult): ClassificationResult {
  return {
    priority: triage.priority,
    category: triage.email_type || 'uncategorised',
    confidence: 0.9,
  };
}

export function useEmailDetail(
  email: Email | null,
  enabled: boolean = true,
  currentUserEmail?: string | null,
) {
  const [loading, setLoading] = useState(false);      // Phase 1 triage loading
  const [enriching, setEnriching] = useState(false);  // Phase 2 enrichment loading
  const [error, setError] = useState<string | null>(null);

  const [classification, setClassification] = useState<ClassificationResult | null>(null);
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [precedents, setPrecedents] = useState<PrecedentItem[]>([]);
  const [pipelineCommitments, setPipelineCommitments] = useState<CommitmentItem[]>([]);

  const [attachments, setAttachments] = useState<Attachment[]>([]);

  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [isSendingDraft, setIsSendingDraft] = useState(false);
  const [activeStyle, setActiveStyle] = useState<'standard' | 'formal' | 'indepth'>('standard');
  const [aiDrafts, setAiDrafts] = useState<Record<'standard' | 'formal' | 'indepth', string | null>>({
    standard: null, formal: null, indepth: null,
  });
  const [isDraftApproved, setIsDraftApproved] = useState(false);

  useEffect(() => {
    if (!email || !enabled) {
      const t = setTimeout(() => {
        setClassification(null);
        setTriageResult(null);
        setPrecedents([]);
        setPipelineCommitments([]);
        setAiDrafts({ standard: null, formal: null, indepth: null });
        setActiveStyle('standard');
        setIsDraftApproved(false);
        setError(null);
        setAttachments([]);
      }, 0);
      return () => clearTimeout(t);
    }

    async function load(currEmail: Email) {
      setError(null);
      setPipelineCommitments([]);
      setPrecedents([]);
      setAttachments([]);
      setAiDrafts({ standard: null, formal: null, indepth: null });
      setActiveStyle('standard');
      setIsDraftApproved(false);

      // ── PHASE 1: Show triage INSTANTLY ──────────────────────────────────────
      // The inbox batch already computed triage — use it directly, no API call.
      const triage = currEmail.triage || null;
      if (triage) {
        setTriageResult(triage);
        setClassification(toClassification(triage));
        setLoading(false);
      } else {
        setLoading(true); // only show spinner if we truly have nothing yet
      }

      // ── Fetch attachment metadata (lazy — only when email has attachments) ────
      if (currEmail.hasAttachments) {
        fetchAttachments(currEmail.id)
          .then((atts) => {
            if (!cancelled) setAttachments(atts);
          })
          .catch((err) => {
            console.warn('[attachments] Failed to fetch:', err);
            if (!cancelled) setAttachments([]);
          });
      }

      // ── Check enrichment cache ───────────────────────────────────────────────
      const cached = enrichCache[currEmail.id] || readEnrichCache()[currEmail.id];
      if (cached) {
        enrichCache[currEmail.id] = cached;
        setPipelineCommitments(cached.commitments);
        setPrecedents(cached.precedents);
        if (cached.draft_reply) {
          setAiDrafts((prev) => ({ ...prev, standard: cached.draft_reply }));
        }
        setLoading(false);
        return;
      }

      // ── PHASE 2: Background enrichment (commitment + rag in parallel) ────────
      setEnriching(true);
      try {
        let result: Record<string, unknown>;

        if (triage) {
          // Fast path: skip triage, pass existing scores to /api/agent/enrich
          result = await enrichEmail({
            email_id: currEmail.id,
            sender: currEmail.sender,
            subject: currEmail.subject,
            body: currEmail.body,
            received_at: currEmail.received_at,
            axes: triage.axes,
            composite_score: triage.composite_score,
            priority: triage.priority,
            approval_mode: triage.approval_mode,
            triage_reasoning: triage.triage_reasoning,
            current_user_email: currentUserEmail,
          });
        } else {
          // Fallback: full pipeline (no prior triage available)
          result = await processEmailFull({
            email_id: currEmail.id,
            sender: currEmail.sender,
            subject: currEmail.subject,
            body: currEmail.body,
            received_at: currEmail.received_at,
          });
          // Extract triage from full pipeline result
          if (!triage && result.priority) {
            const fullTriage: TriageResult = {
              axes: (result.axes as TriageResult['axes']) || [],
              composite_score: (result.composite_score as number) || 0,
              priority: result.priority as TriageResult['priority'],
              approval_mode: result.approval_mode as TriageResult['approval_mode'],
              email_type: result.email_type as string | undefined,
              triage_reasoning: result.triage_reasoning as string | undefined,
            };
            setTriageResult(fullTriage);
            setClassification(toClassification(fullTriage));
          }
        }

        const commitments = (result.commitments as CommitmentItem[]) || [];
        const precedents: PrecedentItem[] = ((result.precedents as unknown[]) || []).map((p) => {
          const pr = p as Record<string, unknown>;
          return {
            email_id: String(pr.email_id || ''),
            subject: String(pr.subject || ''),
            snippet: String(pr.snippet || pr.masked_body || ''),
            similarity_score: Number(pr.similarity_score || 0),
          };
        });

        // Cache enrichment (no draft — draft is generated on demand)
        const entry: EnrichCacheEntry = { commitments, precedents, draft_reply: null };
        writeEnrichCache(currEmail.id, entry);

        setPipelineCommitments(commitments);
        setPrecedents(precedents);
        // Draft is intentionally NOT set here — user must click "Generate Draft"
      } catch (err: unknown) {
        console.error('[useEmailDetail] enrichment error:', err);
        setError(err instanceof Error ? err.message : 'Failed to load email enrichment');
      } finally {
        setLoading(false);
        setEnriching(false);
      }
    }

    let cancelled = false;
    const t = setTimeout(() => load(email), 0);
    return () => { cancelled = true; clearTimeout(t); };
  }, [email, enabled, currentUserEmail]);

  const generateDraft = async (styleToGen?: 'standard' | 'formal' | 'indepth') => {
    if (!email) return;
    const style = styleToGen || activeStyle;

    // Already generated for this style — just switch tab
    if (aiDrafts[style]) { setActiveStyle(style); return; }

    setIsGeneratingDraft(true);
    setError(null);
    setIsDraftApproved(false);

    try {
      if (style === 'standard') {
        // Standard draft: use /api/agent/enrich with generate_draft=true so it
        // runs RAG alongside any remaining commitment state.
        const triage = email.triage;
        const result = await enrichEmail({
          email_id: email.id,
          sender: email.sender,
          subject: email.subject,
          body: email.body,
          received_at: email.received_at,
          axes: triage?.axes,
          composite_score: triage?.composite_score,
          priority: triage?.priority,
          approval_mode: triage?.approval_mode,
          triage_reasoning: triage?.triage_reasoning,
          current_user_email: currentUserEmail ?? undefined,
          generate_draft: true,
        });
        const draft = (result.draft_reply as string) || '';
        setAiDrafts((prev) => ({ ...prev, standard: draft }));

        // Also backfill precedents if they weren't loaded yet
        if (result.precedents?.length && precedents.length === 0) {
          setPrecedents((result.precedents as PrecedentItem[]) || []);
        }
      } else {
        // Formal / in-depth: use the style-specific draft endpoint
        const draftRes = await generateEmailDraft(
          email.body, style, email.sender, email.subject, currentUserEmail ?? undefined,
        );
        setAiDrafts((prev) => ({ ...prev, [style]: draftRes.draft }));
      }
      setActiveStyle(style);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to generate ${style} draft`);
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  const setAiDraft = (text: string) => {
    setAiDrafts((prev) => ({ ...prev, [activeStyle]: text }));
  };

  const sendDraft = async (comment: string) => {
    if (!email) return;
    setIsSendingDraft(true);
    setError(null);
    setIsDraftApproved(false);
    try {
      await sendEmailReply(email.id, comment);
      setIsDraftApproved(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to send email reply');
    } finally {
      setIsSendingDraft(false);
    }
  };

  return {
    loading,
    enriching,   // true while commitment+rag are loading in background
    error,
    classification,
    triageResult,
    precedents,
    pipelineCommitments,
    attachments,
    aiDraft: aiDrafts[activeStyle],
    setAiDraft,
    isGeneratingDraft,
    generateDraft,
    isDraftApproved,
    setIsDraftApproved,
    activeStyle,
    setActiveStyle,
    aiDrafts,
    isSendingDraft,
    sendDraft,
  };
}
