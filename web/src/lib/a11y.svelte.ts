// SPDX-License-Identifier: Apache-2.0
/**
 * Per-device accessibility preferences. Stored in localStorage and applied as
 * `data-*` attributes on <html>; the design tokens key off them. The OS
 * settings (`prefers-reduced-motion`, `prefers-contrast`,
 * `prefers-reduced-transparency`) remain a floor — turning a toggle off here
 * never overrides them.
 */
import { refreshDisplayScale } from "./display.svelte";
import { readLocal, writeLocal } from "./storage";

export const KEY = "pineda.a11y";

export interface A11yPrefs {
  reduceTransparency: boolean;
  largerText: boolean;
  highContrast: boolean;
  announceUpdates: boolean;
}

const DEFAULTS: A11yPrefs = {
  reduceTransparency: false,
  largerText: false,
  highContrast: false,
  announceUpdates: false,
};

export const a11y = $state<A11yPrefs>({ ...DEFAULTS });

function apply(): void {
  const root = document.documentElement;
  root.toggleAttribute("data-reduce-transparency", a11y.reduceTransparency);
  root.toggleAttribute("data-large-text", a11y.largerText);
  root.toggleAttribute("data-high-contrast", a11y.highContrast);
  // "Larger text" is applied as a bump to --ui-scale, not its own type scale.
  refreshDisplayScale();
}

export function initA11y(): void {
  let saved: Partial<A11yPrefs> = {};
  try {
    saved = JSON.parse(readLocal(KEY) ?? "{}") as Partial<A11yPrefs>;
  } catch {
    saved = {};
  }
  // Write each key once, straight to its resolved value — assigning DEFAULTS
  // and then `saved` on top (two Object.assign passes) briefly toggled a
  // changed key back to its default before the override landed, and with an
  // effect already subscribed to it, that transient flip alone was enough to
  // re-trigger the effect and hit Svelte's effect_update_depth_exceeded.
  const merged: A11yPrefs = { ...DEFAULTS, ...saved };
  let key: keyof A11yPrefs;
  for (key in merged) {
    a11y[key] = merged[key];
  }
  apply();
}

export function setA11y<K extends keyof A11yPrefs>(
  key: K,
  value: A11yPrefs[K],
): void {
  a11y[key] = value;
  writeLocal(KEY, JSON.stringify(a11y));
  apply();
}
