// SPDX-License-Identifier: Apache-2.0
/**
 * What this screen plays when a kitchen timer runs out (Settings → Timers).
 * Per screen, in localStorage like the accessibility prefs: a wall tablet by
 * the stove wants a bell, the bedroom one silence. Synthesised with Web
 * Audio — no sound files to ship. A browser that hasn't been touched since
 * it loaded may refuse to play (autoplay rules); that fails quietly.
 */
import type { Timer } from "@pinedaview/protocol";

import { readLocal, writeLocal } from "./storage";

export const KEY = "pineda.timerSound";

export type TimerSound = "chime" | "bell" | "beep" | "off";

const SOUNDS: TimerSound[] = ["chime", "bell", "beep", "off"];

function saved(): TimerSound {
  const value = readLocal(KEY) as TimerSound | null;
  return value && SOUNDS.includes(value) ? value : "chime";
}

export const timerSound = $state<{ choice: TimerSound }>({ choice: saved() });

export function setTimerSound(choice: TimerSound): void {
  timerSound.choice = choice;
  writeLocal(KEY, choice);
}

// [frequency Hz, start s, length s] notes for each sound.
const NOTES: Record<Exclude<TimerSound, "off">, [number, number, number][]> = {
  chime: [
    [880, 0, 0.9],
    [1318.5, 0.18, 1.1],
    [880, 1.4, 0.9],
    [1318.5, 1.58, 1.1],
  ],
  bell: [
    [523.25, 0, 2.2],
    [1046.5, 0, 1.6],
    [523.25, 1.6, 2.2],
    [1046.5, 1.6, 1.6],
  ],
  beep: [
    [1000, 0, 0.18],
    [1000, 0.3, 0.18],
    [1000, 0.6, 0.18],
    [1000, 1.2, 0.18],
    [1000, 1.5, 0.18],
    [1000, 1.8, 0.18],
  ],
};

let audio: AudioContext | undefined;

/** Play `sound` once (also the Settings preview). */
export function playTimerSound(sound: TimerSound = timerSound.choice): void {
  if (sound === "off" || typeof AudioContext === "undefined") return;
  try {
    audio ??= new AudioContext();
    void audio.resume();
    const t0 = audio.currentTime + 0.05;
    for (const [freq, at, length] of NOTES[sound]) {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = sound === "beep" ? "square" : "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, t0 + at);
      gain.gain.exponentialRampToValueAtTime(
        sound === "beep" ? 0.12 : 0.3,
        t0 + at + 0.01,
      );
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + at + length);
      osc.connect(gain).connect(audio.destination);
      osc.start(t0 + at);
      osc.stop(t0 + at + length + 0.05);
    }
  } catch {
    /* no audio here — the timer card still shows it's done */
  }
}

let known = new Map<string, number>();

/**
 * Called with the timers on screen each time they change. One that was here
 * and is now gone at (or past) its due time ran out rather than being
 * cancelled, so play the chime — once, however many finished together.
 * Alarms and reminders take over the screen instead and aren't chimed.
 */
export function chimeForFinishedTimers(
  timers: unknown,
  now: number = Date.now(),
): boolean {
  const list = Array.isArray(timers) ? (timers as Timer[]) : [];
  const current = new Map(
    list
      .filter((t) => (t.kind ?? "timer") === "timer")
      .map((t) => [t.id, Date.parse(t.fires_at)] as const),
  );
  let finished = false;
  for (const [id, firesAt] of known) {
    if (!current.has(id) && now >= firesAt - 2_000) finished = true;
  }
  known = current;
  if (finished) playTimerSound();
  return finished;
}
