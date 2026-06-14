import React from "react";
import { Sequence, staticFile } from "remotion";
import { Audio } from "@remotion/media";

// Scene start frames within the TransitionSeries (durations minus 15f overlaps).
const START = {
  intro: 0,
  logo: 90,
  triage: 175,
  tone: 290,
  features: 425,
  cta: 550,
} as const;

const sf = (name: string) => staticFile(`audio/${name}`);

const Sfx: React.FC<{
  src: string;
  from: number;
  volume?: number;
  loop?: boolean;
  durationInFrames?: number;
}> = ({ src, from, volume = 1, loop, durationInFrames }) => (
  <Sequence from={from} durationInFrames={durationInFrames} layout="none">
    <Audio src={sf(src)} volume={volume} loop={loop} />
  </Sequence>
);

// All cues are timed to the scene starts above.
export const SoundDesign: React.FC = () => {
  return (
    <>
      {/* Ambient music bed for the whole piece (fades baked into the wav). */}
      <Audio src={sf("bed.wav")} volume={0.9} />

      {/* Transition whooshes */}
      <Sfx src="whoosh.wav" from={START.logo - 10} volume={0.45} />
      <Sfx src="riser.wav" from={START.triage - 24} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.tone - 10} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.features - 10} volume={0.4} />
      <Sfx src="whoosh.wav" from={START.cta - 12} volume={0.5} />

      {/* Logo reveal impact */}
      <Sfx src="impact.wav" from={START.logo + 30} volume={0.7} />

      {/* Triage bars filling in (delay 18 + i*7) */}
      {[0, 1, 2, 3, 4].map((i) => (
        <Sfx
          key={`t${i}`}
          src="tick-hi.wav"
          from={START.triage + 18 + i * 7}
          volume={0.3}
        />
      ))}

      {/* Tone DNA typewriter */}
      <Sfx
        src="typing.wav"
        from={START.tone + 24}
        durationInFrames={112}
        loop
        volume={0.5}
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
