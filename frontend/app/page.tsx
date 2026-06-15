'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { HeroCanvas } from '../components/landing/HeroCanvas';
import { Preloader } from '../components/landing/Preloader';
import { WaitlistForm } from '../components/landing/WaitlistForm';

gsap.registerPlugin(ScrollTrigger);

/* ────────────────────────── data ────────────────────────── */

const FEATURES = [
  {
    icon: '◎',
    sender: 'Triage Engine',
    tag: 'CRITICAL',
    tagColor: 'bg-rose-500/15 text-rose-300 border-rose-400/30',
    time: 'now',
    title: '5-Axis Triage',
    body: 'Every email scored across deadline urgency, sender authority, sentiment, thread decay and action type — the inbox sorts itself by what actually matters.',
  },
  {
    icon: '✦',
    sender: 'Tone DNA',
    tag: 'YOUR VOICE',
    tagColor: 'bg-violet-500/15 text-violet-300 border-violet-400/30',
    time: '1m',
    title: 'Drafts that sound like you',
    body: 'MailMind learns your voice from your sent mail — formality, sentence rhythm, favorite phrases — and writes replies that sound like you, not a bot.',
  },
  {
    icon: '◈',
    sender: 'Precedent Recall',
    tag: 'RAG',
    tagColor: 'bg-indigo-500/15 text-indigo-300 border-indigo-400/30',
    time: '2m',
    title: 'Your past decisions, recalled',
    body: 'Retrieval surfaces how you handled similar emails before, injecting your past decisions as context for every new draft.',
  },
  {
    icon: '✓',
    sender: 'Commitment Tracker',
    tag: 'DEADLINE',
    tagColor: 'bg-amber-500/15 text-amber-300 border-amber-400/30',
    time: '5m',
    title: 'Promises become tasks',
    body: '"I\'ll send it by Friday" becomes a tracked task with a deadline — automatically pulled from every thread, never forgotten.',
  },
  {
    icon: '◷',
    sender: 'Calendar Radar',
    tag: 'CONFLICT',
    tagColor: 'bg-cyan-500/15 text-cyan-300 border-cyan-400/30',
    time: '12m',
    title: 'Double-bookings, flagged first',
    body: 'New commitments are checked against your calendar in real time. Conflicts get flagged before you hit send.',
  },
  {
    icon: '⬡',
    sender: 'Workspace',
    tag: 'MULTI-ACCOUNT',
    tagColor: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/30',
    time: '1h',
    title: 'Every inbox, one mind',
    body: 'Gmail and Outlook, multiple accounts, one workspace. Per-account tone profiles and isolated retrieval keep contexts clean.',
  },
];

const PIPELINE = [
  { step: '01', name: 'Ingest', desc: 'PII masked, payload validated, queued.' },
  { step: '02', name: 'Triage', desc: 'Five scoring axes rank true urgency.' },
  { step: '03', name: 'Commitments', desc: 'Promises extracted with deadlines.' },
  { step: '04', name: 'Calendar', desc: 'Conflicts detected deterministically.' },
  { step: '05', name: 'Draft', desc: 'Precedent-aware reply in your voice.' },
  { step: '06', name: 'Approve', desc: 'You stay in the loop. Always.' },
];

const STATS = [
  { value: '1.5s', label: 'triage SLA' },
  { value: '5', label: 'scoring axes' },
  { value: '32', label: 'workspace themes' },
  { value: '100%', label: 'human-approved sends' },
];

/* ────────────────────────── page ────────────────────────── */

