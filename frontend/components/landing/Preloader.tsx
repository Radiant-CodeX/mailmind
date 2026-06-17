'use client';

import { useEffect, useRef } from 'react';
import gsap from 'gsap';

interface PreloaderProps {
  onDone: () => void;
}

// The MailMind monogram — three slashes forming an "M".
// Geometry verbatim from public/mailmind-logo.svg, matched to the video's
// SceneLogo reveal (staggered slide-up + gradient + shimmer + bloom).
const SLASHES = [
  'M217.139 198.5L128.997 352.993L99.0771 301L158.289 198.5H217.139Z',
  'M293.132 198.5L241.503 287.497L212.078 236.004L234.285 198.5H293.132Z',
  'M399.139 150.5L310.994 304.999L280.578 252.999L340.287 150.5H399.139Z',
];

/**
 * Brand intro loader — the same logo-reveal used for the launch video's
 * SceneLogo: the "M" mark draws in slash-by-slash with a gradient bloom and a
 * shimmer sweep, the wordmark and tagline rise in, then the stage splits open.
 */
export function Preloader({ onDone }: PreloaderProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        defaults: { ease: 'power3.out' },
        onComplete: onDone,
      });

      tl
        // halo plate blooms in
        .fromTo('[data-pl-halo]', { scale: 0.5, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.6 })
        // the M reveals slash-by-slash, each sliding up + scaling in
        .fromTo(
          '[data-pl-slash]',
          { y: 60, scale: 0.82, opacity: 0, transformOrigin: '250px 270px' },
          { y: 0, scale: 1, opacity: 1, duration: 0.62, stagger: 0.13 },
          '-=0.35',
        )
        // whole mark pops with a spring-like overshoot
        .fromTo(
          '[data-pl-logo]',
          { scale: 0.85 },
          { scale: 1, duration: 0.55, ease: 'back.out(1.7)' },
          '-=0.5',
        )
        // wordmark rises in
        .fromTo(
          '[data-pl-word]',
          { y: 22, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.5 },
          '-=0.15',
        )
        // tagline rises in
        .fromTo(
          '[data-pl-tag]',
          { y: 14, opacity: 0 },
          { y: 0, opacity: 1, duration: 0.45 },
          '-=0.25',
        )
        // brief beat to let it breathe
        .to({}, { duration: 0.45 })
        // exit: stage lifts away, then the panels split open like an envelope
        .to('[data-pl-stage]', { y: -50, opacity: 0, duration: 0.45, ease: 'power2.in' })
        .to('[data-pl-top]', { yPercent: -100, duration: 0.75, ease: 'power4.inOut' }, '-=0.1')
        .to('[data-pl-bottom]', { yPercent: 100, duration: 0.75, ease: 'power4.inOut' }, '<');

      // Continuous shimmer sweep across the mark (matches the video).
      const shimmer = rootRef.current?.querySelector('[data-pl-shimmer]');
      if (shimmer) {
        gsap.fromTo(
          shimmer,
          { attr: { x1: -260, x2: -100 } },
          { attr: { x1: 760, x2: 920 }, duration: 1.8, ease: 'none', repeat: -1 },
        );
      }

      // Gentle idle pulse on the mark while everything settles.
      gsap.to('[data-pl-logo]', {
        scale: 1.03,
        duration: 1.1,
        ease: 'sine.inOut',
        yoyo: true,
        repeat: -1,
        delay: 1.2,
      });
    }, rootRef);

    return () => ctx.revert();
  }, [onDone]);

  return (
    <div ref={rootRef} className="fixed inset-0 z-[100] pointer-events-none font-sans">
      {/* split panels */}
      <div data-pl-top className="absolute inset-x-0 top-0 h-1/2 bg-[#05060a]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(124,92,255,0.10),transparent_60%)]" />
      </div>
      <div data-pl-bottom className="absolute inset-x-0 bottom-0 h-1/2 bg-[#05060a]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,92,255,0.10),transparent_60%)]" />
      </div>

      {/* stage */}
      <div data-pl-stage className="absolute inset-0 flex flex-col items-center justify-center gap-7">
        {/* logo mark */}
        <div className="relative flex items-center justify-center">
          {/* soft halo behind the mark */}
          <div
            data-pl-halo
            className="absolute w-[260px] h-[260px] rounded-full bg-[#7c5cff] opacity-0 blur-[60px]"
          />
          <svg
            data-pl-logo
            width={190}
            height={190}
            viewBox="0 0 500 500"
            style={{
              overflow: 'visible',
              filter:
                'drop-shadow(0 0 34px rgba(124,92,255,0.8)) drop-shadow(0 0 12px rgba(56,224,224,0.55))',
            }}
          >
            <defs>
              <linearGradient id="pl-fill" x1="80" y1="350" x2="400" y2="150" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#38e0e0" />
                <stop offset="50%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
              <linearGradient
                data-pl-shimmer
                id="pl-shimmer"
                gradientUnits="userSpaceOnUse"
                x1="-260"
                y1="0"
                x2="-100"
                y2="500"
              >
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
                <stop offset="50%" stopColor="#ffffff" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
              </linearGradient>
            </defs>

            {SLASHES.map((d, i) => (
              <g key={i} data-pl-slash>
                <path d={d} fill="url(#pl-fill)" />
                {/* shimmer pass clipped to the slash */}
                <path d={d} fill="url(#pl-shimmer)" style={{ mixBlendMode: 'screen' }} />
                {/* crisp inner edge light */}
                <path d={d} fill="none" stroke="#ffffff" strokeOpacity={0.25} strokeWidth={1.5} />
              </g>
            ))}
          </svg>
        </div>

        {/* wordmark */}
        <div
          data-pl-word
          style={{
            fontFamily: 'var(--font-space), system-ui, sans-serif',
            fontSize: 52,
            fontWeight: 700,
            letterSpacing: -1,
            background: 'linear-gradient(90deg, #f4f6ff, #a78bfa)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
            textShadow: '0 0 40px rgba(124,92,255,0.25)',
          }}
        >
          MailMind
        </div>

        {/* tagline */}
        <div
          data-pl-tag
          className="text-[11px] font-medium text-[#8a90b0]"
          style={{ fontFamily: 'var(--font-space), system-ui, sans-serif', letterSpacing: '0.4em' }}
        >
          THE INTELLIGENT EMAIL CO-PILOT
        </div>
      </div>
    </div>
  );
}
