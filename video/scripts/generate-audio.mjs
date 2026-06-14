// Sound design for the MailMind reveal — rebuilt from scratch.
// =============================================================
// Goal: aesthetic and clean, NOT noisy. Everything is tonal and in key
// (C major / C-major-pentatonic), so the SFX feel musical against the pad bed.
// White noise is avoided entirely; "air" and space come from a small Schroeder
// reverb instead. Generates 44.1kHz 16-bit mono WAVs into ../public/audio.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "public", "audio");
mkdirSync(OUT, { recursive: true });

const SR = 44100;
const TAU = Math.PI * 2;

// ---- helpers ---------------------------------------------------------------
const buf = (seconds) => new Float32Array(Math.ceil(seconds * SR));
const clamp = (v) => Math.max(-1, Math.min(1, v));
const lerp = (a, b, t) => a + (b - a) * t;
const sat = (x) => Math.tanh(x * 1.1); // gentle warmth / glue, no hard edges
const note = (n) => 440 * Math.pow(2, (n - 69) / 12); // A4=440

// A sine with a few soft, quickly-thinning harmonics → a clean "bell/celesta"
// timbre without any noise.
const bell = (f, t) =>
  Math.sin(TAU * f * t) +
  Math.sin(TAU * 2 * f * t) * 0.22 +
  Math.sin(TAU * 3 * f * t) * 0.08 +
  Math.sin(TAU * 4.2 * f * t) * 0.03;

// C major pentatonic across a few octaves (MIDI). Used so every blip is in key.
// C4 D4 E4 G4 A4 C5 D5 E5 G5 A5 C6 D6 E6
const PENTA = [60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84, 86, 88];

// ---- a small, clean Schroeder reverb (Freeverb-ish) -----------------------
// Adds space/polish so short sounds bloom instead of clicking. Fully
// deterministic, no randomness.
function reverb(input, { mix = 0.22, decay = 0.72, tailSec = 0.0 } = {}) {
  const len = input.length + Math.floor(tailSec * SR);
  const out = new Float32Array(len);
  const combTunings = [1116, 1188, 1277, 1356, 1422, 1491];
  const allpassTunings = [556, 441, 341, 225];
  const combs = combTunings.map((d) => ({
    b: new Float32Array(d),
    i: 0,
    fb: decay,
    lp: 0,
  }));
  const alls = allpassTunings.map((d) => ({ b: new Float32Array(d), i: 0, fb: 0.5 }));
  for (let n = 0; n < len; n++) {
    const x = n < input.length ? input[n] : 0;
    let wet = 0;
    for (const c of combs) {
      const y = c.b[c.i];
      // gentle damping low-pass inside the comb keeps the tail smooth/dark
      c.lp = y * 0.6 + c.lp * 0.4;
      wet += y;
      c.b[c.i] = x + c.lp * c.fb;
      c.i = (c.i + 1) % c.b.length;
    }
    wet /= combs.length;
    for (const a of alls) {
      const d = a.b[a.i];
      const y = d - wet * a.fb;
      a.b[a.i] = wet + d * a.fb;
      a.i = (a.i + 1) % a.b.length;
      wet = y;
    }
    out[n] = x * (1 - mix) + wet * mix;
  }
  return out;
}

// Remove DC offset / sub-sonic drift (a decaying sub leaves a net DC term).
// One-pole high-pass at ~20 Hz: preserves audible sub, kills the offset+click.
function dcblock(data, R = 0.997) {
  let xPrev = 0;
  let yPrev = 0;
  for (let i = 0; i < data.length; i++) {
    const x = data[i];
    const y = x - xPrev + R * yPrev;
    xPrev = x;
    yPrev = y;
    data[i] = y;
  }
  return data;
}

// Normalise to a target peak so nothing clips and levels are consistent.
function normalize(data, peak = 0.9) {
  let mx = 0;
  for (let i = 0; i < data.length; i++) mx = Math.max(mx, Math.abs(data[i]));
  if (mx < 1e-6) return data;
  const g = peak / mx;
  for (let i = 0; i < data.length; i++) data[i] *= g;
  return data;
}

const writeWav = (name, data) => {
  const dcblocked = dcblock(data);
  const n = dcblocked.length;
  const bytes = Buffer.alloc(44 + n * 2);
  bytes.write("RIFF", 0);
  bytes.writeUInt32LE(36 + n * 2, 4);
  bytes.write("WAVE", 8);
  bytes.write("fmt ", 12);
  bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20); // PCM
  bytes.writeUInt16LE(1, 22); // mono
  bytes.writeUInt32LE(SR, 24);
  bytes.writeUInt32LE(SR * 2, 28);
  bytes.writeUInt16LE(2, 32);
  bytes.writeUInt16LE(16, 34);
  bytes.write("data", 36);
  bytes.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) {
    bytes.writeInt16LE(Math.round(clamp(dcblocked[i]) * 32767), 44 + i * 2);
  }
  writeFileSync(join(OUT, name), bytes);
  console.log("wrote", name, (bytes.length / 1024).toFixed(0) + "kb");
};

