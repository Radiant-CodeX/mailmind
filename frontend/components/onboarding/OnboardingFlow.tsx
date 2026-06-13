'use client';

import React, { useState, useEffect, useLayoutEffect, useCallback } from 'react';

interface OnboardingFlowProps {
  userEmail: string | null;
  userName: string | null;
  onComplete: (data: { role: string; goals: string[] }) => void;
}

const ROLES = [
  { id: 'executive', label: 'Executive / C-Suite' },
  { id: 'manager', label: 'Manager / Team Lead' },
  { id: 'developer', label: 'Developer / Engineer' },
  { id: 'sales', label: 'Sales / BD' },
  { id: 'support', label: 'Support / CS' },
  { id: 'other', label: 'Other' },
];

const GOALS = [
  { id: 'inbox_zero', label: 'Reach Inbox Zero' },
  { id: 'draft_faster', label: 'Draft Replies Faster' },
  { id: 'track_commitments', label: 'Track Commitments' },
  { id: 'reduce_stress', label: 'Reduce Email Stress' },
  { id: 'stay_organized', label: 'Stay Organized' },
];

interface TourStep {
  targetId: string | null;
  title: string;
  description: string;
  padding?: number;
}

const TOUR_STEPS: TourStep[] = [
  {
    targetId: 'sidebar',
    title: 'Your command center',
    description: 'Navigate between your inbox folders, calendar, tasks, AI tools, and metrics — all from this sidebar.',
    padding: 4,
  },
  {
    targetId: 'sidebar-compose-btn',
    title: 'Compose anytime',
    description: 'Start a new email in seconds. MailMind drafts replies in your Tone DNA style — so it sounds like you.',
    padding: 6,
  },
  {
    targetId: 'email-list-panel',
    title: 'AI triage at a glance',
    description: 'Every email is scored across 5 axes — deadline urgency, sender authority, sentiment, decay, and action type — so you always know what to handle first.',
    padding: 6,
  },
  {
    targetId: null,
    title: 'Full AI pipeline on every email',
    description: 'Click any email to unlock classification, commitment extraction, calendar conflict detection, RAG-powered precedent retrieval, and an AI-generated draft — all in parallel.',
  },
];

type Phase = 'welcome' | 'about' | 'tour' | 'complete';

