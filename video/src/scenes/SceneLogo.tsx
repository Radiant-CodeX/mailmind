import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { LogoMark } from "../components/Logo";
import { COLORS, FONT } from "../theme";

export const SceneLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const draw = interpolate(frame, [6, 48], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const pop = spring({ frame: frame - 30, fps, config: { damping: 14 } });
  const wordIn = spring({ frame: frame - 42, fps, config: { damping: 200 } });
  const taglineIn = spring({ frame: frame - 58, fps, config: { damping: 200 } });
  const pulse = 1 + 0.03 * Math.sin((frame - 48) / 9);
  const exit = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );

  return (
    <AbsoluteFill style={{ opacity: exit }}>
      <Background intensity={1} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 26,
        }}
      >
        <div style={{ transform: `scale(${(0.85 + pop * 0.15) * pulse})` }}>
          <LogoMark size={190} draw={draw} glow={0.4 + draw} />
        </div>

        <div
          style={{
            fontFamily: FONT,
            fontSize: 104,
            fontWeight: 700,
            letterSpacing: -1,
            opacity: wordIn,
            transform: `translateY(${(1 - wordIn) * 20}px)`,
            background: `linear-gradient(90deg, ${COLORS.ink}, ${COLORS.violet})`,
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
            textShadow: `0 0 40px ${COLORS.violetDeep}40`,
          }}
        >
          MailMind
        </div>

        <div
          style={{
            fontFamily: FONT,
            fontSize: 26,
            letterSpacing: 6,
            color: COLORS.inkDim,
            fontWeight: 500,
            opacity: taglineIn,
            transform: `translateY(${(1 - taglineIn) * 14}px)`,
          }}
        >
          THE INTELLIGENT EMAIL CO-PILOT
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
