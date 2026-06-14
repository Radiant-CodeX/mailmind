import React from "react";
import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { FONT_FAMILY } from "./fonts";
import { SoundDesign } from "./SoundDesign";
import { SceneIntro } from "./scenes/SceneIntro";
import { SceneLogo } from "./scenes/SceneLogo";
import { SceneTriage } from "./scenes/SceneTriage";
import { SceneToneDNA } from "./scenes/SceneToneDNA";
import { SceneFeatures } from "./scenes/SceneFeatures";
import { SceneCTA } from "./scenes/SceneCTA";

export const SCENE_DURATIONS = {
  intro: 105,
  logo: 100,
  triage: 130,
  tone: 150,
  features: 140,
  cta: 120,
} as const;

export const TRANSITION = 15;

export const TOTAL_DURATION =
  Object.values(SCENE_DURATIONS).reduce((a, b) => a + b, 0) - TRANSITION * 5;

const t = () => linearTiming({ durationInFrames: TRANSITION });

export const MailMindReveal: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#05060a", fontFamily: FONT_FAMILY }}>
      <SoundDesign />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={SCENE_DURATIONS.intro}>
          <SceneIntro />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t()} />

        <TransitionSeries.Sequence durationInFrames={SCENE_DURATIONS.logo}>
          <SceneLogo />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t()} />

        <TransitionSeries.Sequence durationInFrames={SCENE_DURATIONS.triage}>
          <SceneTriage />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t()} />

        <TransitionSeries.Sequence durationInFrames={SCENE_DURATIONS.tone}>
          <SceneToneDNA />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t()} />

        <TransitionSeries.Sequence durationInFrames={SCENE_DURATIONS.features}>
          <SceneFeatures />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={t()} />

        <TransitionSeries.Sequence durationInFrames={SCENE_DURATIONS.cta}>
          <SceneCTA />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};
