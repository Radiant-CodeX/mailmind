import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { COLORS } from "../theme";

// The real MailMind monogram: three slashes forming an "M".
// Geometry taken verbatim from frontend/public/mailmind-logo.svg, then
// enhanced with a brand gradient, bloom, staggered reveal and a shimmer sweep.
const SLASHES = [
  "M217.139 198.5L128.997 352.993L99.0771 301L158.289 198.5H217.139Z",
  "M293.132 198.5L241.503 287.497L212.078 236.004L234.285 198.5H293.132Z",
  "M399.139 150.5L310.994 304.999L280.578 252.999L340.287 150.5H399.139Z",
];

export const LogoMark: React.FC<{
  size?: number;
  draw?: number; // 0..1 reveal progress
  glow?: number; // bloom multiplier
}> = ({ size = 160, draw = 1, glow = 1 }) => {
  const frame = useCurrentFrame();
  // Shimmer highlight travels across the mark.
  const shimmer = interpolate(frame % 90, [0, 90], [-260, 760]);

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 500 500"
      style={{
        filter: `drop-shadow(0 0 ${26 * glow}px ${COLORS.violetDeep}cc) drop-shadow(0 0 ${
          10 * glow
        }px ${COLORS.cyan}88)`,
        overflow: "visible",
      }}
    >
      <defs>
        <linearGradient id="mm-fill" x1="80" y1="350" x2="400" y2="150" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={COLORS.cyan} />
          <stop offset="50%" stopColor={COLORS.indigo} />
          <stop offset="100%" stopColor={COLORS.violet} />
        </linearGradient>
        <linearGradient
          id="mm-shimmer"
          gradientUnits="userSpaceOnUse"
          x1={shimmer}
          y1="0"
          x2={shimmer + 160}
          y2="500"
        >
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>
        <filter id="mm-soft" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>

      {/* Soft halo plate behind the mark */}
      <circle
        cx="250"
        cy="250"
        r="150"
        fill={COLORS.violetDeep}
        opacity={0.1 * glow}
        style={{ filter: "blur(30px)" }}
      />

      {SLASHES.map((d, i) => {
        // Stagger each slash in, sliding up from below with a slight scale.
        const p = interpolate(draw, [i * 0.16, i * 0.16 + 0.55], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const cx = 250;
        const cy = 270;
        return (
          <g
            key={i}
            style={{
              opacity: p,
              transform: `translateY(${(1 - p) * 60}px) scale(${0.82 + p * 0.18})`,
              transformOrigin: `${cx}px ${cy}px`,
            }}
          >
            <path d={d} fill="url(#mm-fill)" />
            {/* shimmer pass on top, clipped to the slash */}
            <path d={d} fill="url(#mm-shimmer)" style={{ mixBlendMode: "screen" }} />
            {/* crisp inner edge light */}
            <path
              d={d}
              fill="none"
              stroke="#ffffff"
              strokeOpacity={0.25}
              strokeWidth={1.5}
            />
          </g>
        );
      })}
    </svg>
  );
};
