<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { SCREEN_COLOURS } from "../lib/screenColours";

  interface Props {
    brightness: number;
    blackout: boolean;
    identifyAt: number;
    /** The screen's name and colour, shown big while it's being found. */
    name?: string;
    colour?: string | null;
  }
  let {
    brightness,
    blackout,
    identifyAt,
    name = "",
    colour = null,
  }: Props = $props();
  const tint = $derived((colour && SCREEN_COLOURS[colour]) || null);

  let flashing = $state(false);
  $effect(() => {
    if (identifyAt === 0) return;
    flashing = true;
    const id = setTimeout(() => (flashing = false), 2500);
    return () => clearTimeout(id);
  });

  const dim = $derived(blackout ? 0.97 : Math.max(0, 1 - brightness));
</script>

{#if dim > 0}
  <div class="dim" style:opacity={dim} aria-hidden="true"></div>
{/if}
{#if flashing}
  <div class="flash" style:background={tint} aria-hidden="true"></div>
  {#if tint && name}
    <div class="found" style:background={tint} role="status">{name}</div>
  {/if}
{/if}

<style>
  .dim {
    position: fixed;
    inset: 0;
    background: #000;
    pointer-events: none;
    transition: opacity var(--dur-mid) linear;
    z-index: 25;
  }
  .flash {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 30;
    animation: pulse 0.7s ease-in-out 3;
    background: var(--accent);
  }
  .found {
    position: fixed;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 31;
    padding: 0.4em 1.1em;
    border-radius: 0.5em;
    color: #fff;
    font-size: clamp(2rem, 9vmin, 6rem);
    font-weight: 700;
    pointer-events: none;
    box-shadow: 0 1rem 3rem rgb(0 0 0 / 0.35);
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 0;
    }
    50% {
      opacity: 0.55;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .flash {
      animation: none;
      opacity: 0.4;
    }
  }
</style>