export default function LandingPage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const [loaded, setLoaded] = useState(false);
  const handlePreloaderDone = useCallback(() => setLoaded(true), []);

  /* hero + nav entrance — fires once after the preloader finishes.
     Guarded by a ref (NOT reverted on cleanup) so React StrictMode's
     double-mount in dev can't reset and replay the animation. */
  const heroPlayed = useRef(false);
  useEffect(() => {
    if (!loaded || heroPlayed.current) return;
    heroPlayed.current = true;

    gsap
      .timeline({ defaults: { ease: 'power3.out' } })
      .from('[data-hero-badge]', { y: 24, opacity: 0, duration: 0.7, delay: 0.05 })
      .from('[data-hero-line]', { y: 80, opacity: 0, duration: 1, stagger: 0.12 }, '-=0.4')
      .from('[data-hero-sub]', { y: 30, opacity: 0, duration: 0.8 }, '-=0.55')
      .from('[data-hero-cta]', { y: 20, opacity: 0, duration: 0.7, stagger: 0.1 }, '-=0.5')
      .from('[data-hero-stat]', { y: 24, opacity: 0, duration: 0.6, stagger: 0.08 }, '-=0.4');

    gsap.from('[data-nav]', { y: -40, opacity: 0, duration: 0.8, ease: 'power2.out' });

    // re-measure scroll positions now that the preloader overlay is gone
    ScrollTrigger.refresh();
  }, [loaded]);

  useEffect(() => {
    // globals.css locks body scroll for the dashboard; the landing needs window scroll
    document.body.style.overflow = 'auto';
    document.body.style.height = 'auto';

    const ctx = gsap.context(() => {
      /* section headings */
      gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((el) => {
        gsap.from(el, {
          y: 60,
          opacity: 0,
          duration: 0.9,
          ease: 'power3.out',
          scrollTrigger: { trigger: el, start: 'top 85%' },
        });
      });

      /* feature cards: per-card reveal, fire once, self-clearing so a missed
         trigger can never leave a card invisible */
      gsap.utils.toArray<HTMLElement>('[data-feature-card]').forEach((card, i) => {
        gsap.fromTo(
          card,
          { y: 60, autoAlpha: 0 },
          {
            y: 0,
            autoAlpha: 1,
            duration: 0.7,
            delay: (i % 3) * 0.1,
            ease: 'power3.out',
            clearProps: 'all',
            scrollTrigger: { trigger: card, start: 'top 92%', once: true },
          },
        );
      });

      /* circular pipeline: nodes pop in around the ring */
      gsap.from('[data-pipe-node]', {
        scale: 0,
        opacity: 0,
        duration: 0.7,
        stagger: 0.12,
        ease: 'back.out(1.8)',
        scrollTrigger: { trigger: '[data-pipeline-wheel]', start: 'top 75%' },
      });

      /* the dashed orbit ring slowly rotates forever */
      gsap.to('[data-pipe-ring]', {
        rotation: 360,
        duration: 60,
        repeat: -1,
        ease: 'none',
        transformOrigin: 'center center',
      });

      /* center envelope floats and sways */
      gsap.to('[data-pipe-envelope]', {
        y: -14,
        rotation: 3,
        duration: 2.6,
        yoyo: true,
        repeat: -1,
        ease: 'sine.inOut',
      });
      gsap.from('[data-pipe-envelope]', {
        scale: 0,
        duration: 0.8,
        ease: 'back.out(1.6)',
        scrollTrigger: { trigger: '[data-pipeline-wheel]', start: 'top 75%' },
      });

      /* big CTA zoom */
      gsap.from('[data-final-cta]', {
        scale: 0.92,
        opacity: 0,
        duration: 1,
        ease: 'power3.out',
        scrollTrigger: { trigger: '[data-final-cta]', start: 'top 80%' },
      });

      /* gradient orbs drift */
      gsap.to('[data-orb-1]', { y: -60, x: 40, duration: 9, yoyo: true, repeat: -1, ease: 'sine.inOut' });
      gsap.to('[data-orb-2]', { y: 50, x: -30, duration: 11, yoyo: true, repeat: -1, ease: 'sine.inOut' });

      /* cursor spotlight tracking on the email cards */
      gsap.utils.toArray<HTMLElement>('[data-feature-card]').forEach((card) => {
        card.addEventListener('mousemove', (e) => {
          const r = card.getBoundingClientRect();
          card.style.setProperty('--mx', `${e.clientX - r.left}px`);
          card.style.setProperty('--my', `${e.clientY - r.top}px`);
        });
      });

      /* magnetic buttons */
      gsap.utils.toArray<HTMLElement>('[data-magnetic]').forEach((btn) => {
        const qx = gsap.quickTo(btn, 'x', { duration: 0.35, ease: 'power3.out' });
        const qy = gsap.quickTo(btn, 'y', { duration: 0.35, ease: 'power3.out' });

        btn.addEventListener('mousemove', (e) => {
          const r = btn.getBoundingClientRect();
          qx((e.clientX - (r.left + r.width / 2)) * 0.35);
          qy((e.clientY - (r.top + r.height / 2)) * 0.35);
        });
        btn.addEventListener('mouseleave', () => {
          gsap.to(btn, { x: 0, y: 0, duration: 0.7, ease: 'elastic.out(1, 0.35)' });
        });
      });

    }, rootRef);

    return () => {
      ctx.revert();
      document.body.style.overflow = '';
      document.body.style.height = '';
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className="min-h-screen bg-[#05060a] text-white antialiased overflow-x-hidden selection:bg-indigo-500/40"
      style={{ fontFamily: 'var(--font-space), var(--font-geist-sans), sans-serif' }}
    >
      {!loaded && <Preloader onDone={handlePreloaderDone} />}

      {/* ── Nav ─────────────────────────────────────────── */}
      <nav
        data-nav
        className="fixed top-0 inset-x-0 z-50 backdrop-blur-xl bg-[#05060a]/60 border-b border-white/5"
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center font-black text-sm shadow-lg shadow-indigo-500/30">
              M
            </div>
            <span className="font-semibold tracking-tight text-[15px]">MailMind</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-white/60">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#pipeline" className="hover:text-white transition-colors">How it works</a>
            <a href="#security" className="hover:text-white transition-colors">Security</a>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm text-white/70 hover:text-white transition-colors px-3 py-2"
            >
              Sign in
            </Link>
            <a
              href="#waitlist"
              className="text-sm font-medium bg-white text-black px-4 py-2 rounded-full hover:bg-white/90 transition-all hover:scale-[1.03] active:scale-[0.98]"
            >
              Request access
            </a>
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────── */}
      <header className="relative min-h-screen flex items-center justify-center overflow-hidden">
        <HeroCanvas />
        {/* vignette + orbs */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_30%,#05060a_85%)] pointer-events-none" />
        <div data-orb-1 className="absolute -top-32 -left-32 w-[480px] h-[480px] rounded-full bg-indigo-600/20 blur-[140px] pointer-events-none" />
        <div data-orb-2 className="absolute -bottom-40 -right-24 w-[520px] h-[520px] rounded-full bg-violet-600/15 blur-[160px] pointer-events-none" />

        <div className="relative z-10 max-w-5xl mx-auto px-6 text-center pt-24 pb-16">
          <div
            data-hero-badge
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-white/10 bg-white/5 backdrop-blur text-xs text-white/70 mb-8"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            AI email co-pilot · Gmail &amp; Outlook
          </div>

          <h1 className="font-black tracking-[-0.04em] leading-[0.92] text-5xl sm:text-7xl lg:text-8xl">
            <span data-hero-line className="block">Your inbox,</span>
            <span
              data-hero-line
              className="block bg-gradient-to-r from-indigo-400 via-violet-400 via-60% to-cyan-300 bg-clip-text text-transparent pb-2 animate-shimmer bg-[length:200%_auto]"
            >
              finally sentient.
            </span>
          </h1>

          <p data-hero-sub className="mt-7 text-lg sm:text-xl text-white/55 max-w-2xl mx-auto leading-relaxed [text-wrap:balance]">
            MailMind triages every email on five axes, extracts the promises you make,
            guards your calendar, and drafts replies in <em className="text-white/80 not-italic font-medium">your</em> voice —
            while you stay in control of every send.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              data-hero-cta
              data-magnetic
              href="#waitlist"
              className="group relative px-8 py-4 rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 font-semibold text-[15px] shadow-xl shadow-indigo-500/30 hover:shadow-indigo-500/50 transition-shadow active:scale-[0.98]"
            >
              Request early access
              <span className="inline-block ml-2 transition-transform group-hover:translate-x-1">→</span>
            </a>
            <a
              data-hero-cta
              data-magnetic
              href="#pipeline"
              className="px-8 py-4 rounded-full border border-white/15 text-white/80 font-medium text-[15px] hover:bg-white/5 hover:border-white/30 transition-colors"
            >
              See how it thinks
            </a>
          </div>

          <div className="mt-20 grid grid-cols-2 sm:grid-cols-4 gap-px rounded-2xl overflow-hidden border border-white/10 bg-white/10 max-w-3xl mx-auto">
            {STATS.map((s) => (
              <div key={s.label} data-hero-stat className="bg-[#0a0c14] px-6 py-5">
                <div className="text-2xl sm:text-3xl font-bold bg-gradient-to-br from-white to-white/60 bg-clip-text text-transparent">
                  {s.value}
                </div>
                <div className="text-[11px] uppercase tracking-widest text-white/40 mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white/30 text-xs tracking-widest animate-bounce">
          SCROLL ↓
        </div>
      </header>

      {/* ── Features ───────────────────────────────────── */}
      <section id="features" data-features className="relative py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div data-reveal className="max-w-2xl mb-16">
            <div className="text-xs uppercase tracking-[0.3em] text-indigo-400 mb-4">Capabilities</div>
            <h2 className="text-4xl sm:text-5xl font-bold tracking-[-0.03em] leading-[1.08]">
              Not another email client.
              <span className="block text-white/40">A second brain for your correspondence.</span>
            </h2>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" style={{ perspective: 1200 }}>
            {FEATURES.map((f) => (
              <div
                key={f.title}
                data-feature-card
                className="group relative rounded-2xl border border-white/8 bg-gradient-to-b from-[#0d1020] to-[#080a14] overflow-hidden will-change-transform transition-all duration-300 ease-out hover:-translate-y-3 hover:scale-[1.02] hover:border-indigo-400/50 hover:shadow-[0_24px_60px_-12px_rgba(99,102,241,0.45)] cursor-default"
              >
                {/* cursor spotlight */}
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none z-10"
                  style={{
                    background:
                      'radial-gradient(280px circle at var(--mx, 50%) var(--my, 50%), rgba(99,102,241,0.15), transparent 65%)',
                  }}
                />

                {/* email header bar */}
                <div className="flex items-center gap-3 px-5 pt-5 pb-3.5 border-b border-white/5">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500/30 to-violet-600/30 border border-indigo-400/30 flex items-center justify-center text-indigo-300 text-base shrink-0">
                    {f.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-white/90 truncate">MailMind · {f.sender}</span>
                      {/* unread dot */}
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0 group-hover:opacity-0 transition-opacity" />
                    </div>
                    <div className="text-[10px] text-white/35 font-mono tracking-wide">to: you@inbox</div>
                  </div>
                  <span className="text-[10px] text-white/30 font-mono shrink-0">{f.time}</span>
                </div>

                {/* email body */}
                <div className="px-5 py-4">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-[15px] font-bold tracking-tight">{f.title}</h3>
                  </div>
                  <p className="text-[13px] text-white/45 leading-relaxed">{f.body}</p>
                </div>

                {/* email footer: tag chip + actions appear on hover */}
                <div className="flex items-center justify-between px-5 pb-4">
                  <span className={`text-[9px] font-bold tracking-[0.15em] px-2 py-1 rounded border ${f.tagColor}`}>
                    {f.tag}
                  </span>
                  <div className="flex gap-1.5 opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300">
                    {['↩', '★', '⋯'].map((a) => (
                      <span
                        key={a}
                        className="w-6 h-6 rounded-md bg-white/5 border border-white/10 flex items-center justify-center text-[10px] text-white/60"
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                </div>

                {/* bottom glow line on hover */}
                <div className="absolute bottom-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-indigo-400/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pipeline ───────────────────────────────────── */}
      <section id="pipeline" data-pipeline className="relative py-32 px-6 bg-gradient-to-b from-transparent via-indigo-950/10 to-transparent">
        <div className="max-w-4xl mx-auto">
          <div data-reveal className="text-center mb-20">
            <div className="text-xs uppercase tracking-[0.3em] text-indigo-400 mb-4">The pipeline</div>
            <h2 className="text-4xl sm:text-5xl font-bold tracking-[-0.03em]">
              Six stages. <span className="text-white/40">Zero guesswork.</span>
            </h2>
            <p className="mt-5 text-white/50 max-w-xl mx-auto">
              Every message flows through an agentic LangGraph pipeline — deterministic where it
              should be, intelligent where it counts, human-approved where it matters.
            </p>
          </div>

          {/* ── circular wheel (desktop) ── */}
          <div
            data-pipeline-wheel
            className="relative hidden md:block mx-auto"
            style={{ width: 640, height: 640 }}
          >
            {/* rotating dashed orbit */}
            <svg
              data-pipe-ring
              className="absolute inset-0 w-full h-full"
              viewBox="0 0 640 640"
              fill="none"
            >
              <circle
                cx="320"
                cy="320"
                r="230"
                stroke="url(#ringGrad)"
                strokeWidth="1.5"
                strokeDasharray="6 10"
                opacity="0.5"
              />
              <circle cx="320" cy="320" r="290" stroke="rgba(99,102,241,0.12)" strokeWidth="1" />
              <defs>
                <linearGradient id="ringGrad" x1="0" y1="0" x2="640" y2="640">
                  <stop stopColor="#6366f1" />
                  <stop offset="0.5" stopColor="#a855f7" />
                  <stop offset="1" stopColor="#22d3ee" />
                </linearGradient>
              </defs>
            </svg>

            {/* floating envelope in the middle */}
            <div
              data-pipe-envelope
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
            >
              <div className="relative" style={{ perspective: 800 }}>
                <div className="relative w-36 h-[92px] rounded-lg bg-gradient-to-b from-[#181d36] to-[#0b0e1c] border border-indigo-400/40 shadow-[0_0_60px_rgba(99,102,241,0.5)]">
                  <svg className="absolute inset-0 w-full h-full opacity-60" viewBox="0 0 144 92" fill="none">
                    <path d="M0 0 L72 52 L144 0" stroke="#818cf8" strokeWidth="1.4" />
                    <path d="M0 92 L52 48 M144 92 L92 48" stroke="rgba(129,140,248,0.4)" strokeWidth="1" />
                  </svg>
                  <div className="absolute -right-1.5 -top-1.5 w-3.5 h-3.5 rounded-full bg-gradient-to-br from-rose-400 to-rose-600 shadow-[0_0_10px_rgba(244,63,94,0.8)]" />
                </div>
                {/* glow under envelope */}
                <div className="absolute -inset-6 rounded-full bg-indigo-500/15 blur-2xl -z-10" />
              </div>
              <div className="mt-4 text-center text-[10px] font-mono tracking-[0.3em] text-indigo-300/60">
                YOUR EMAIL
              </div>
            </div>

            {/* six nodes around the circle */}
            {PIPELINE.map((p, i) => {
              const angle = (i * 60 - 90) * (Math.PI / 180); // start at top, clockwise
              const x = 50 + 36 * Math.cos(angle);
              const y = 50 + 36 * Math.sin(angle);
              return (
                <div
                  key={p.step}
                  data-pipe-node
                  className="absolute w-44 -translate-x-1/2 -translate-y-1/2 text-center"
                  style={{ left: `${x}%`, top: `${y}%` }}
                >
                  <div className="mx-auto w-14 h-14 rounded-full border border-indigo-400/40 bg-[#0a0c14] flex items-center justify-center font-mono text-xs text-indigo-300 shadow-[0_0_30px_rgba(99,102,241,0.25)] mb-3">
                    {p.step}
                  </div>
                  <h3 className="text-base font-bold tracking-tight">{p.name}</h3>
                  <p className="text-[12px] text-white/40 mt-1 leading-snug">{p.desc}</p>
                </div>
              );
            })}
          </div>

          {/* ── vertical fallback (mobile) ── */}
          <div className="md:hidden space-y-8">
            {PIPELINE.map((p) => (
              <div key={p.step} className="flex items-start gap-4">
                <div className="w-12 h-12 shrink-0 rounded-full border border-indigo-400/40 bg-[#0a0c14] flex items-center justify-center font-mono text-xs text-indigo-300">
                  {p.step}
                </div>
                <div>
                  <h3 className="text-lg font-bold">{p.name}</h3>
                  <p className="text-sm text-white/45 mt-0.5">{p.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Security band ──────────────────────────────── */}
      <section id="security" className="relative py-28 px-6">
        <div data-reveal className="max-w-5xl mx-auto rounded-3xl border border-white/10 bg-gradient-to-br from-white/[0.04] to-transparent p-10 sm:p-16 overflow-hidden relative">
          <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full bg-cyan-500/10 blur-[100px] pointer-events-none" />
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <div className="text-xs uppercase tracking-[0.3em] text-cyan-400 mb-4">Trust &amp; safety</div>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight leading-tight">
                Your mail never trains anyone else&rsquo;s model.
              </h2>
              <p className="mt-5 text-white/50 leading-relaxed">
                PII is masked before any LLM call. Retrieval indexes are isolated per account.
                Sessions are HttpOnly-cookie scoped, drafts require explicit approval, and a full
                audit log records every action taken on your behalf.
              </p>
            </div>
            <ul className="space-y-4">
              {[
                'PII masking before indexing & inference',
                'Per-account RAG + Tone DNA isolation',
                'Human-in-the-loop approval gate on every send',
                '90-day data retention with full audit trail',
              ].map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm text-white/70">
                  <span className="mt-0.5 w-5 h-5 rounded-full bg-emerald-500/15 border border-emerald-400/30 text-emerald-300 flex items-center justify-center text-[10px] shrink-0">
                    ✓
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Final CTA / Waitlist ───────────────────────── */}
      <section id="waitlist" className="relative scroll-mt-20 py-36 px-6 text-center overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.15),transparent_60%)] pointer-events-none" />
        <div data-final-cta className="relative max-w-3xl mx-auto">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs text-white/70 backdrop-blur">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-400" />
            Private beta · Limited spots
          </div>
          <h2 className="text-5xl sm:text-6xl font-black tracking-[-0.04em] leading-[1.0]">
            Stop managing email.
            <span className="block bg-gradient-to-r from-indigo-400 to-cyan-300 bg-clip-text text-transparent pb-2">
              Start commanding it.
            </span>
          </h2>
          <p className="mt-6 mb-10 text-white/50 text-lg">
            MailMind is invite-only while we onboard our first users. Request early access and
            we&apos;ll reach out when your spot opens up.
          </p>
          <WaitlistForm />
          <div className="mt-6 text-xs text-white/30">
            Already approved?{' '}
            <Link href="/login" className="font-medium text-white/60 underline-offset-2 hover:underline">
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────── */}
      <footer className="border-t border-white/5 px-6 py-10">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-white/35">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center font-black text-[10px] text-white">
              M
            </div>
            MailMind — AI email co-pilot
          </div>
          <div className="flex items-center gap-6">
            <a href="#features" className="hover:text-white/70 transition-colors">Features</a>
            <a href="#pipeline" className="hover:text-white/70 transition-colors">Pipeline</a>
            <a href="#security" className="hover:text-white/70 transition-colors">Security</a>
            <Link href="/privacy" className="hover:text-white/70 transition-colors">Privacy</Link>
            <Link href="/terms" className="hover:text-white/70 transition-colors">Terms</Link>
            <Link href="/login" className="hover:text-white/70 transition-colors">Sign in</Link>
          </div>
          <div>© {new Date().getFullYear()} Radiants</div>
        </div>
      </footer>
    </div>
  );
}
