import React from "react";
import { Sequence, staticFile } from "remotion";
import { Audio } from "@remotion/media";
import { SCENE_START } from "./timeline";

// Scene start frames are derived from the single timeline source of truth, so
// adding/removing a scene keeps every cue aligned automatically.
const START = SCENE_START;

const sf = (name: string) => staticFile(`audio/${name}`);

const Sfx: React.FC<{
  src: string;
  from: number;
  volume?: number;
  loop?: boolean;
  durationInFrames?: number;
}> = ({ src, from, volume = 1, loop, durationInFrames }) => (
  <Sequence from={Math.max(0, from)} durationInFrames={durationInFrames} layout="none">
    <Audio src={sf(src)} volume={volume} loop={loop} />
  </Sequence>
);

// Dashboard: triage results resolve per-row at 50 + i*9 (see SceneDashboard).
const DASH_RESOLVE = (i: number) => 50 + i * 9;
const DASH_ROWS = 7;
const DASH_LAST = DASH_RESOLVE(DASH_ROWS - 1) + 12;

// All cues are timed to the scene starts above.
export const SoundDesign: React.FC = () => {
  return (
    <>
      {/* Ambient music bed for the whole piece (fades baked into the wav). */}
      <Audio src={sf("bed.wav")} volume={0.5} />

      {/* Transition whooshes */}
      <Sfx src="whoosh.wav" from={START.logo - 10} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.dashboard - 10} volume={0.4} />
      <Sfx src="riser.wav" from={START.triage - 24} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.tone - 10} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.features - 10} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.cta - 12} volume={0.5} />

      {/* Logo reveal impact */}
      <Sfx src="impact.wav" from={START.logo + 30} volume={0.7} />

      {/* ── Dashboard: live triage ──────────────────────────────────────── */}
      {/* Soft typing texture while the co-pilot works through the inbox. */}
      <Sfx
        src="typing.wav"
        from={START.dashboard + 14}
        durationInFrames={DASH_RESOLVE(DASH_ROWS - 1) - 6}
        loop
        volume={0.28}
      />
      {/* A blip as each row's score + priority lands. */}
      {Array.from({ length: DASH_ROWS }, (_, i) => (
        <Sfx
          key={`d${i}`}
          src="tick-hi.wav"
          from={START.dashboard + DASH_RESOLVE(i)}
          volume={0.32}
        />
      ))}
      {/* Success chime when the whole inbox is triaged. */}
      <Sfx src="chime.wav" from={START.dashboard + DASH_LAST} volume={0.4} />
      {/* Cursor click on the critical email. */}
      <Sfx src="tick.wav" from={START.dashboard + 122} volume={0.4} />

      {/* Triage bars filling in (delay 18 + i*7) */}
      {[0, 1, 2, 3, 4].map((i) => (
        <Sfx
          key={`t${i}`}
          src="tick-hi.wav"
          from={START.triage + 18 + i * 7}
          volume={0.3}
        />
      ))}

      {/* Tone DNA typewriter — the hero typing moment, drafting in your voice. */}
      <Sfx
        src="typing.wav"
        from={START.tone + 24}
        durationInFrames={112}
        loop
        volume={0.55}
      />
      <Sfx src="tick.wav" from={START.tone + 138} volume={0.3} />

      {/* Feature cards popping in (delay 12 + i*6) */}
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Sfx
          key={`f${i}`}
          src="tick.wav"
          from={START.features + 12 + i * 6}
          volume={0.28}
        />
      ))}

      {/* CTA: chime on logo, impact on the button */}
      <Sfx src="chime.wav" from={START.cta + 4} volume={0.55} />
      <Sfx src="impact.wav" from={START.cta + 46} volume={0.6} />
    </>
  );
};
