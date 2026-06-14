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

const FEATURES = [
  {
    icon: "◎",
    title: "5-Axis Triage",
    body: "Every email scored by what actually matters.",
    color: COLORS.rose,
  },
  {
    icon: "✦",
    title: "Tone DNA",
    body: "Replies written in your own voice.",
    color: COLORS.violet,
  },
  {
    icon: "◈",
    title: "Precedent Recall",
    body: "Your past decisions, retrieved as context.",
    color: COLORS.indigo,
  },
  {
    icon: "✓",
    title: "Commitment Tracker",
    body: "Promises become tracked, dated tasks.",
    color: COLORS.amber,
  },
  {
    icon: "◷",
    title: "Calendar Radar",
    body: "Conflicts flagged before you hit send.",
    color: COLORS.cyan,
  },
  {
    icon: "⬡",
    title: "One Workspace",
    body: "Gmail + Outlook, every inbox, one mind.",
    color: COLORS.emerald,
  },
];

export const SceneFeatures: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const headIn = spring({ frame: frame - 4, fps, config: { damping: 200 } });
  const exit = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      <Background intensity={0.85} />
      <AbsoluteFill style={{ padding: "90px 130px", justifyContent: "center" }}>
        <div
          style={{
            fontFamily: FONT,
            marginBottom: 48,
            opacity: headIn,
            transform: `translateY(${(1 - headIn) * 16}px)`,
          }}
        >
          <div
            style={{
              fontSize: 22,
              letterSpacing: 6,
              color: COLORS.cyan,
              fontWeight: 600,
              marginBottom: 10,
            }}
          >
            ONE CO-PILOT, EVERY STEP
          </div>
          <div style={{ fontSize: 58, fontWeight: 700, color: COLORS.ink }}>
            Built for the whole inbox.
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 26,
          }}
        >
          {FEATURES.map((f, i) => {
            const delay = 12 + i * 6;
            const s = spring({
              frame: frame - delay,
              fps,
              config: { damping: 18, mass: 0.7 },
            });
            return (
              <div
                key={f.title}
                style={{
                  opacity: s,
                  transform: `translateY(${(1 - s) * 34}px)`,
                  padding: "30px 30px 34px",
                  borderRadius: 22,
                  background:
                    "linear-gradient(180deg, rgba(20,24,42,0.9), rgba(11,14,28,0.9))",
                  border: `1px solid ${f.color}33`,
                  boxShadow: `0 26px 60px -36px ${f.color}66`,
                  fontFamily: FONT,
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 18,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 30,
                    color: f.color,
                    background: `${f.color}1c`,
                    border: `1px solid ${f.color}44`,
                    boxShadow: `0 0 24px ${f.color}40`,
                    marginBottom: 22,
                  }}
                >
                  {f.icon}
                </div>
                <div
                  style={{
                    fontSize: 30,
                    fontWeight: 700,
                    color: COLORS.ink,
                    marginBottom: 10,
                  }}
                >
                  {f.title}
                </div>
                <div
                  style={{ fontSize: 20, color: COLORS.inkDim, lineHeight: 1.45 }}
                >
                  {f.body}
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
