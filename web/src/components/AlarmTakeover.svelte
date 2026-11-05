<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { fade, scale } from "svelte/transition";
  import { createClient, type components } from "@pinedaview/protocol";

  import { formatClock } from "../lib/format";

  type Takeover = components["schemas"]["Takeover"];
  type Alarm = components["schemas"]["AlarmTakeover"];

  interface Props {
    takeover: Takeover;
  }
  let { takeover }: Props = $props();

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  const card = $derived(takeover.card as Alarm);
  const at = $derived(formatClock(new Date(card.fires_at)));

  // Any screen with a touchscreen can turn it off; the kiosk can't, so the
  // phone menu has a button for it too.
  function dismiss(): void {
    void client.clearTakeover().catch(() => {});
  }
</script>

<button
  type="button"
  class="alarm"
  onclick={dismiss}
  aria-live="assertive"
  in:scale={{ start: 1.04, duration: 340 }}
  out:fade={{ duration: 200 }}
>
  <span class="glow" aria-hidden="true"></span>
  <span class="label">{card.label}</span>
  <span class="time">{at.time}<small>{at.ampm}</small></span>
  <span class="hint">Tap here or use the menu on your phone to turn it off</span
  >
</button>

<style>
  .alarm {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    width: 100%;
    border: 0;
    padding: calc(var(--space-5) + var(--frame-y, 0px))
      calc(var(--space-5) + var(--frame-x, 0px));
    background: var(--stage);
    color: var(--on-stage);
    font: inherit;
    cursor: pointer;
    overflow: hidden;
  }
  /* The one moving thing: a slow breath of the theme's accent behind the
     time. Opacity only, so the Pi composites it without repainting. */
  .glow {
    position: absolute;
    inset: 0;
    background: radial-gradient(
      closest-side,
      color-mix(in srgb, var(--accent) 38%, transparent),
      transparent
    );
    animation: breathe 2.4s ease-in-out infinite alternate;
  }
  @keyframes breathe {
    from {
      opacity: 0.35;
    }
    to {
      opacity: 1;
    }
  }
  .label,
  .time,
  .hint {
    position: relative;
  }
  .label {
    font-family: var(--font-display);
    font-size: var(--type-lg);
    font-weight: var(--weight-label);
  }
  .time {
    font-family: var(--font-clock);
    font-size: calc(var(--type-hero) * 1.6);
    font-variation-settings:
      "SOFT" 100,
      "opsz" 144;
    line-height: 0.9;
    letter-spacing: -0.03em;
  }
  .time small {
    margin-left: 0.12em;
    font-size: 0.28em;
    letter-spacing: 0;
  }
  .hint {
    color: var(--on-stage-soft);
    font-size: var(--type-sm);
  }
  :global(:root[data-motion="lite"]) .glow,
  :global(:root[data-reduce-motion="true"]) .glow {
    animation: none;
    opacity: 0.8;
  }
  @media (prefers-reduced-motion: reduce) {
    .glow {
      animation: none;
      opacity: 0.8;
    }
  }
</style>
