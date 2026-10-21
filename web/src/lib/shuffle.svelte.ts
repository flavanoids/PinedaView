// SPDX-License-Identifier: Apache-2.0
import { edit } from "./edit.svelte";
import { prefs } from "./prefs.svelte";

const QUEUE_KEY = "pineda:shuffle-queue-index";
const EXPAND_MS = 450;
const CONTRACT_MS = 400;
const REST_MS = 1000;

class DynamicShuffleController {
  /** The card id currently expanded to the hero position, or null. */
  expandedCard = $state<string | null>(null);

  /** Current phase of the dynamic hero motion. */
  phase = $state<"idle" | "expanding" | "dwelling" | "contracting">("idle");

  /** Whether the shuffle engine is actively running. */
  active = $state(false);

  #cardIds: string[] = [];
  #queueIndex = 0;
  #timer: ReturnType<typeof setTimeout> | undefined;
  #paused = false;
  #userInteractingUntil = 0;

  constructor() {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(QUEUE_KEY);
        if (saved) this.#queueIndex = parseInt(saved, 10) || 0;
      } catch {
        // LocalStorage unavailable in private mode or SSR
      }
      this.#setupInteractionListeners();
    }
  }

  get queueIndex(): number {
    return this.#queueIndex;
  }

  /** Start or update the dynamic shuffle queue with the currently visible grid cards. */
  start(cardIds: string[]): void {
    const valid = cardIds.filter((id) => id !== "photo" && id !== "video");
    this.#cardIds = valid;

    if (!prefs.dynamic_shuffle || valid.length === 0 || edit.active) {
      this.stop();
      return;
    }

    if (this.active) return;
    this.active = true;
    this.#paused = false;
    this.#scheduleNextCard(REST_MS);
  }

  /** Stop the shuffle engine and return any expanded card back to its slot. */
  stop(): void {
    clearTimeout(this.#timer);
    this.active = false;
    this.phase = "idle";
    this.expandedCard = null;
  }

  /** Temporarily pause the shuffle (e.g. during user touch or settings open). */
  pause(): void {
    this.#paused = true;
    clearTimeout(this.#timer);
  }

  /** Resume the shuffle after a pause. */
  resume(): void {
    if (!this.#paused || !this.active) return;
    this.#paused = false;
    if (this.phase === "dwelling") {
      // Finish out current card's dwell time
      const dwellMs = Math.max(5000, (prefs.shuffle_hold_s ?? 15) * 1000);
      this.#timer = setTimeout(() => this.#contract(), dwellMs);
    } else {
      this.#scheduleNextCard(REST_MS);
    }
  }

  #scheduleNextCard(delayMs: number): void {
    clearTimeout(this.#timer);
    if (!this.active || this.#paused || this.#cardIds.length === 0) return;

    this.#timer = setTimeout(() => {
      if (!this.active || this.#paused || this.#cardIds.length === 0) return;
      if (Date.now() < this.#userInteractingUntil) {
        this.#scheduleNextCard(1500);
        return;
      }

      const nextId = this.#cardIds[this.#queueIndex % this.#cardIds.length];
      if (!nextId) return;

      this.expandedCard = nextId;
      this.phase = "expanding";

      // Allow FLIP expand animation to complete
      this.#timer = setTimeout(() => {
        if (!this.active) return;
        this.phase = "dwelling";
        const dwellMs = Math.max(5000, (prefs.shuffle_hold_s ?? 15) * 1000);

        this.#timer = setTimeout(() => {
          this.#contract();
        }, dwellMs);
      }, EXPAND_MS);
    }, delayMs);
  }

  #contract(): void {
    if (!this.active) return;
    this.phase = "contracting";

    this.#timer = setTimeout(() => {
      this.phase = "idle";
      this.expandedCard = null;
      this.#advanceQueue();
      this.#scheduleNextCard(REST_MS);
    }, CONTRACT_MS);
  }

  #advanceQueue(): void {
    this.#queueIndex += 1;
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(QUEUE_KEY, String(this.#queueIndex));
      } catch {
        // Ignore storage errors
      }
    }
  }

  #setupInteractionListeners(): void {
    const onInteract = (): void => {
      // Pause shuffling during touch/pointer interactions, wait 4s after last interaction
      this.#userInteractingUntil = Date.now() + 4000;
    };
    window.addEventListener("pointerdown", onInteract, { passive: true });
    window.addEventListener("keydown", onInteract, { passive: true });
  }
}

export const shuffle = new DynamicShuffleController();
