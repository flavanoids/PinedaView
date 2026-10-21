// SPDX-License-Identifier: Apache-2.0
import { platform } from "./platform.svelte";
import { readLocal, writeLocal } from "./storage";

export type MotionTier = "lite" | "standard" | "rich";
export type MotionChoice = "auto" | MotionTier;

export const MOTION_KEY = "pineda.motion";

type MemoryNavigator = Navigator & { deviceMemory?: number };

export const motion = $state<{
  tier: MotionTier;
  /** What the user picked in Accessibility: "auto" follows the device. */
  choice: MotionChoice;
  reduced: boolean;
  /** True while the device is on battery and low — animations drop to Lite
   * without discarding the user's chosen tier. */
  batterySaver: boolean;
}>({
  tier: "standard",
  choice: "auto",
  reduced: false,
  batterySaver: false,
});

/** The tier actually in force once battery saving is taken into account. */
export function effectiveTier(): MotionTier {
  return motion.batterySaver ? "lite" : motion.tier;
}

function prefersReducedMotion(): boolean {
  return (
    typeof matchMedia === "function" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** Pick a starting tier from what the device tells us about itself. */
export function detectMotionTier(): MotionTier {
  if (prefersReducedMotion()) return "lite";
  // A detected Raspberry Pi is a hard floor: its GPU is weaker than its core
  // count/RAM numbers suggest, and those are the only signals below this.
  if (platform.isPi) return "lite";
  const cores = navigator.hardwareConcurrency ?? 4;
  const memory = (navigator as MemoryNavigator).deviceMemory ?? 4;
  if (cores <= 4 || memory <= 2) return "lite";
  if (cores >= 8 && memory >= 8) return "rich";
  return "standard";
}

function stamp(): void {
  const root = document.documentElement;
  root.dataset.motion = effectiveTier();
  root.dataset.reduceMotion = String(motion.reduced);
}

interface BatteryLike {
  charging: boolean;
  level: number;
  addEventListener: (type: string, fn: () => void) => void;
}
type BatteryNavigator = Navigator & { getBattery?: () => Promise<BatteryLike> };

/** Drop to Lite when unplugged and under 25 %. Best-effort: the Battery API is
 * absent on iOS and desktop Firefox, in which case this is a no-op. */
export async function watchBattery(): Promise<void> {
  const getBattery = (navigator as BatteryNavigator).getBattery;
  if (typeof getBattery !== "function") return;
  let battery: BatteryLike;
  try {
    battery = await getBattery.call(navigator);
  } catch {
    return;
  }
  const sync = (): void => {
    const low = !battery.charging && battery.level <= 0.25;
    if (low !== motion.batterySaver) {
      motion.batterySaver = low;
      stamp();
    }
  };
  battery.addEventListener("levelchange", sync);
  battery.addEventListener("chargingchange", sync);
  sync();
}

export function initMotion(): void {
  motion.reduced = prefersReducedMotion();
  const saved = readLocal(MOTION_KEY) as MotionChoice | null;
  motion.choice =
    saved === "lite" || saved === "standard" || saved === "rich"
      ? saved
      : "auto";
  motion.tier = motion.choice === "auto" ? detectMotionTier() : motion.choice;
  stamp();
  void watchBattery();
}

/** Set the tier for this session without changing the saved Auto/… choice —
 * used by the setup wizard's benchmark. */
export function setMotionTier(tier: MotionTier): void {
  motion.tier = tier;
  stamp();
}

/** The Accessibility control: persist an explicit choice, or "auto". */
export function setMotionChoice(choice: MotionChoice): void {
  motion.choice = choice;
  motion.tier = choice === "auto" ? detectMotionTier() : choice;
  writeLocal(MOTION_KEY, choice);
  stamp();
}

const RANK: Record<MotionTier, number> = { lite: 0, standard: 1, rich: 2 };

/** Does the current tier meet `required` — e.g. a card's `tier.features.flip`? */
export function allows(required: MotionTier): boolean {
  return RANK[effectiveTier()] >= RANK[required];
}

/** Map a measured average frame time (ms) to a tier. 60fps ≈ 16.7ms. */
export function tierForFrameTime(avgMs: number): MotionTier {
  if (avgMs <= 20) return "rich";
  if (avgMs <= 34) return "standard";
  return "lite";
}

/**
 * Run a short animation and time the frames. Combined with the device hints,
 * the lower of the two verdicts wins. Used by the setup wizard's tier step.
 */
export async function benchmarkTier(frames = 24): Promise<MotionTier> {
  if (prefersReducedMotion() || typeof requestAnimationFrame !== "function") {
    return "lite";
  }
  const probe = document.createElement("div");
  probe.style.cssText =
    "position:fixed;top:-9999px;width:80px;height:80px;filter:blur(6px);will-change:transform";
  document.body.appendChild(probe);

  const samples: number[] = [];
  let last = performance.now();
  await new Promise<void>((resolve) => {
    function step(now: number): void {
      samples.push(now - last);
      last = now;
      probe.style.transform = `translate3d(${samples.length}px,0,0) rotate(${samples.length}deg)`;
      if (samples.length < frames) requestAnimationFrame(step);
      else resolve();
    }
    requestAnimationFrame(step);
  });
  probe.remove();

  const sorted = samples.slice(1).sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)] ?? 16;
  const measured = tierForFrameTime(median);
  return RANK[measured] < RANK[detectMotionTier()]
    ? measured
    : detectMotionTier();
}
