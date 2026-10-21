// SPDX-License-Identifier: Apache-2.0
/**
 * Ambient dashboards sit untouched for hours. After a minute with no input — or
 * whenever the tab is hidden — stamp `data-idle="true"` so CSS can freeze
 * decorative animation and the device can clock down. Any pointer / key / touch
 * event or the tab becoming visible wakes it instantly.
 */
const IDLE_AFTER_MS = 60_000;

export const idle = $state<{ active: boolean }>({ active: false });

let timer: ReturnType<typeof setTimeout> | undefined;

function set(active: boolean): void {
  if (active === idle.active) return;
  idle.active = active;
  document.documentElement.dataset.idle = String(active);
}

function poke(): void {
  set(false);
  clearTimeout(timer);
  if (document.visibilityState === "visible") {
    timer = setTimeout(() => set(true), IDLE_AFTER_MS);
  }
}

export function initIdle(): () => void {
  const events = [
    "pointerdown",
    "pointermove",
    "keydown",
    "touchstart",
    "wheel",
  ];
  const onVisibility = (): void => {
    if (document.visibilityState === "hidden") set(true);
    else poke();
  };
  for (const e of events) window.addEventListener(e, poke, { passive: true });
  document.addEventListener("visibilitychange", onVisibility);
  poke();

  return () => {
    clearTimeout(timer);
    for (const e of events) window.removeEventListener(e, poke);
    document.removeEventListener("visibilitychange", onVisibility);
  };
}