// ---- 1. Ambient pad bed (full track) --------------------------------------
// Warm, neutral, professional. A simple I–V–vi–IV progression in C major with
// discrete crossfaded chord changes, a gentle low-pass to stay mellow, a soft
// sub, and a sparse felt-piano pluck for quiet motion. No detune-wobble, no
// shimmer, no noise.
const CHORDS = [
  [48, 55, 60, 64, 67], // C  : C3 G3 C4 E4 G4
  [47, 55, 59, 62, 67], // G  : B2 G3 B3 D4 G4
  [45, 52, 57, 60, 64], // Am : A2 E3 A3 C4 E4
  [41, 53, 57, 60, 65], // F  : F2 F3 A3 C4 F4
];

function chordVoices(chord, t) {
  let s = 0;
  const det = 0.0011; // ~2 cents, warmth only
  for (let v = 0; v < chord.length; v++) {
    const f = note(chord[v]);
    const pair =
      Math.sin(TAU * f * (1 - det) * t) + Math.sin(TAU * f * (1 + det) * t);
    const harm = Math.sin(TAU * 2 * f * t) * 0.09;
    const g = v === 0 ? 0.5 : 0.4 / (v + 0.5);
    s += (pair * 0.5 + harm) * g;
  }
  return s * 0.5;
}

function makeBed(dur) {
  const out = buf(dur);
  const hold = 5.0; // seconds per chord
  const fade = 1.4; // crossfade into the next chord
  const fadeFrac = fade / hold;
  let lp = 0; // one-pole low-pass (~1.2 kHz)
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const pos = t / hold;
    const idx = Math.floor(pos) % CHORDS.length;
    const nextIdx = (idx + 1) % CHORDS.length;
    const frac = pos - Math.floor(pos);
    const blend = frac > 1 - fadeFrac ? (frac - (1 - fadeFrac)) / fadeFrac : 0;

    let s =
      chordVoices(CHORDS[idx], t) * (1 - blend) +
      chordVoices(CHORDS[nextIdx], t) * blend;

    const subA = Math.sin(TAU * note(CHORDS[idx][0] - 12) * t);
    const subB = Math.sin(TAU * note(CHORDS[nextIdx][0] - 12) * t);
    s += (subA * (1 - blend) + subB * blend) * 0.16;

    lp += (s - lp) * 0.18;
    s = lp;

    // Sparse felt-piano pluck on an upper chord tone, ~one per 1.25 s.
    const plistep = 1.25;
    const pk = Math.floor(t / plistep);
    const ptone = note(CHORDS[idx][2 + (pk % 3)]);
    const pt = t - pk * plistep;
    s += Math.sin(TAU * ptone * pt) * Math.exp(-pt * 6) * 0.05;

    const fadeg = Math.min(1, t / 3) * Math.min(1, (dur - t) / 3.5);
    out[i] = sat(s * 0.95) * 0.13 * fadeg;
  }
  // A whisper of reverb for air — kept very low so the bed stays clean.
  // Normalised to a steady bed level (it's continuous, so it sits lower than
  // the transient SFX even at a similar peak).
  return normalize(reverb(out, { mix: 0.16, decay: 0.7 }), 0.5);
}

// ---- 2. Lift (transition swoosh, tonal) -----------------------------------
// Replaces the old noise whoosh. A soft major triad that swells up with a small
// upward pitch glide + reverb bloom. Airy, musical, not hissy.
function makeLift(dur = 0.85) {
  const out = buf(dur);
  const notes = [60, 64, 67]; // C E G
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const x = t / dur;
    const glide = lerp(0.94, 1.06, x); // gentle rise
    const swell = Math.sin(Math.min(1, x) * Math.PI); // in-out
    let s = 0;
    for (const m of notes) s += Math.sin(TAU * note(m) * glide * t);
    out[i] = sat((s / notes.length) * swell * 0.6);
  }
  return normalize(reverb(out, { mix: 0.3, decay: 0.7, tailSec: 0.5 }), 0.85);
}

// ---- 3. Build (riser into a beat, tonal) ----------------------------------
// Accelerating ascending pentatonic plucks (a harp-like run up) under a swelling
// pad — builds anticipation without any noise sweep.
function makeBuild(dur = 1.35) {
  const out = buf(dur);
  // Swelling pad (C major) underneath.
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const x = t / dur;
    const pad =
      (Math.sin(TAU * note(60) * t) +
        Math.sin(TAU * note(64) * t) +
        Math.sin(TAU * note(67) * t)) /
      3;
    out[i] = pad * Math.pow(x, 1.6) * 0.35;
  }
  // Ascending run: notes get closer together (accelerando) and rise in pitch.
  const steps = 9;
  let tcur = 0.05;
  for (let k = 0; k < steps; k++) {
    const m = PENTA[Math.min(PENTA.length - 1, 3 + k)]; // climb the scale
    const f = note(m);
    const startIdx = Math.floor(tcur * SR);
    for (let j = 0; j < SR * 0.4; j++) {
      const idx = startIdx + j;
      if (idx >= out.length) break;
      const tt = j / SR;
      const e = Math.exp(-tt * 7);
      out[idx] += bell(f, tt) * e * 0.4;
    }
    tcur += lerp(0.16, 0.06, k / (steps - 1)); // accelerate
  }
  return normalize(reverb(out, { mix: 0.26, decay: 0.72, tailSec: 0.6 }), 0.9);
}

