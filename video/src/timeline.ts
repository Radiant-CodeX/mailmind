// Single source of truth for scene order, durations and the resulting cue
// offsets. Kept free of component imports so both the composition
// (MailMindReveal) and the sound design can import it without a cycle.

export const TRANSITION = 15;

export const SCENE_ORDER = [
  { key: "intro", duration: 105 },
  { key: "logo", duration: 100 },
  { key: "dashboard", duration: 175 },
  { key: "triage", duration: 130 },
  { key: "tone", duration: 150 },
  { key: "features", duration: 140 },
  { key: "cta", duration: 120 },
] as const;

export type SceneKey = (typeof SCENE_ORDER)[number]["key"];

// Frame at which each scene begins inside the TransitionSeries. Each preceding
// transition overlaps its neighbours by TRANSITION frames, so scene N starts at
// sum(durations[0..N-1]) − N·TRANSITION.
export const SCENE_START = SCENE_ORDER.reduce<Record<SceneKey, number>>(
  (acc, s, i) => {
    const prev = SCENE_ORDER.slice(0, i).reduce((a, x) => a + x.duration, 0);
    acc[s.key] = prev - i * TRANSITION;
    return acc;
  },
  {} as Record<SceneKey, number>,
);

export const TOTAL_DURATION =
  SCENE_ORDER.reduce((a, s) => a + s.duration, 0) -
  TRANSITION * (SCENE_ORDER.length - 1);
