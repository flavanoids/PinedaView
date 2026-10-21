// SPDX-License-Identifier: Apache-2.0
import { createClient } from "@pinedaview/protocol";

import { platform } from "./platform.svelte";

/** Drives the "video" card's on/off cycle: hero-sized and visible for
    `onSeconds`, then hidden (the usual cards show) for `offSeconds`, forever.
    A module-level singleton so Stage (which sizes/filters the grid) and
    Video.svelte (which mounts/unmounts the actual player) agree on phase
    without threading a prop through the card list. */
class VideoHeroCycle {
  active = $state(false);

  #client = createClient(import.meta.env.VITE_API_URL ?? "");
  #timer: ReturnType<typeof setTimeout> | undefined;
  #onMs = 30_000;
  #offMs = 180_000;
  #running = false;

  /** Idempotent — call every time the "video" card is present; a second call
      while already running is a no-op so remounts don't restart the phase. */
  start(): void {
    if (this.#running) return;
    this.#running = true;
    void this.#client.getCardSettings("video").then((settings) => {
      if (!this.#running) return; // stopped while the fetch was in flight
      // Measured on real hardware: a live stream is near-certainly VP9, and a
      // Pi 4's decoder block only takes H.264, so this is ~2 cores of pure
      // software decode there — on a device that already runs close to its
      // limit. Never cycle on a Pi unless someone explicitly opts in.
      if (platform.isPi && !settings.values.allowOnPi) return;
      const onSeconds = Number(settings.values.onSeconds ?? 30);
      const offSeconds = Number(settings.values.offSeconds ?? 180);
      this.#onMs =
        (Number.isFinite(onSeconds) && onSeconds > 0 ? onSeconds : 30) * 1000;
      this.#offMs =
        (Number.isFinite(offSeconds) && offSeconds > 0 ? offSeconds : 180) *
        1000;
      this.#scheduleOff();
    });
  }

  /** Called once the "video" card leaves the stack. */
  stop(): void {
    this.#running = false;
    this.active = false;
    clearTimeout(this.#timer);
  }

  #scheduleOff(): void {
    this.active = false;
    this.#timer = setTimeout(() => this.#scheduleOn(), this.#offMs);
  }
  #scheduleOn(): void {
    this.active = true;
    this.#timer = setTimeout(() => this.#scheduleOff(), this.#onMs);
  }
}

export const videoHero = new VideoHeroCycle();