// ---- 4. Bloom (impact / arrival, tonal) -----------------------------------
// Clean deep sub with a pitch drop + a low octave chord bloom and reverb tail.
// No transient noise click — the "weight" is all tonal.
function makeBloom(dur = 1.4) {
  const out = buf(dur);
  const low = [36, 43, 48]; // C2 G2 C3
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    // Sub with a short pitch drop for body.
    const f = lerp(96, 46, Math.min(1, t / 0.18));
    const sub = Math.sin(TAU * f * t) * Math.exp(-t * 2.6);
    // Low chord bloom (soft attack so there's no click).
    let chord = 0;
    for (const m of low) chord += Math.sin(TAU * note(m) * t);
    chord = (chord / low.length) * Math.min(1, t / 0.02) * Math.exp(-t * 3.0);
    out[i] = sat(sub * 0.8 + chord * 0.5);
  }
  return normalize(reverb(out, { mix: 0.25, decay: 0.75, tailSec: 0.8 }), 0.92);
}

// ---- 5. Blip (clean UI tick, in key) --------------------------------------
// A short pentatonic bell — celesta-like. Multiple of these in a row form a
// gentle musical run as triage scores resolve. No noise.
function makeBlip(midi, dur = 0.55) {
  const out = buf(dur);
  const f = note(midi);
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const e = Math.exp(-t * 9) * Math.min(1, t / 0.003); // soft attack, bell decay
    out[i] = bell(f, t) * e * 0.5;
  }
  return normalize(reverb(out, { mix: 0.24, decay: 0.55, tailSec: 0.3 }), 0.8);
}

// ---- 6. Typing (soft keys, minimal noise) ---------------------------------
// Each keystroke is mostly a low tonal "tok" plus a gentle, heavily low-passed
// click — no white-noise hiss. Humanised cadence with occasional fast doubles.
function makeTyping(dur = 2.4) {
  const out = buf(dur);
  // Deterministic pseudo-jitter so timing feels human but renders identically.
  let seed = 7;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff; // 0..1
  };
  const press = (at) => {
    const startIdx = Math.floor(at * SR);
    const tokF = 150 + rnd() * 90; // 150–240 Hz woody body
    let click = 0;
    for (let j = 0; j < SR * 0.1; j++) {
      const idx = startIdx + j;
      if (idx >= out.length) break;
      const t = j / SR;
      // Low-passed impulse → a soft "tick" with no hiss.
      const imp = j === 0 ? 1 : 0;
      click = imp + click * 0.86; // leaky integrator (one-pole)
      const tok = Math.sin(TAU * tokF * t) * Math.exp(-t * 42) * 0.5;
      out[idx] += sat(tok + click * Math.exp(-t * 60) * 0.18) * 0.34;
    }
  };
  let t0 = 0.02;
  while (t0 < dur) {
    press(t0);
    const fast = rnd() > 0.8;
    const gap = fast ? 0.05 + rnd() * 0.02 : 0.09 + rnd() * 0.07;
    t0 += gap;
  }
  return normalize(out, 0.7); // dry — keyboards don't live in a reverb hall
}

// ---- 7. Chime (success bell arpeggio) -------------------------------------
// A pretty ascending C-major arpeggio that rings out — the "done" moment.
function makeChime(dur = 2.0) {
  const out = buf(dur);
  const arp = [72, 76, 79, 84]; // C5 E5 G5 C6
  arp.forEach((m, k) => {
    const start = k * 0.09;
    const f = note(m);
    const startIdx = Math.floor(start * SR);
    for (let j = 0; j < out.length - startIdx; j++) {
      const idx = startIdx + j;
      const t = j / SR;
      const e = Math.exp(-t * 2.4) * Math.min(1, t / 0.004);
      out[idx] += bell(f, t) * e * (0.34 - k * 0.04);
    }
  });
  return normalize(reverb(out, { mix: 0.3, decay: 0.78, tailSec: 1.0 }), 0.85);
}

// ---- render all ------------------------------------------------------------
const TOTAL = 830 / 30 + 0.5; // composition seconds + tail (see timeline.ts)
writeWav("bed.wav", makeBed(TOTAL));
writeWav("whoosh.wav", makeLift()); // tonal "lift" (filename kept for wiring)
writeWav("riser.wav", makeBuild());
writeWav("impact.wav", makeBloom());
writeWav("tick.wav", makeBlip(81)); // A5
writeWav("tick-hi.wav", makeBlip(88)); // E6
writeWav("typing.wav", makeTyping());
writeWav("chime.wav", makeChime());
console.log("done");
