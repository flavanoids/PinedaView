// SPDX-License-Identifier: Apache-2.0
/**
 * Per-device interface scale. One multiplier — `--ui-scale` on <html> — that
 * every structural token (spacing, radii, type floors, QR, tap targets) is a
 * multiple of. It starts from what the browser reports about the panel (CSS
 * resolution + device-pixel-ratio) and can be pinned in Settings → Display for
 * the odd tablet the heuristic gets wrong. The Accessibility "Larger text"
 * toggle multiplies whatever is in force.
 */
import { readLocal, writeLocal } from "./storage";

export type DisplaySize = "auto" | "s" | "m" | "l" | "xl";

export const KEY = "pineda.uiSize";

const MANUAL: Record<Exclude<DisplaySize, "auto">, number> = {
  s: 0.85,
  m: 1,
  l: 1.18,
  xl: 1.4,
};
const LARGE_TEXT_BOOST = 1.12;

export const display = $state<{
  choice: DisplaySize;
  /** The multiplier actually written to --ui-scale. */
  scale: number;
  /** What auto-detection alone would pick — shown as a hint in Settings. */
  detected: number;
}>({
  choice: "auto",
  scale: 1,
  detected: 1,
});

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

const round2 = (n: number): number => Math.round(n * 100) / 100;

/**
 * A starting multiplier from the panel itself. Larger, lower-density screens —
 * and the 1× panels common on older tablets, which tend to be physically big
 * and viewed from a distance — get nudged up; small dense handsets get nudged
 * down.
 */
export function detectScale(): number {
  if (typeof window === "undefined") return 1;
  const short = Math.min(window.innerWidth, window.innerHeight);
  const dpr = window.devicePixelRatio || 1;

  let scale =
    short >= 1500
      ? 1.35
      : short >= 1100
        ? 1.25
        : short >= 900
          ? 1.12
          : short >= 700
            ? 1
            : short >= 540
              ? 0.95
              : 0.9;

  // 1× panels are typically large and viewed from a distance (wall-mounted
  // displays, kiosk monitors — a 15.6" 1080p panel is often read from 3-10
  // feet, not arm's length), so they need a much firmer nudge than a dense
  // one that's held or sat in front of.
  if (dpr <= 1 && short >= 700) scale += 0.3;
  if (dpr >= 3 && short < 540) scale -= 0.05;

  return round2(clamp(scale, 0.8, 1.7));
}

function largerText(): boolean {
  return (
    typeof document !== "undefined" &&
    document.documentElement.hasAttribute("data-large-text")
  );
}

/** Another screen's scale, when this page is drawing it (lib/preview). */
let forced: number | null = null;

function compute(): number {
  if (forced !== null) return forced;
  const base =
    display.choice === "auto" ? display.detected : MANUAL[display.choice];
  return round2(base * (largerText() ? LARGE_TEXT_BOOST : 1));
}

let ready = false;
let bound = false;

function stamp(): void {
  display.scale = compute();
  const root = document.documentElement;
  root.style.setProperty("--ui-scale", String(display.scale));
  root.dataset.uiSize = display.choice;
}

export function initDisplay(): void {
  const saved = readLocal(KEY);
  display.choice =
    saved === "s" || saved === "m" || saved === "l" || saved === "xl"
      ? saved
      : "auto";
  display.detected = detectScale();
  ready = true;
  stamp();

  if (typeof window !== "undefined" && !bound) {
    bound = true;
    let timer: ReturnType<typeof setTimeout>;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        display.detected = detectScale();
        if (display.choice === "auto") stamp();
      }, 200);
    });
  }
}

/** Draw at exactly this scale, whatever this device would pick — the
    menu's live miniature copying the real screen. Not persisted. */
export function forceScale(scale: number): void {
  forced = scale;
  stamp();
}

/** Settings → Display. Persist an explicit size, or "auto". */
export function setDisplaySize(choice: DisplaySize): void {
  display.choice = choice;
  writeLocal(KEY, choice);
  stamp();
}

/** Re-read the "Larger text" state and restamp — called by setA11y so the
 * toggle takes effect without a reload. No-op until initDisplay() has run. */
export function refreshDisplayScale(): void {
  if (ready) stamp();
}
