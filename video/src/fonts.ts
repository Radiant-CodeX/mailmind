import { loadFont as loadSpaceGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";

const sg = loadSpaceGrotesk("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const jb = loadJetBrainsMono("normal", {
  weights: ["400", "500"],
  subsets: ["latin"],
});

export const FONT_FAMILY = `${sg.fontFamily}, system-ui, sans-serif`;
export const MONO_FAMILY = `${jb.fontFamily}, ui-monospace, monospace`;
