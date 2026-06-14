import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { COLORS, FONT, MONO } from "../theme";

const AXES = [
  { label: "Deadline proximity", value: 0.92, color: COLORS.rose },
  { label: "Sender authority", value: 0.78, color: COLORS.amber },
  { label: "Sentiment urgency", value: 0.64, color: COLORS.violet },
  { label: "Thread decay", value: 0.41, color: COLORS.indigo },
  { label: "Action type", value: 0.85, color: COLORS.cyan },
];

const SectionHeading: React.FC<{ kicker: string; title: string; o: number }> = ({
  kicker,
  title,
  o,
}) => (
  <div style={{ fontFamily: FONT, opacity: o }}>
    <div
      style={{
        fontSize: 22,
        letterSpacing: 6,
        color: COLORS.cyan,
        fontWeight: 600,
        marginBottom: 10,
      }}
    >
      {kicker}
    </div>
    <div style={{ fontSize: 58, fontWeight: 700, color: COLORS.ink }}>
      {title}
    </div>
  </div>
);

export const SceneTriage: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const headIn = spring({ frame: frame - 6, fps, config: { damping: 200 } });
  const exit = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );

  // Composite score counts up as the bars fill.
  const scoreProg = interpolate(frame, [30, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const score = Math.round(scoreProg * 94);

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      <Background intensity={0.8} />
      <AbsoluteFill
        style={{
          padding: "0 130px",
          justifyContent: "center",
          gap: 56,
        }}
      >
        <SectionHeading
          kicker="EXPLAINABLE TRIAGE"
          title="Five axes. One honest score."
          o={headIn}
        />

        <div style={{ display: "flex", gap: 70, alignItems: "center" }}>
          {/* Bars */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              gap: 22,
            }}
          >
            {AXES.map((a, i) => {
              const delay = 18 + i * 7;
              const fill = spring({
                frame: frame - delay,
                fps,
                config: { damping: 16, mass: 0.7 },
              });
              const w = a.value * fill;
              return (
                <div key={a.label} style={{ fontFamily: FONT }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 8,
                    }}
                  >
                    <span
                      style={{ color: COLORS.inkDim, fontSize: 22, fontWeight: 500 }}
                    >
                      {a.label}
                    </span>
                    <span
                      style={{
                        color: a.color,
                        fontFamily: MONO,
                        fontSize: 20,
                      }}
                    >
                      {Math.round(w * 100)}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 14,
                      borderRadius: 999,
                      background: "rgba(255,255,255,0.06)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${w * 100}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: `linear-gradient(90deg, ${a.color}99, ${a.color})`,
                        boxShadow: `0 0 16px ${a.color}aa`,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Composite score dial */}
          <ScoreDial score={score} progress={scoreProg} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const ScoreDial: React.FC<{ score: number; progress: number }> = ({
  score,
  progress,
}) => {
  const R = 130;
  const C = 2 * Math.PI * R;
  return (
    <div
      style={{
        width: 320,
        height: 320,
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <svg width={320} height={320} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={160}
          cy={160}
          r={R}
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          strokeWidth={18}
        />
        <circle
          cx={160}
          cy={160}
          r={R}
          fill="none"
          stroke="url(#dial)"
          strokeWidth={18}
          strokeLinecap="round"
          strokeDasharray={C}
          strokeDashoffset={C * (1 - progress * 0.94)}
          style={{ filter: `drop-shadow(0 0 12px ${COLORS.rose})` }}
        />
        <defs>
          <linearGradient id="dial" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={COLORS.cyan} />
            <stop offset="60%" stopColor={COLORS.violet} />
            <stop offset="100%" stopColor={COLORS.rose} />
          </linearGradient>
        </defs>
      </svg>
      <div
        style={{
          position: "absolute",
          textAlign: "center",
          fontFamily: FONT,
        }}
      >
        <div
          style={{
            fontSize: 96,
            fontWeight: 700,
            color: COLORS.ink,
            lineHeight: 1,
            fontFamily: MONO,
          }}
        >
          {score}
        </div>
        <div
          style={{
            fontSize: 20,
            letterSpacing: 3,
            color: COLORS.rose,
            fontWeight: 600,
            marginTop: 6,
          }}
        >
          CRITICAL
        </div>
      </div>
    </div>
  );
};
