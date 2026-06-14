import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS } from "../theme";

// Living aurora background: two slow-drifting radial glows over a deep navy
// base, a faint grid, and a vignette. Everything is frame-driven.
export const Background: React.FC<{ intensity?: number }> = ({
  intensity = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const ax = width * (0.32 + 0.06 * Math.sin(t * 0.5));
  const ay = height * (0.36 + 0.05 * Math.cos(t * 0.42));
  const bx = width * (0.72 + 0.05 * Math.cos(t * 0.37));
  const by = height * (0.7 + 0.06 * Math.sin(t * 0.46));

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg0 }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${ax}px ${ay}px, ${COLORS.violetDeep}${alpha(
            0.28 * intensity,
          )}, transparent 42%), radial-gradient(circle at ${bx}px ${by}px, ${
            COLORS.cyan
          }${alpha(0.16 * intensity)}, transparent 46%)`,
          filter: "blur(8px)",
        }}
      />
      {/* Fine grid */}
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${COLORS.indigo}10 1px, transparent 1px), linear-gradient(90deg, ${COLORS.indigo}10 1px, transparent 1px)`,
          backgroundSize: "64px 64px",
          opacity: 0.35,
          maskImage:
            "radial-gradient(circle at 50% 45%, black 10%, transparent 75%)",
        }}
      />
      {/* Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 50% 50%, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

// 0..1 -> two-digit hex alpha suffix for hex colors.
const alpha = (v: number) => {
  const c = Math.max(0, Math.min(255, Math.round(v * 255)));
  return c.toString(16).padStart(2, "0");
};
