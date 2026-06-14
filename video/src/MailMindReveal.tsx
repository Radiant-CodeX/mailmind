import React from "react";
import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { FONT_FAMILY } from "./fonts";
import { SoundDesign } from "./SoundDesign";
import { SCENE_ORDER, TRANSITION, TOTAL_DURATION } from "./timeline";
import { SceneIntro } from "./scenes/SceneIntro";
import { SceneLogo } from "./scenes/SceneLogo";
import { SceneDashboard } from "./scenes/SceneDashboard";
import { SceneTriage } from "./scenes/SceneTriage";
import { SceneToneDNA } from "./scenes/SceneToneDNA";
import { SceneFeatures } from "./scenes/SceneFeatures";
import { SceneCTA } from "./scenes/SceneCTA";

export { TOTAL_DURATION };

const SCENE_COMPONENT: Record<string, React.FC> = {
  intro: SceneIntro,
  logo: SceneLogo,
  dashboard: SceneDashboard,
  triage: SceneTriage,
  tone: SceneToneDNA,
  features: SceneFeatures,
  cta: SceneCTA,
};

const t = () => linearTiming({ durationInFrames: TRANSITION });

export const MailMindReveal: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#05060a", fontFamily: FONT_FAMILY }}>
      <SoundDesign />
      <TransitionSeries>
        {SCENE_ORDER.flatMap((s, i) => {
          const Comp = SCENE_COMPONENT[s.key];
          const nodes = [
            <TransitionSeries.Sequence key={s.key} durationInFrames={s.duration}>
              <Comp />
            </TransitionSeries.Sequence>,
          ];
          if (i < SCENE_ORDER.length - 1) {
            nodes.push(
              <TransitionSeries.Transition
                key={`${s.key}-t`}
                presentation={fade()}
                timing={t()}
              />,
            );
          }
          return nodes;
        })}
      </TransitionSeries>
    </AbsoluteFill>
  );
};
