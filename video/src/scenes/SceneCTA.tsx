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

export const SceneCTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoIn = spring({ frame: frame - 4, fps, config: { damping: 14 } });
  const wordIn = spring({ frame: frame - 16, fps, config: { damping: 200 } });
  const lineIn = spring({ frame: frame - 30, fps, config: { damping: 200 } });
  const pillIn = spring({ frame: frame - 46, fps, config: { damping: 14 } });
  const pulse = 1 + 0.02 * Math.sin(frame / 10);

  // Sweep a soft glow across the title.
  const sweep = interpolate(frame, [20, 70], [-40, 140], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <Background intensity={1.1} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 30,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 24,
            transform: `scale(${(0.9 + logoIn * 0.1) * pulse})`,
            opacity: logoIn,
          }}
        >
          <LogoMark size={92} draw={logoIn} glow={1.1} />
          <div
            style={{
              fontFamily: FONT,
              fontSize: 80,
              fontWeight: 700,
              letterSpacing: -1,
              color: COLORS.ink,
            }}
          >
            MailMind
          </div>
        </div>

        <div
          style={{
            position: "relative",
            fontFamily: FONT,
            fontSize: 64,
            fontWeight: 700,
            color: COLORS.ink,
            opacity: wordIn,
            transform: `translateY(${(1 - wordIn) * 18}px)`,
            backgroundImage: `linear-gradient(90deg, ${COLORS.ink} 0%, ${COLORS.violet} ${sweep}%, ${COLORS.ink} ${sweep + 20}%)`,
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          Every inbox, one mind.
        </div>

        <div
          style={{
            fontFamily: FONT,
            fontSize: 26,
            color: COLORS.inkDim,
            opacity: lineIn,
            transform: `translateY(${(1 - lineIn) * 14}px)`,
            maxWidth: 760,
            textAlign: "center",
            lineHeight: 1.5,
          }}
        >
          Prioritize, draft, and never drop a commitment — with you in
          control of every send.
        </div>

        <div
          style={{
            marginTop: 18,
            opacity: pillIn,
            transform: `scale(${0.9 + pillIn * 0.1})`,
            fontFamily: FONT,
            fontSize: 26,
            fontWeight: 600,
            color: COLORS.bg0,
            padding: "18px 44px",
            borderRadius: 999,
            background: `linear-gradient(90deg, ${COLORS.cyan}, ${COLORS.violet})`,
            boxShadow: `0 0 50px ${COLORS.violetDeep}80`,
          }}
        >
          Reclaim your inbox →
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