export function OnboardingFlow({ userEmail, userName, onComplete }: OnboardingFlowProps) {
  const [phase, setPhase] = useState<Phase>('welcome');
  const [role, setRole] = useState('');
  const [goals, setGoals] = useState<string[]>([]);
  const [tourStep, setTourStep] = useState(0);
  const [spotlightRect, setSpotlightRect] = useState<DOMRect | null>(null);
  const [tooltipSide, setTooltipSide] = useState<'right' | 'left' | 'bottom' | 'center'>('center');

  const currentTourStep = TOUR_STEPS[tourStep];

  const measureSpotlight = useCallback(() => {
    if (phase !== 'tour' || !currentTourStep?.targetId) {
      setSpotlightRect(null);
      setTooltipSide('center');
      return;
    }
    const el = document.getElementById(currentTourStep.targetId);
    if (!el) {
      setSpotlightRect(null);
      setTooltipSide('center');
      return;
    }
    const rect = el.getBoundingClientRect();
    setSpotlightRect(rect);
    // Decide tooltip side
    const mid = window.innerWidth / 2;
    if (rect.right + 340 < window.innerWidth) {
      setTooltipSide('right');
    } else if (rect.left - 340 > 0) {
      setTooltipSide('left');
    } else if (rect.bottom + 160 < window.innerHeight) {
      setTooltipSide('bottom');
    } else {
      setTooltipSide('center');
    }
    void mid;
  }, [phase, currentTourStep]);

  useLayoutEffect(() => {
    measureSpotlight();
  }, [measureSpotlight]);

  useEffect(() => {
    window.addEventListener('resize', measureSpotlight);
    return () => window.removeEventListener('resize', measureSpotlight);
  }, [measureSpotlight]);

  const toggleGoal = (id: string) => {
    setGoals((prev) =>
      prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]
    );
  };

  const handleAboutNext = () => {
    if (!role) return;
    setPhase('tour');
    setTourStep(0);
  };

  const handleTourNext = () => {
    if (tourStep < TOUR_STEPS.length - 1) {
      setTourStep((s) => s + 1);
    } else {
      setPhase('complete');
    }
  };

  const handleTourBack = () => {
    if (tourStep > 0) {
      setTourStep((s) => s - 1);
    } else {
      setPhase('about');
    }
  };

  const handleComplete = () => {
    onComplete({ role, goals });
  };

  // Tooltip position when spotlighting an element
  const getTooltipStyle = (): React.CSSProperties => {
    if (!spotlightRect || tooltipSide === 'center') {
      return {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        width: 320,
        zIndex: 9999,
      };
    }
    const pad = (currentTourStep?.padding ?? 6) + 2;
    if (tooltipSide === 'right') {
      return {
        position: 'fixed',
        top: Math.max(16, Math.min(spotlightRect.top + spotlightRect.height / 2 - 100, window.innerHeight - 230)),
        left: spotlightRect.right + pad + 16,
        width: 300,
        zIndex: 9999,
      };
    }
    if (tooltipSide === 'left') {
      return {
        position: 'fixed',
        top: Math.max(16, Math.min(spotlightRect.top + spotlightRect.height / 2 - 100, window.innerHeight - 230)),
        right: window.innerWidth - spotlightRect.left + pad + 16,
        width: 300,
        zIndex: 9999,
      };
    }
    // bottom
    return {
      position: 'fixed',
      top: spotlightRect.bottom + pad + 16,
      left: Math.max(16, Math.min(spotlightRect.left + spotlightRect.width / 2 - 150, window.innerWidth - 332)),
      width: 300,
      zIndex: 9999,
    };
  };

  const displayName = userName || (userEmail ? userEmail.split('@')[0] : 'there');

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-[9990] transition-all duration-300"
        style={{
          background: phase === 'tour' && spotlightRect
            ? 'transparent'
            : 'rgba(0,0,0,0.75)',
          backdropFilter: phase === 'tour' && spotlightRect ? 'none' : 'blur(2px)',
        }}
      />

      {/* Spotlight lens (only during tour with a target element) */}
      {phase === 'tour' && spotlightRect && (
        <div
          className="fixed pointer-events-none transition-all duration-300"
          style={{
            top: spotlightRect.top - (currentTourStep?.padding ?? 6),
            left: spotlightRect.left - (currentTourStep?.padding ?? 6),
            width: spotlightRect.width + (currentTourStep?.padding ?? 6) * 2,
            height: spotlightRect.height + (currentTourStep?.padding ?? 6) * 2,
            borderRadius: 12,
            boxShadow: '0 0 0 9999px rgba(0,0,0,0.80)',
            border: '2px solid hsl(var(--p) / 0.7)',
            zIndex: 9995,
          }}
        />
      )}

      {/* ── WELCOME ── */}
      {phase === 'welcome' && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          <div className="bg-base-100 rounded-2xl shadow-2xl border border-base-300 w-full max-w-md mx-4 overflow-hidden animate-fade-in">
            <div className="px-8 py-10 text-center">
              <div className="flex items-center justify-center gap-3 mb-6">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/mailmind-logo.svg" alt="MailMind" className="w-14 h-14 rounded-2xl shadow-lg" />
              </div>
              <h1 className="text-2xl font-bold text-base-content mb-1">
                Welcome to MailMind
                {displayName !== 'there' && (
                  <span className="text-primary">, {displayName.charAt(0).toUpperCase() + displayName.slice(1)}</span>
                )}
              </h1>
              <p className="text-base-content/60 text-sm mb-2">
                Your AI-powered email co-pilot studio
              </p>
              <div className="flex flex-wrap justify-center gap-2 my-5">
                {[
                  { icon: '⚡', label: '5-axis triage' },
                  { icon: '🧠', label: 'Tone DNA drafts' },
                  { icon: '📅', label: 'Commitment tracking' },
                  { icon: '🔍', label: 'RAG precedents' },
                ].map((pill) => (
                  <span key={pill.label} className="flex items-center gap-1.5 px-3 py-1 bg-base-200 rounded-full text-xs text-base-content/70 font-medium">
                    <span>{pill.icon}</span> {pill.label}
                  </span>
                ))}
              </div>
              <p className="text-base-content/50 text-xs mb-6">
                Let's take a quick 2-minute tour to get you set up.
              </p>
              <button
                onClick={() => setPhase('about')}
                className="w-full py-3 bg-primary text-base-100 font-bold rounded-xl text-sm hover:opacity-90 transition-opacity cursor-pointer"
              >
                Get Started →
              </button>
              <button
                onClick={() => onComplete({ role: '', goals: [] })}
                className="mt-3 text-xs text-base-content/40 hover:text-base-content/60 transition-colors cursor-pointer"
              >
                Skip tour
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── ABOUT YOU ── */}
      {phase === 'about' && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          <div className="bg-base-100 rounded-2xl shadow-2xl border border-base-300 w-full max-w-md mx-4 overflow-hidden animate-fade-in">
            {/* Progress bar */}
            <div className="h-1 bg-base-200">
              <div className="h-full bg-primary transition-all duration-500" style={{ width: '25%' }} />
            </div>
            <div className="px-7 py-6">
              <p className="text-[10px] font-bold uppercase tracking-widest text-base-content/40 mb-1">Step 1 of 2</p>
              <h2 className="text-lg font-bold text-base-content mb-0.5">Tell us about yourself</h2>
              <p className="text-xs text-base-content/50 mb-5">This helps us tailor MailMind to your workflow.</p>

              {/* Role */}
              <div className="mb-5">
                <p className="text-xs font-semibold text-base-content/70 mb-2">Your role</p>
                <div className="grid grid-cols-2 gap-2">
                  {ROLES.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => setRole(r.id)}
                      className={`px-3 py-2 rounded-lg border text-xs font-medium transition-all cursor-pointer text-left ${
                        role === r.id
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-base-300 text-base-content/60 hover:border-base-content/30 hover:text-base-content'
                      }`}
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Goals */}
              <div className="mb-6">
                <p className="text-xs font-semibold text-base-content/70 mb-2">
                  What are you hoping to achieve? <span className="text-base-content/40 font-normal">(pick all that apply)</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  {GOALS.map((g) => (
                    <button
                      key={g.id}
                      onClick={() => toggleGoal(g.id)}
                      className={`px-3 py-1.5 rounded-full border text-xs font-medium transition-all cursor-pointer ${
                        goals.includes(g.id)
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-base-300 text-base-content/60 hover:border-base-content/30 hover:text-base-content'
                      }`}
                    >
                      {g.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setPhase('welcome')}
                  className="flex-1 py-2.5 border border-base-300 text-base-content/60 font-semibold rounded-xl text-sm hover:bg-base-200 transition-colors cursor-pointer"
                >
                  Back
                </button>
                <button
                  onClick={handleAboutNext}
                  disabled={!role}
                  className="flex-2 flex-grow py-2.5 bg-primary disabled:opacity-40 text-base-100 font-bold rounded-xl text-sm hover:opacity-90 transition-all cursor-pointer"
                >
                  Continue →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── TOUR ── */}
      {phase === 'tour' && (
        <div style={getTooltipStyle()} className="animate-fade-in">
          <div className="bg-base-100 rounded-2xl shadow-2xl border border-base-300 overflow-hidden">
            {/* Progress bar */}
            <div className="h-1 bg-base-200">
              <div
                className="h-full bg-primary transition-all duration-500"
                style={{ width: `${50 + ((tourStep + 1) / TOUR_STEPS.length) * 50}%` }}
              />
            </div>
            <div className="p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold uppercase tracking-widest text-primary/70">
                  Tour · {tourStep + 1} of {TOUR_STEPS.length}
                </span>
                <div className="flex gap-1">
                  {TOUR_STEPS.map((_, i) => (
                    <div
                      key={i}
                      className={`w-1.5 h-1.5 rounded-full transition-all ${
                        i === tourStep ? 'bg-primary w-4' : i < tourStep ? 'bg-primary/40' : 'bg-base-300'
                      }`}
                    />
                  ))}
                </div>
              </div>

              <h3 className="font-bold text-base-content text-sm mb-1.5">{currentTourStep.title}</h3>
              <p className="text-xs text-base-content/60 leading-relaxed mb-4">{currentTourStep.description}</p>

              <div className="flex gap-2">
                <button
                  onClick={handleTourBack}
                  className="flex-1 py-2 border border-base-300 text-base-content/60 font-semibold rounded-lg text-xs hover:bg-base-200 transition-colors cursor-pointer"
                >
                  ← Back
                </button>
                <button
                  onClick={handleTourNext}
                  className="flex-grow py-2 bg-primary text-base-100 font-bold rounded-lg text-xs hover:opacity-90 transition-all cursor-pointer"
                >
                  {tourStep < TOUR_STEPS.length - 1 ? 'Next →' : 'Almost done →'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── COMPLETE ── */}
      {phase === 'complete' && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center">
          <div className="bg-base-100 rounded-2xl shadow-2xl border border-base-300 w-full max-w-md mx-4 overflow-hidden animate-fade-in">
            <div className="h-1 bg-primary" />
            <div className="px-8 py-8 text-center">
              <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-xl font-bold text-base-content mb-1">You're all set!</h2>
              <p className="text-base-content/60 text-sm mb-6">MailMind is ready to supercharge your inbox.</p>

              <div className="bg-base-200 rounded-xl p-4 mb-6 text-left space-y-3">
                <p className="text-xs font-bold text-base-content/70 uppercase tracking-widest mb-2">Quick tips</p>
                {[
                  { icon: '👆', tip: 'Click any email to run the full AI pipeline' },
                  { icon: '⚡', tip: 'Triage scores appear within 2–3 seconds of loading' },
                  { icon: '✍️', tip: 'Approve or edit AI drafts before sending' },
                  { icon: '📊', tip: 'Check the Metrics tab to see performance live' },
                ].map((item) => (
                  <div key={item.tip} className="flex items-start gap-2.5">
                    <span className="text-base shrink-0 mt-0.5">{item.icon}</span>
                    <p className="text-xs text-base-content/60">{item.tip}</p>
                  </div>
                ))}
              </div>

              <button
                onClick={handleComplete}
                className="w-full py-3 bg-primary text-base-100 font-bold rounded-xl text-sm hover:opacity-90 transition-opacity cursor-pointer"
              >
                Start using MailMind
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
