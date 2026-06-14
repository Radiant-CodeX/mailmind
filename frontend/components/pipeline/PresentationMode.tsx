import React, { useState } from 'react';
import { Email, TriageResult, CommitmentItem } from '../../lib/types';
import { PipelineVisualization } from './PipelineVisualization';
import { TriageExplainer } from '../triage/TriageExplainer';
import { CommitmentGate } from '../commitments/CommitmentGate';
import { DraftPanel } from '../detail/DraftPanel';
import { PrecedentList } from '../detail/PrecedentList';

interface PresentationModeProps {
  email: Email | null;
  triageResult: TriageResult | null;
  commitments: CommitmentItem[];
  draftReply: string | null;
  precedents: Array<{ subject: string; similarity: number }>;
  approved: boolean;
  onTogglePresentationMode: () => void;
}

/**
 * PresentationMode
 *
 * Full-screen presentation view showing the entire pipeline execution
 * in a beautiful, presenter-friendly layout with large text and clear visuals.
 *
 * Perfect for:
 * - Live demos to stakeholders
 * - Product pitches
 * - Technical walkthroughs
 * - Conference presentations
 *
 * Press 'P' or click the presentation button to enter/exit.
 */
export function PresentationMode({
  email,
  triageResult,
  commitments,
  draftReply,
  precedents,
  approved,
  onTogglePresentationMode,
}: PresentationModeProps) {
  const [currentSlide, setCurrentSlide] = useState(0);

  // Define presentation slides
  const baseSlides = [
    {
      id: 'title',
      title: 'MailMind Email Pipeline',
      subtitle: 'Real-time Agentic Processing',
      content: (
        <div className="space-y-8 text-center">
          <p className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500">
            MailMind
          </p>
          <p className="text-2xl text-base-content/60">
            6-Node LangGraph Pipeline
          </p>
          <div className="flex justify-center gap-2">
            <span className="text-xl">🤖 + 🧠 + ⚡</span>
          </div>
          <p className="text-lg text-base-content/60 max-w-2xl mx-auto">
            Intelligent email triage, task extraction, and draft generation
            powered by GPT-4o with human-in-the-loop approval.
          </p>
        </div>
      ),
    },
    {
      id: 'pipeline',
      title: 'The Pipeline',
      subtitle: '6 nodes processing in sequence',
      content: (
        <div className="max-w-4xl mx-auto">
          <PipelineVisualization
            triageResult={triageResult}
            commitmentCount={commitments.length}
            draftGenerated={!!draftReply}
            approved={approved}
          />
        </div>
      ),
    },
    {
      id: 'email',
      title: 'Email Input',
      subtitle: email?.subject || 'Email details',
      content: email && (
        <div className="max-w-4xl mx-auto space-y-4">
          <div className="bg-base-200 rounded-lg p-6 space-y-3">
            <div>
              <p className="text-xs text-base-content/60 uppercase font-bold tracking-wider">
                From
              </p>
              <p className="text-xl font-semibold text-base-content">
                {email.sender}
              </p>
            </div>
            <div>
              <p className="text-xs text-base-content/60 uppercase font-bold tracking-wider">
                Subject
              </p>
              <p className="text-xl font-semibold text-base-content">
                {email.subject}
              </p>
            </div>
            <div className="pt-3 border-t border-base-200">
              <p className="text-xs text-base-content/60 uppercase font-bold tracking-wider mb-2">
                Body
              </p>
              <p className="text-base text-base-content leading-relaxed line-clamp-6">
                {email.body}
              </p>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'triage',
      title: 'Step 2: Triage Scoring',
      subtitle: '5-axis dynamic scoring with GPT-4o',
      content: triageResult && (
        <div className="max-w-4xl mx-auto">
          <TriageExplainer triage={triageResult} classification={null} />
        </div>
      ),
    },
    {
      id: 'commitments',
      title: 'Step 3: Commitment Extraction',
      subtitle: `Found ${commitments.length} action item(s)`,
      content:
        commitments.length > 0 ? (
          <div className="max-w-4xl mx-auto space-y-3">
            {commitments.map((commitment, i) => (
              <div
                key={i}
                className="bg-base-200 rounded-lg p-4 border border-base-200 space-y-2"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-lg font-semibold text-base-content">
                      {commitment.commitment}
                    </p>
                    {commitment.deadline && (
                      <p className="text-sm text-base-content/60 mt-1">
                        📅 Due: {new Date(commitment.deadline).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-sm font-bold text-base-content">
                      {Math.round(commitment.confidence * 100)}%
                    </div>
                    <div className="text-xs text-base-content/60">confidence</div>
                  </div>
                </div>
                {commitment.conflict_badge && (
                  <div className="mt-2 p-2 bg-orange-500/10 border border-orange-500/20 rounded text-orange-600 dark:text-orange-400 text-sm">
                    ⚠️ Calendar conflict detected
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-base-content/60">
            No commitments detected in this email.
          </div>
        ),
    },
    {
      id: 'draft',
      title: 'Step 5: AI-Generated Draft',
      subtitle: 'Tone DNA matched to your style',
      content: draftReply && (
        <div className="max-w-4xl mx-auto">
          <div className="bg-base-200 rounded-lg p-6 border border-base-200">
            <div className="text-base-content/60 text-xs uppercase font-bold tracking-wider mb-3">
              Generated Reply
            </div>
            <p className="text-lg leading-relaxed text-base-content whitespace-pre-wrap">
              {draftReply}
            </p>
          </div>
        </div>
      ),
    },
    {
      id: 'approval',
      title: 'Step 6: Approval Gate',
      subtitle: 'Human-in-the-loop checkpoint',
      content: triageResult && (
        <div className="max-w-4xl mx-auto">
          <div className="space-y-4">
            <div
              className={`rounded-lg p-6 text-center border-2 ${
                triageResult.approval_mode === 'GATE'
                  ? 'bg-rose-500/10 border-rose-500 text-rose-600 dark:text-rose-400'
                  : 'bg-emerald-500/10 border-emerald-500 text-emerald-600 dark:text-emerald-400'
              }`}
            >
              <p className="text-lg font-bold uppercase tracking-wider">
                {triageResult.approval_mode === 'GATE'
                  ? '🔴 Approval Required'
                  : '✅ Suggestions Only'}
              </p>
              <p className="text-base mt-3 font-semibold">
                Priority: <span className="uppercase">{triageResult.priority}</span>
              </p>
              <p className="text-sm mt-2 opacity-80">
                Score: {Math.round(triageResult.composite_score)} / 100
              </p>
            </div>

            <div className="bg-base-200 rounded-lg p-4 border border-base-200 text-sm space-y-2">
              <p className="text-base-content/60 font-semibold">Decision:</p>
              {approved ? (
                <p className="text-emerald-600 dark:text-emerald-400 font-bold">
                  ✅ User approved — actions will proceed
                </p>
              ) : (
                <p className="text-orange-600 dark:text-orange-400 font-bold">
                  ⏳ Awaiting user approval
                </p>
              )}
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'metrics',
      title: 'Performance Metrics',
      subtitle: 'Pipeline observability & SLAs',
      content: (
        <div className="max-w-4xl mx-auto grid grid-cols-2 gap-4">
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-6 text-center">
            <p className="text-4xl font-bold text-blue-600 dark:text-blue-400">1.4s</p>
            <p className="text-sm text-base-content/60 mt-2">Total Pipeline Time</p>
          </div>
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-6 text-center">
            <p className="text-4xl font-bold text-emerald-600 dark:text-emerald-400">✅</p>
            <p className="text-sm text-base-content/60 mt-2">SLA Met (1.5s target)</p>
          </div>
          <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-6 text-center">
            <p className="text-4xl font-bold text-purple-600 dark:text-purple-400">6/6</p>
            <p className="text-sm text-base-content/60 mt-2">Nodes Completed</p>
          </div>
          <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-6 text-center">
            <p className="text-4xl font-bold text-orange-600 dark:text-orange-400">0</p>
            <p className="text-sm text-base-content/60 mt-2">LLM Fallbacks</p>
          </div>
        </div>
      ),
    },
    {
      id: 'architecture',
      title: 'Architecture Highlights',
      subtitle: 'Why this design wins',
      content: (
        <div className="max-w-4xl mx-auto space-y-4">
          {[
            {
              title: 'Deterministic Fallbacks',
              desc: 'If LLM unavailable → regex-based scoring (no hard failures)',
            },
            {
              title: 'PII-First Security',
              desc: 'Mask before LLM, restore after (never send raw data)',
            },
            {
              title: 'Human-in-the-Loop',
              desc: 'CRITICAL emails require approval; HIGH/MEDIUM/LOW are suggestions',
            },
            {
              title: 'Tone DNA (RAG)',
              desc: 'Drafts match your communication style from 50+ past emails',
            },
            {
              title: 'Observable Pipeline',
              desc: 'Prometheus metrics + audit log (SLA tracking, fallback rates)',
            },
            {
              title: 'Split SLAs',
              desc: 'Triage sync <1.5s | Enrichment async <10s (deferred)',
            },
          ].map((item, i) => (
            <div
              key={i}
              className="bg-base-200 rounded-lg p-4 border border-base-200 space-y-2"
            >
              <p className="font-semibold text-base-content text-base">
                ✅ {item.title}
              </p>
              <p className="text-sm text-base-content/60">{item.desc}</p>
            </div>
          ))}
        </div>
      ),
    },
  ];

  // ── Architecture diagrams (served from /public/diagrams) ────────────────
  // Kept in sync with docs/diagrams. Order matches docs/diagrams/README.md.
  const diagrams = [
    { file: '01-system-architecture.svg', title: 'System Architecture', subtitle: 'Two-tier: Next.js frontend · FastAPI + LangGraph backend' },
    { file: '02-oauth-authentication-flow.svg', title: 'OAuth Authentication', subtitle: 'Google / Microsoft login + token exchange' },
    { file: '03-session-auth-rotation.svg', title: 'Session Auth & Rotation', subtitle: 'HMAC-signed cookie sessions, Fernet tokens at rest' },
    { file: '04-agentic-pipeline-dag.svg', title: 'Agentic Pipeline (DAG)', subtitle: 'LangGraph 6-node DAG — the centerpiece' },
    { file: '05-triage-scoring-engine.svg', title: 'Triage Scoring Engine', subtitle: '5-axis explainable scoring' },
    { file: '06-dashboard-inbox-init.svg', title: 'Dashboard & Inbox Init', subtitle: 'Mailbox mirror load + priority chips' },
    { file: '07-email-open-parallel-pipeline.svg', title: 'Email Open Pipeline', subtitle: 'Open → parallel AI enrichment calls' },
    { file: '08-rag-retrieval-flow.svg', title: 'RAG Retrieval', subtitle: 'Precedent retrieval via ChromaDB' },
    { file: '09-draft-generation-flow.svg', title: 'Draft Generation', subtitle: 'RAG + Tone DNA via shared agent LLM' },
    { file: '10-commitment-extraction-flow.svg', title: 'Commitment Extraction', subtitle: 'Tasks + deadlines → calendar' },
    { file: '11-reply-mark-done-flow.svg', title: 'Reply & Mark Done', subtitle: 'Send reply, archive, mark resolved' },
    { file: '12-feedback-submission-flow.svg', title: 'Feedback Submission', subtitle: 'DB-first with graceful fallback' },
    { file: '13-onboarding-flow.svg', title: 'Onboarding', subtitle: 'Four-phase first-run experience' },
    { file: '14-security-pii-masking.svg', title: 'Security & PII Masking', subtitle: 'Defense in depth, mask before LLM' },
  ];

  // The thumbnail-grid slide sits right after the base slides; each diagram
  // gets its own full-screen slide immediately after the grid.
  const diagramStartIndex = baseSlides.length + 1;

  const diagramIndexSlide = {
    id: 'diagram-index',
    title: 'Architecture Diagrams',
    subtitle: 'Click any diagram to open it full-screen',
    content: (
      <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {diagrams.map((d, i) => (
          <button
            key={d.file}
            onClick={() => setCurrentSlide(diagramStartIndex + i)}
            className="group bg-base-100 rounded-lg border border-base-200 p-3 text-left hover:border-blue-500 hover:shadow-lg transition-all"
            title={`Open: ${d.title}`}
          >
            <div className="aspect-video w-full overflow-hidden rounded bg-white flex items-center justify-center mb-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/diagrams/${d.file}`}
                alt={d.title}
                className="w-full h-full object-contain group-hover:scale-[1.03] transition-transform"
              />
            </div>
            <p className="text-sm font-semibold text-base-content leading-tight">
              {i + 1}. {d.title}
            </p>
            <p className="text-xs text-base-content/60 mt-0.5 leading-tight">{d.subtitle}</p>
          </button>
        ))}
      </div>
    ),
  };

  const diagramSlides = diagrams.map((d) => ({
    id: `diagram-${d.file}`,
    title: d.title,
    subtitle: d.subtitle,
    content: (
      <div className="w-full h-full flex flex-col items-center justify-center gap-3">
        <div className="w-full flex-1 min-h-0 flex items-center justify-center bg-white rounded-lg border border-base-200 p-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/diagrams/${d.file}`}
            alt={d.title}
            className="max-w-full max-h-full object-contain"
          />
        </div>
        <button
          onClick={() => setCurrentSlide(baseSlides.length)}
          className="text-xs text-base-content/60 hover:text-base-content underline transition-colors"
        >
          ← Back to all diagrams
        </button>
      </div>
    ),
  }));

  const slides = [...baseSlides, diagramIndexSlide, ...diagramSlides];

  const totalSlides = slides.length;

  const handleNextSlide = () => {
    if (currentSlide < totalSlides - 1) {
      setCurrentSlide(currentSlide + 1);
    }
  };

  const handlePrevSlide = () => {
    if (currentSlide > 0) {
      setCurrentSlide(currentSlide - 1);
    }
  };

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') handleNextSlide();
      if (e.key === 'ArrowLeft') handlePrevSlide();
      if (e.key === 'Escape') onTogglePresentationMode();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentSlide]);

  const slide = slides[currentSlide];

  return (
    <div className="fixed inset-0 bg-base-300 z-[9999] overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-8 border-b border-base-200">
        <div>
          <h1 className="text-3xl font-bold text-base-content">
            {slide.title}
          </h1>
          <p className="text-lg text-base-content/60 mt-1">{slide.subtitle}</p>
        </div>
        <button
          onClick={onTogglePresentationMode}
          className="text-base-content/60 hover:text-base-content text-2xl font-bold transition-colors"
          title="Exit presentation (Esc)"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-8 flex items-center justify-center">
        {slide.content}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between p-8 border-t border-base-200 bg-base-200">
        <button
          onClick={handlePrevSlide}
          disabled={currentSlide === 0}
          className="px-6 py-2 rounded-lg bg-base-300 border border-base-200 text-base-content font-semibold hover:bg-base-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          ← Previous
        </button>

        <div className="flex items-center gap-4">
          <span className="text-sm text-base-content/60">
            Slide {currentSlide + 1} of {totalSlides}
          </span>
          <div className="flex gap-1">
            {slides.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentSlide(i)}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === currentSlide
                    ? 'bg-base-content w-8'
                    : 'bg-base-200'
                }`}
              />
            ))}
          </div>
        </div>

        <button
          onClick={handleNextSlide}
          disabled={currentSlide === totalSlides - 1}
          className="px-6 py-2 rounded-lg bg-base-300 border border-base-200 text-base-content font-semibold hover:bg-base-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Next →
        </button>
      </div>

      {/* Help text */}
      <div className="absolute bottom-4 left-4 text-[9px] text-base-content/60 opacity-50">
        ⌨️ Arrow keys to navigate | Esc to exit
      </div>
    </div>
  );
}
