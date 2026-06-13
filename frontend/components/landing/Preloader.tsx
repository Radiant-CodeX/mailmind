'use client';

import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';

interface PreloaderProps {
  onDone: () => void;
}

const STATUS_STEPS = [
  'CONNECTING TO INBOX',
  'RECEIVING MESSAGE',
  'PARSING TONE DNA',
  'READY',
];

/**
 * Email-themed intro loader.
 * Stacking order is the whole trick here:
 *   opened flap (z:0)  <  letter (z:1)  <  envelope body (z:2)  <  closed flap (z:3)
 * The letter starts hidden *inside* the body; when it slides up, only the part
 * above the envelope's top edge is visible — exactly like real mail.
 */
export function Preloader({ onDone }: PreloaderProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [progress, setProgress] = useState(0);
  const [statusIdx, setStatusIdx] = useState(0);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const counter = { v: 0 };

      const tl = gsap.timeline({
        defaults: { ease: 'power3.out' },
        onComplete: onDone,
      });

      tl
        // ── paper plane streaks in ──────────────────────────────
        .fromTo(
          '[data-pl-plane]',
          { x: '-55vw', y: '20vh', rotate: 24, opacity: 0, scale: 0.5 },
          { x: 0, y: 0, rotate: 0, opacity: 1, scale: 1, duration: 0.85, ease: 'power2.inOut' },
        )
        .fromTo(
          '[data-pl-trail]',
          { scaleX: 1, opacity: 0.6 },
          { scaleX: 0, opacity: 0, transformOrigin: 'right center', duration: 0.45 },
          '<0.25',
        )
        .call(() => setStatusIdx(1))
        // plane folds away → envelope pops in with a shockwave ring
        .to('[data-pl-plane]', { scale: 0, rotate: -40, duration: 0.3, ease: 'back.in(2.5)' })
        .fromTo(
          '[data-pl-envelope]',
          { scale: 0, rotate: 6 },
          { scale: 1, rotate: 0, duration: 0.55, ease: 'back.out(1.7)' },
          '-=0.05',
        )
        .fromTo(
          '[data-pl-ring]',
          { scale: 0.4, opacity: 0.7 },
          { scale: 2.2, opacity: 0, duration: 0.9, ease: 'power2.out' },
          '<',
        )
        // ── flap opens, then drops BEHIND the body ──────────────
        .to('[data-pl-flap]', {
          rotateX: 178,
          duration: 0.6,
          ease: 'power2.inOut',
          transformOrigin: 'top center',
        })
        .set('[data-pl-flap]', { zIndex: 0 }) // opened flap now sits behind everything
        .call(() => setStatusIdx(2))
        // ── letter rises out of the envelope ────────────────────
        .fromTo(
          '[data-pl-letter]',
          { y: 10, opacity: 1 },
          { y: -118, duration: 0.9, ease: 'power3.inOut' },
        )
        .fromTo(
          '[data-pl-letter-inner]',
          { opacity: 0, y: 8 },
          { opacity: 1, y: 0, duration: 0.45, stagger: 0.08 },
          '-=0.4',
        )
        // ── progress fills like a download ──────────────────────
        .fromTo(
          '[data-pl-bar]',
          { scaleX: 0 },
          { scaleX: 1, transformOrigin: 'left center', duration: 1.0, ease: 'power1.inOut' },
          '-=0.5',
        )
        .to(
          counter,
          {
            v: 100,
            duration: 1.0,
            ease: 'power1.inOut',
            onUpdate: () => setProgress(Math.round(counter.v)),
          },
          '<',
        )
        .call(() => setStatusIdx(3))
        // ── exit: stage lifts, panels split like an opening envelope ──
        .to('[data-pl-stage]', { y: -50, opacity: 0, duration: 0.45, ease: 'power2.in' }, '+=0.25')
        .to('[data-pl-top]', { yPercent: -100, duration: 0.75, ease: 'power4.inOut' }, '-=0.1')
        .to('[data-pl-bottom]', { yPercent: 100, duration: 0.75, ease: 'power4.inOut' }, '<');

      /* ambient floating dust */
      gsap.utils.toArray<HTMLElement>('[data-pl-dust]').forEach((d, i) => {
        gsap.to(d, {
          y: -30 - Math.random() * 50,
          x: (Math.random() - 0.5) * 40,
          opacity: 0,
          duration: 2.5 + Math.random() * 2,
          repeat: -1,
          delay: i * 0.4,
          ease: 'none',
        });
      });
    }, rootRef);

    return () => ctx.revert();
  }, [onDone]);

  return (
    <div ref={rootRef} className="fixed inset-0 z-[100] pointer-events-none font-sans">
      {/* split panels */}
      <div data-pl-top className="absolute inset-x-0 top-0 h-1/2 bg-[#05060a]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(99,102,241,0.08),transparent_60%)]" />
      </div>
      <div data-pl-bottom className="absolute inset-x-0 bottom-0 h-1/2 bg-[#05060a]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.08),transparent_60%)]" />
      </div>

      {/* stage */}
      <div data-pl-stage className="absolute inset-0 flex flex-col items-center justify-center">
        {/* ambient dust — each particle suppressHydrationWarning since positions are cosmetic + randomized */}
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            data-pl-dust
            className="absolute w-1 h-1 rounded-full bg-indigo-400/50"
            suppressHydrationWarning
            style={{
              left: `${30 + Math.random() * 40}%`,
              top: `${40 + Math.random() * 25}%`,
            }}
          />
        ))}

        {/* paper plane */}
        <div data-pl-plane className="absolute opacity-0">
          <div data-pl-trail className="absolute right-full top-1/2 w-[38vw] h-px bg-gradient-to-l from-indigo-400/90 via-violet-400/40 to-transparent" />
          <svg width="68" height="68" viewBox="0 0 24 24" fill="none" className="drop-shadow-[0_0_28px_rgba(99,102,241,0.9)]">
            <path d="M2 12 L22 3 L15 21 L11 13.5 Z" fill="url(#plGrad)" stroke="#a5b4fc" strokeWidth="0.6" strokeLinejoin="round" />
            <path d="M22 3 L11 13.5" stroke="#c7d2fe" strokeWidth="0.6" />
            <defs>
              <linearGradient id="plGrad" x1="2" y1="3" x2="22" y2="21">
                <stop stopColor="#6366f1" />
                <stop offset="1" stopColor="#a855f7" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* envelope assembly */}
        <div data-pl-envelope className="relative scale-0" style={{ perspective: 1000 }}>
          {/* shockwave ring */}
          <div
            data-pl-ring
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 rounded-full border border-indigo-400/60 opacity-0"
          />

          {/* letter — z:1, between opened flap (0) and body (2) */}
          <div
            data-pl-letter
            className="absolute left-1/2 -translate-x-1/2 top-1 w-44 h-32 rounded-lg bg-gradient-to-b from-white via-slate-50 to-indigo-100 shadow-[0_-8px_40px_rgba(99,102,241,0.45)] flex flex-col items-center justify-center gap-2.5 px-4"
            style={{ zIndex: 1 }}
          >
            <div data-pl-letter-inner className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center font-black text-white text-lg shadow-lg shadow-indigo-500/50">
              M
            </div>
            <div data-pl-letter-inner className="text-[13px] font-extrabold tracking-[0.3em] text-slate-800 leading-none">
              MAILMIND
            </div>
            <div data-pl-letter-inner className="text-[8px] font-semibold tracking-[0.28em] text-indigo-500/80 leading-none">
              AI EMAIL CO-PILOT
            </div>
            {/* faux text lines */}
            <div data-pl-letter-inner className="w-full space-y-1 mt-0.5">
              <div className="h-[3px] rounded-full bg-slate-300/80 w-full" />
              <div className="h-[3px] rounded-full bg-slate-300/60 w-4/5 mx-auto" />
              <div className="h-[3px] rounded-full bg-slate-300/40 w-3/5 mx-auto" />
            </div>
          </div>

          {/* body — z:2, hides the lower part of the letter */}
          <div
            className="relative w-60 h-[150px] rounded-xl bg-gradient-to-b from-[#181d36] to-[#0b0e1c] border border-indigo-400/40 shadow-[0_0_70px_rgba(99,102,241,0.4),inset_0_1px_0_rgba(165,180,252,0.15)]"
            style={{ zIndex: 2 }}
          >
            {/* inner V fold */}
            <svg className="absolute inset-0 w-full h-full opacity-50" viewBox="0 0 240 150" fill="none">
              <path d="M0 150 L120 62 L240 150" stroke="url(#vGrad)" strokeWidth="1.4" />
              <defs>
                <linearGradient id="vGrad" x1="0" y1="150" x2="240" y2="150">
                  <stop stopColor="#6366f1" stopOpacity="0.4" />
                  <stop offset="0.5" stopColor="#a78bfa" />
                  <stop offset="1" stopColor="#6366f1" stopOpacity="0.4" />
                </linearGradient>
              </defs>
            </svg>
            {/* wax-seal style notification dot */}
            <div className="absolute -right-1.5 -top-1.5 w-4 h-4 rounded-full bg-gradient-to-br from-rose-400 to-rose-600 shadow-[0_0_12px_rgba(244,63,94,0.8)] border border-rose-300/50" />
          </div>

          {/* flap — z:3 closed; dropped to z:0 by the timeline once opened */}
          <div
            data-pl-flap
            className="absolute inset-x-0 top-0 h-[76px]"
            style={{
              zIndex: 3,
              transformStyle: 'preserve-3d',
              backfaceVisibility: 'visible',
              clipPath: 'polygon(0 0, 100% 0, 50% 100%)',
              background: 'linear-gradient(180deg, #2a3158 0%, #161a31 100%)',
              borderTop: '1px solid rgba(165,180,252,0.6)',
            }}
          />
        </div>

        {/* status + progress */}
        <div className="absolute bottom-[20vh] flex flex-col items-center gap-4 w-72">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-mono font-medium tracking-[0.25em] text-indigo-200/80">
                {STATUS_STEPS[statusIdx]}
                <span className="animate-pulse">…</span>
              </span>
            </div>
            <span className="text-[11px] font-mono font-bold tracking-wider text-white/90 tabular-nums">
              {progress}%
            </span>
          </div>
          <div className="w-full h-[3px] rounded-full bg-white/8 overflow-hidden">
            <div data-pl-bar className="h-full w-full rounded-full bg-gradient-to-r from-indigo-500 via-violet-500 to-cyan-400 scale-x-0 shadow-[0_0_12px_rgba(139,92,246,0.8)]" />
          </div>
          <div className="text-[9px] font-mono tracking-[0.4em] text-white/25 uppercase">
            MailMind · Secure Channel
          </div>
        </div>
      </div>
    </div>
  );
}
