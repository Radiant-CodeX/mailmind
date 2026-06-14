import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { EmailCard } from "../components/EmailCard";
import { COLORS, FONT } from "../theme";

const NOISE = [
  { sender: "LinkedIn", subject: "You appeared in 9 searches this week" },
  { sender: "Jira", subject: "MM-482 was assigned to you" },
  { sender: "Slack", subject: "3 unread mentions in #release" },
  { sender: "Finance", subject: "Q3 reconciliation — action required" },
  { sender: "Calendar", subject: "Invite: Roadmap sync at 4:00 PM" },
  { sender: "GitHub", subject: "[PR #1184] review requested" },
  { sender: "Notion", subject: "Weekly digest of your workspace" },
  { sender: "Stripe", subject: "A payment of $4,200 succeeded" },
  { sender: "Zoom", subject: "Your meeting recording is ready" },
  { sender: "AWS", subject: "Your monthly cost report is available" },
  { sender: "Figma", subject: "Dana left 12 comments on Flow v3" },
  { sender: "Support", subject: "Ticket #88213 escalated to you" },
];

export const SceneIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();

  // Headline appears, then the storm of email fades up behind it.
  const headIn = spring({ frame: frame - 8, fps, config: { damping: 200 } });
  const stormIn = interpolate(frame, [10, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Everything pulls toward the exit at the end of the scene.
  const exit = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp" },
  );

  return (
    <AbsoluteFill>
      <Background intensity={0.7} />

      {/* The storm */}
      <AbsoluteFill style={{ opacity: stormIn * (1 - exit) }}>
        {NOISE.map((m, i) => {
          const seed = i + 1;
          const x = random(`x${seed}`) * (width - 480);
          const y = random(`y${seed}`) * (height - 120);
          const rot = (random(`r${seed}`) - 0.5) * 10;
          const delay = i * 3;
          const rise = spring({
            frame: frame - 12 - delay,
            fps,
            config: { damping: 18, mass: 0.8 },
          });
          const drift = Math.sin((frame + i * 30) / 28) * 6;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: x,
                top: y,
                transform: `translateY(${(1 - rise) * 40 + drift}px) rotate(${rot}deg) scale(${0.8 + rise * 0.2})`,
                opacity: 0.5 * rise,
                filter: "saturate(0.6)",
              }}
            >
              <EmailCard
                sender={m.sender}
                subject={m.subject}
                width={420}
                accent={COLORS.inkFaint}
              />
            </div>
          );
        })}
      </AbsoluteFill>

      {/* Darkening so the headline reads */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 50% 50%, rgba(5,6,10,0.82) 0%, rgba(5,6,10,0.5) 60%, transparent 100%)",
        }}
      />

      {/* Headline */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          opacity: headIn * (1 - exit),
          transform: `translateY(${(1 - headIn) * 24 - exit * 30}px)`,
        }}
      >
        <div style={{ textAlign: "center", fontFamily: FONT }}>
          <div
            style={{
              fontSize: 30,
              letterSpacing: 8,
              color: COLORS.cyan,
              fontWeight: 500,
              marginBottom: 18,
            }}
          >
            EVERY DAY, 121 EMAILS
          </div>
          <div
            style={{
              fontSize: 92,
              fontWeight: 700,
              color: COLORS.ink,
              lineHeight: 1.05,
            }}
          >
            Your inbox is
            <br />
            <span style={{ color: COLORS.inkDim }}>winning.</span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
