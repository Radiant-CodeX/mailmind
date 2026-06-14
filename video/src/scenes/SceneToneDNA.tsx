import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { COLORS, FONT } from "../theme";

const DRAFT =
  "Hi Priya — thanks for the nudge. I'll have the revised deck over to you by Thursday EOD, with the Q3 numbers baked in. Quick call Friday to lock it? Best, Alex";

export const SceneToneDNA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const panelIn = spring({ frame: frame - 4, fps, config: { damping: 200 } });
  const exit = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );

  // Typewriter via string slicing (never per-char opacity).
  const start = 24;
  const cps = 1.45; // characters per frame
  const charCount = Math.max(0, Math.floor((frame - start) * cps));
  const shown = DRAFT.slice(0, charCount);
  const typing = charCount < DRAFT.length;
  const cursorOn = Math.floor(frame / 8) % 2 === 0;

  const headIn = spring({ frame: frame - 2, fps, config: { damping: 200 } });

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      <Background intensity={0.7} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 40,
        }}
      >
        <div
          style={{
            fontFamily: FONT,
            textAlign: "center",
            opacity: headIn,
            transform: `translateY(${(1 - headIn) * 16}px)`,
          }}
        >
          <div
            style={{
              fontSize: 22,
              letterSpacing: 6,
              color: COLORS.violet,
              fontWeight: 600,
              marginBottom: 12,
            }}
          >
            TONE DNA
          </div>
          <div style={{ fontSize: 58, fontWeight: 700, color: COLORS.ink }}>
            Drafts that sound like you.
          </div>
        </div>

        {/* Compose window */}
        <div
          style={{
            width: 1100,
            borderRadius: 22,
            background:
              "linear-gradient(180deg, rgba(18,22,40,0.96), rgba(10,13,26,0.96))",
            border: `1px solid ${COLORS.violet}30`,
            boxShadow: `0 40px 90px -40px ${COLORS.violetDeep}80`,
            overflow: "hidden",
            opacity: panelIn,
            transform: `translateY(${(1 - panelIn) * 30}px) scale(${0.96 + panelIn * 0.04})`,
            fontFamily: FONT,
          }}
        >
          {/* Title bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "16px 22px",
              borderBottom: `1px solid ${COLORS.indigo}1f`,
            }}
          >
            <Dot c={COLORS.rose} />
            <Dot c={COLORS.amber} />
            <Dot c={COLORS.emerald} />
            <span
              style={{
                marginLeft: 14,
                color: COLORS.inkDim,
                fontSize: 16,
              }}
            >
              Re: Q3 deck review
            </span>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: 1,
                color: COLORS.violet,
                border: `1px solid ${COLORS.violet}55`,
                background: `${COLORS.violet}18`,
                padding: "5px 12px",
                borderRadius: 999,
              }}
            >
              {typing ? "✦ WRITING IN YOUR VOICE" : "✓ MATCHES YOUR STYLE"}
            </span>
          </div>

          {/* Body */}
          <div
            style={{
              padding: "30px 34px 38px",
              minHeight: 230,
              fontSize: 30,
              lineHeight: 1.55,
              color: COLORS.ink,
              fontWeight: 400,
            }}
          >
            {shown}
            <span
              style={{
                opacity: cursorOn ? 1 : 0,
                color: COLORS.violet,
                fontWeight: 700,
              }}
            >
              |
            </span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Dot: React.FC<{ c: string }> = ({ c }) => (
  <div style={{ width: 13, height: 13, borderRadius: 13, background: c }} />
);
