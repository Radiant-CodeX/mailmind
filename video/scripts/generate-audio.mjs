// Procedural sound design for the MailMind reveal.
// Generates a set of 44.1kHz 16-bit mono WAV files into ../public.
// Vibe: cinematic, cool, ethereal — minor-key ambient pad bed + clean UI SFX.
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

// Simple seeded noise.
let _s = 12345;
const noise = () => {
  _s = (_s * 1103515245 + 12345) & 0x7fffffff;
  return (_s / 0x3fffffff) - 1;
};

// ADSR-ish envelope by time t within total dur.
const env = (t, dur, attack, release) => {
  if (t < attack) return t / attack;
  if (t > dur - release) return Math.max(0, (dur - t) / release);
  return 1;
};

const writeWav = (name, data) => {
  const n = data.length;
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
    bytes.writeInt16LE(Math.round(clamp(data[i]) * 32767), 44 + i * 2);
  }
  writeFileSync(join(OUT, name), bytes);
  console.log("wrote", name, (bytes.length / 1024).toFixed(0) + "kb");
};

// Note frequencies (equal temperament, A4=440).
const note = (n) => 440 * Math.pow(2, (n - 69) / 12);
// MIDI: A2=45 C3=48 E3=52 G3=55 A3=57 C4=60 E4=64 G4=67 B4=71 D5=74

// ---- 1. Ambient pad bed (full track) --------------------------------------
// Slow evolving minor-9 pads. Two chords cross-fading, gentle tremolo, sub.
function makeBed(dur) {
  const out = buf(dur);
  // Chord voicings (MIDI notes). Am(add9) -> Fmaj9 feel, ethereal.
  const chordA = [45, 57, 60, 64, 67, 74]; // A2 A3 C4 E4 G4 D5
  const chordB = [41, 53, 60, 65, 69, 72]; // F2 F3 C4 F4 A4 C5
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const x = t / dur;
    // crossfade between the two chords across the track, twice
    const morph = 0.5 - 0.5 * Math.cos(x * TAU * 1.5);
    let s = 0;
    for (let v = 0; v < chordA.length; v++) {
      const fa = note(chordA[v]);
      const fb = note(chordB[v]);
      const f = lerp(fa, fb, morph);
      const detune = 1 + 0.004 * Math.sin(t * 0.7 + v);
      // two slightly detuned saw-ish (sine stack) voices for warmth
      const voice =
        Math.sin(TAU * f * detune * t) * 0.6 +
        Math.sin(TAU * f * 2 * t) * 0.12 * (v < 3 ? 1 : 0.3);
      const voiceGain = v === 0 ? 0.9 : 0.55 / (v + 1);
      s += voice * voiceGain;
    }
    // sub layer
    s += Math.sin(TAU * note(33) * t) * 0.18;
    // slow tremolo shimmer
    const trem = 0.85 + 0.15 * Math.sin(t * TAU * 0.25);
    // a touch of air
    s += noise() * 0.012;
    // global fade in/out
    const fade =
      Math.min(1, t / 2.5) * Math.min(1, (dur - t) / 3.0);
    out[i] = s * 0.16 * trem * fade;
  }
  return out;
}

// ---- 2. Whoosh transition --------------------------------------------------
function makeWhoosh(dur = 0.9) {
  const out = buf(dur);
  let lp = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const x = t / dur;
    // filtered noise that sweeps up then down
    const n = noise();
    const cutoff = lerp(0.02, 0.5, Math.sin(x * Math.PI)); // band-ish
    lp += (n - lp) * cutoff;
    const body = lp;
    const e = Math.sin(x * Math.PI); // swell in-out
    // a faint pitch sweep tone underneath
    const tone = Math.sin(TAU * lerp(180, 520, x) * t) * 0.15;
    out[i] = (body * 0.9 + tone) * e * 0.5;
  }
  return out;
}

// ---- 3. Impact / boom ------------------------------------------------------
function makeImpact(dur = 1.1) {
  const out = buf(dur);
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    // pitch-dropping sine sub
    const f = lerp(140, 42, Math.min(1, t / 0.25));
    const sub = Math.sin(TAU * f * t);
    // transient click
    const click = noise() * Math.exp(-t * 90) * 0.6;
    const e = Math.exp(-t * 3.2);
    out[i] = (sub * e + click) * 0.85;
  }
  return out;
}

// ---- 4. Riser --------------------------------------------------------------
function makeRiser(dur = 1.3) {
  const out = buf(dur);
  let lp = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const x = t / dur;
    // rising filtered noise + rising tone
    const n = noise();
    lp += (n - lp) * lerp(0.03, 0.45, x);
    const tone = Math.sin(TAU * lerp(120, 900, x * x) * t) * 0.2;
    const e = Math.pow(x, 1.5); // build up
    out[i] = (lp * 0.7 + tone) * e * 0.5;
  }
  return out;
}

// ---- 5. Soft UI tick -------------------------------------------------------
function makeTick(dur = 0.09, freq = 1400) {
  const out = buf(dur);
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    const e = Math.exp(-t * 55);
    const s = Math.sin(TAU * freq * t) * 0.6 + noise() * 0.2 * Math.exp(-t * 120);
    out[i] = s * e * 0.5;
  }
  return out;
}

// ---- 6. Typing loop (soft mechanical keys) --------------------------------
function makeTyping(dur = 1.6) {
  const out = buf(dur);
  const keyEvery = 0.075; // ~13 keys/sec
  for (let k = 0; k * keyEvery < dur; k++) {
    const start = k * keyEvery + (noise() * 0.01);
    const freq = 1100 + noise() * 500;
    const startIdx = Math.floor(start * SR);
    for (let j = 0; j < SR * 0.05; j++) {
      const idx = startIdx + j;
      if (idx >= out.length) break;
      const t = j / SR;
      const e = Math.exp(-t * 70);
      out[idx] +=
        (Math.sin(TAU * freq * t) * 0.4 + noise() * 0.5 * Math.exp(-t * 200)) *
        e *
        0.28;
    }
  }
  return out;
}

// ---- 7. Chime / success bell ----------------------------------------------
function makeChime(dur = 1.8) {
  const out = buf(dur);
  // bell partials over a C major triad up high
  const partials = [
    [note(72), 1.0],
    [note(76), 0.7],
    [note(79), 0.55],
    [note(84), 0.35],
    [note(88), 0.2],
  ];
  for (let i = 0; i < out.length; i++) {
    const t = i / SR;
    let s = 0;
    for (const [f, g] of partials) {
      s += Math.sin(TAU * f * t) * g;
    }
    const e = Math.exp(-t * 2.0) * env(t, dur, 0.005, 0.4);
    out[i] = s * e * 0.12;
  }
  return out;
}

// ---- render all ------------------------------------------------------------
const TOTAL = 670 / 30 + 0.4; // composition seconds + tail
writeWav("bed.wav", makeBed(TOTAL));
writeWav("whoosh.wav", makeWhoosh());
writeWav("impact.wav", makeImpact());
writeWav("riser.wav", makeRiser());
writeWav("tick.wav", makeTick());
writeWav("tick-hi.wav", makeTick(0.08, 1900));
writeWav("typing.wav", makeTyping());
writeWav("chime.wav", makeChime());
console.log("done");
