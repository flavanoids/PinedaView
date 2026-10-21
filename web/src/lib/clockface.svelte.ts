// SPDX-License-Identifier: Apache-2.0
/**
 * Per-device clock face. The clock card composes the time several ways — a
 * carved serif block, the time in words, a split-flap board, a seven-segment
 * LCD, a poster-scale column, two hands on a bare dial or a domed one, or a
 * QLOCKTWO-style letter grid. Each screen in the house can wear a different
 * one.
 *
 * Stored in localStorage (like the motion tier and interface size), not on the
 * server. A `?clock=` URL param seeds it for a kiosk that can't reach Settings,
 * and the phone menu can push one to every screen on a profile (`pushed`).
 */
import { readLocal, writeLocal } from "./storage";

export type ClockFace =
  | "stack"
  | "words"
  | "poster"
  | "flip"
  | "seg"
  | "analog"
  | "contour"
  | "bulge"
  | "qlock";

export const KEY = "pineda.clockFace";

const DEFAULT: ClockFace = "stack";

export const FACES: { id: ClockFace; label: string }[] = [
  { id: "stack", label: "Stacked" },
  { id: "words", label: "In words" },
  { id: "poster", label: "Poster" },
  { id: "flip", label: "Flip board" },
  { id: "seg", label: "Seven-segment" },
  { id: "analog", label: "Analog" },
  { id: "contour", label: "Contour" },
  { id: "bulge", label: "Bulge" },
  { id: "qlock", label: "Word grid" },
];

export type PhotoClockFont =
  "roboto" | "aileron" | "fraunces" | "bricolage" | "anton" | "cormorant";

export type PhotoClockSize = "s" | "m" | "l" | "xl";
export type PhotoClockGlass =
  | "liquid"
  | "frosted"
  | "crystal"
  | "flat"
  | "mesh"
  | "match"
  | "opposite"
  | "chrome"
  | "print"
  | "neon";
export type PhotoClockLayout = "row" | "stack";
export type PhotoClockTransition = "swipe" | "fade";

export interface PhotoClockSettings {
  font: PhotoClockFont;
  size: PhotoClockSize;
  glass: PhotoClockGlass;
  opacity: number;
  depth: boolean;
  date: boolean;
  /** Glass figures, or the round clock with glass hands. */
  face: "digits" | "hands";
  /** The round clock's second hand. */
  seconds: boolean;
  /** The round clock's hands glide at 60 fps instead of ticking. */
  sweep: boolean;
  layout: PhotoClockLayout;
  drift: boolean;
  transition: PhotoClockTransition;
  whisper: boolean;
  weather: boolean;
  grain: number;
}

/** Where the Photo Clock's settings lived before they moved to the server
    (the screen's `photo_clock`). Read once to carry them over. */
const LEGACY_PHOTO_CLOCK_KEY = "pineda.photoClockSettings";

export const DEFAULT_PHOTO_CLOCK: PhotoClockSettings = {
  font: "roboto",
  size: "l",
  glass: "liquid",
  opacity: 0.45,
  depth: true,
  date: true,
  face: "digits",
  seconds: false,
  sweep: false,
  layout: "row",
  drift: false,
  transition: "swipe",
  whisper: false,
  weather: false,
  grain: 0.0,
};

export const PHOTO_CLOCK_FONTS: {
  id: PhotoClockFont;
  label: string;
  family: string;
}[] = [
  { id: "roboto", label: "Roboto", family: "'Roboto', sans-serif" },
  { id: "aileron", label: "Aileron", family: "'Aileron', sans-serif" },
  { id: "fraunces", label: "Fraunces", family: "'Fraunces', serif" },
  {
    id: "bricolage",
    label: "Bricolage",
    family: "'Bricolage Grotesque', sans-serif",
  },
  { id: "anton", label: "Anton", family: "'Anton', sans-serif" },
  { id: "cormorant", label: "Cormorant", family: "'Cormorant', serif" },
];

/** A screen's stored Photo Clock settings over the defaults. */
export function resolvePhotoClock(
  saved: Partial<PhotoClockSettings> | null | undefined,
): PhotoClockSettings {
  return { ...DEFAULT_PHOTO_CLOCK, ...saved };
}

/** Settings this browser kept for itself before they moved to the server,
    handed over once: reading them forgets them, so a later Reset sticks. */
export function takeLegacyPhotoClock(): PhotoClockSettings | null {
  const saved = readLocal(LEGACY_PHOTO_CLOCK_KEY);
  if (!saved) return null;
  writeLocal(LEGACY_PHOTO_CLOCK_KEY, "");
  try {
    return resolvePhotoClock(JSON.parse(saved) as Partial<PhotoClockSettings>);
  } catch {
    return null;
  }
}

const IDS = new Set<string>(FACES.map((f) => f.id));

export function isClockFace(value: unknown): value is ClockFace {
  return typeof value === "string" && IDS.has(value);
}

export const clockFace = $state<{
  face: ClockFace;
  /** Pushed from the phone menu's /settings page via the view (the profile's
      clock_face). While set it wins over this screen's own choice — and over
      a kiosk's `?clock=`, which re-seeds `face` on every boot. */
  pushed: ClockFace | null;
}>({ face: DEFAULT, pushed: null });

/** The face to draw: the pushed one if any, else this screen's own. */
export function currentFace(): ClockFace {
  return clockFace.pushed ?? clockFace.face;
}

export function initClockFace(): void {
  const saved = readLocal(KEY);
  clockFace.face = isClockFace(saved) ? saved : DEFAULT;
}

/** Settings → Display. */
export function setClockFace(face: ClockFace): void {
  clockFace.face = face;
  writeLocal(KEY, face);
}
