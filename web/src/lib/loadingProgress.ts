// SPDX-License-Identifier: Apache-2.0
/**
 * The Now Playing card's "getting that ready" panel. Antigua only knows
 * coarse stages (finding the song → starting the speaker), so the bar eases
 * toward each stage's ceiling and never quite reaches it: it keeps moving
 * while there's real work going on, and only jumps to full when the music
 * actually starts.
 */

export interface Loading {
  stage: "finding" | "starting" | "failed";
  /** ISO start of the whole wait (first report). */
  since: string;
  /** ISO start of the current stage. */
  stageAt: string;
  text?: string;
  title?: string;
  artist?: string;
}

const STAGES = {
  finding: { from: 4, to: 45, tau: 5 },
  starting: { from: 45, to: 97, tau: 7 },
} as const;

const secondsSince = (iso: string, now: Date): number =>
  iso ? Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000) : 0;

/** 0–100: the stage's floor plus an easing share of what's left to its cap. */
export function loadingPercent(l: Loading, now: Date): number {
  if (l.stage === "failed") return 100;
  const s = STAGES[l.stage] ?? STAGES.finding;
  const t = secondsSince(l.stageAt, now);
  return Math.round(s.from + (s.to - s.from) * (1 - Math.exp(-t / s.tau)));
}

/** Seconds since the request started, for "12s" under the bar. */
export function loadingElapsed(l: Loading, now: Date): number {
  return Math.floor(secondsSince(l.since, now));
}

/** The small line on top: what Antigua is doing. */
export function loadingEyebrow(l: Loading): string {
  if (l.stage === "failed") return "Antigua";
  return l.stage === "starting" ? "Getting it ready" : "Antigua is looking";
}

/** The big line: what's being fetched. */
export function loadingHeadline(l: Loading): string {
  if (l.stage === "failed") return "That didn't start";
  if (l.stage === "starting") return l.title || "Your music";
  return l.title ? `“${l.title}”` : (l.text ?? "Looking that up…");
}

/** The friendly line under it, more reassuring the longer it goes. */
export function loadingDetail(l: Loading, now: Date): string {
  if (l.stage === "failed")
    return l.text ?? "Something went wrong. Try asking again.";
  const total = loadingElapsed(l, now);
  if (l.stage === "finding")
    return total < 6
      ? "Searching Apple Music for the best match…"
      : "Still searching. Apple Music is a little slow right now.";
  const t = secondsSince(l.stageAt, now);
  if (t < 3) return "Found it! Asking Apple Music for the stream…";
  if (t < 8) return "Connecting to the kitchen speaker…";
  if (t < 15) return "Almost there. The speaker is buffering.";
  if (t < 35) return "Apple Music is slow to answer right now. Still trying…";
  return "This one's taking a while. Hang tight, or ask me again.";
}
