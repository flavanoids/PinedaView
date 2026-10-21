// SPDX-License-Identifier: Apache-2.0
import type { MotionTier } from "./tier.svelte";
import { readLocal, writeLocal } from "./storage";

export const STEPS = [
  "welcome",
  "location",
  "numbers",
  "look",
  "cards",
  "screen",
  "invite",
] as const;
export type Step = (typeof STEPS)[number];

export interface WizardDraft {
  location_query: string;
  location_label: string | null;
  units: "imperial" | "metric";
  theme: string;
  countdown_enabled: boolean;
  countdown_start: string;
  countdown_end: string;
  cards: string[];
  maps_key: string;
  device_name: string;
  tier: MotionTier | null;
}

const KEY = "pineda.wizard";

function fresh(): WizardDraft {
  return {
    location_query: "",
    location_label: null,
    units: "imperial",
    theme: "quiet_canvas",
    countdown_enabled: false,
    countdown_start: "07:30",
    countdown_end: "08:00",
    cards: ["clock", "weather", "radar", "affirmation", "traffic", "moon"],
    maps_key: "",
    device_name: "Screen",
    tier: null,
  };
}

export const wizard = $state<{ index: number; draft: WizardDraft }>(restore());

export const currentStep = (): Step => STEPS[wizard.index] ?? "welcome";
export const isLast = (): boolean => wizard.index >= STEPS.length - 1;

export function next(): void {
  wizard.index = Math.min(wizard.index + 1, STEPS.length - 1);
  persist();
}
export function back(): void {
  wizard.index = Math.max(wizard.index - 1, 0);
  persist();
}
export function reset(): void {
  wizard.index = 0;
  wizard.draft = fresh();
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export function persist(): void {
  writeLocal(KEY, JSON.stringify({ index: wizard.index, draft: wizard.draft }));
}

function restore(): { index: number; draft: WizardDraft } {
  const raw = readLocal(KEY);
  if (!raw) return { index: 0, draft: fresh() };
  try {
    const saved = JSON.parse(raw) as { index: number; draft: WizardDraft };
    const index = Math.min(Math.max(saved.index ?? 0, 0), STEPS.length - 1);
    return { index, draft: { ...fresh(), ...saved.draft } };
  } catch {
    return { index: 0, draft: fresh() };
  }
}
