<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The moon card's crescent icon, split out so a mini-card cluster (see
  cards/MoonClimate.svelte) can reuse the same glyph at a smaller size
  without duplicating the phase geometry.
-->
<script lang="ts">
  interface Props {
    phase: number;
    illumination: number;
  }
  let { phase, illumination }: Props = $props();

  const R = 20; // svg units, viewBox is 48x48 centred on 24,24

  // A real crescent/gibbous shape, sized off the actual illumination
  // percent — not one of 8 stock emoji glyphs, whose nearest bucket can
  // land a half-moon icon next to a "35% illuminated" label. The disk's lit
  // region is the lens between two arcs of the same top-to-bottom span: the
  // full-radius limb on the lit side, and a terminator ellipse whose
  // horizontal radius shrinks to 0 at the quarters and grows back out on
  // the far side past them (see the phase math in providers/moon.py).
  const litPath = $derived.by(() => {
    const k = Math.min(1, Math.max(0, illumination / 100));
    const waxing = phase < 0.5;
    const rx = R * Math.abs(1 - 2 * k);
    const litRight = waxing;
    const innerRight = k < 0.5 ? litRight : !litRight;
    const outerSweep = litRight ? 1 : 0;
    const innerSweep = innerRight ? 0 : 1;
    return `M 24,${24 - R} A ${R},${R} 0 0 ${outerSweep} 24,${24 + R} A ${rx},${R} 0 0 ${innerSweep} 24,${24 - R} Z`;
  });
</script>

<svg viewBox="0 0 48 48" class="glyph" aria-hidden="true">
  <circle cx="24" cy="24" r={R} class="disk" />
  <path d={litPath} class="lit" />
  <circle cx="24" cy="24" r={R} class="ring" />
</svg>

<style>
  .glyph {
    width: 100%;
    height: 100%;
  }
  .disk {
    fill: color-mix(in srgb, var(--on-card) 14%, transparent);
  }
  .lit {
    fill: color-mix(in srgb, var(--accent-gold) 65%, var(--on-card) 35%);
  }
  .ring {
    fill: none;
    stroke: color-mix(in srgb, var(--on-card) 22%, transparent);
    stroke-width: 1;
  }
  /* Dark themes (see applyTheme's stage-luminance check) put the card on a
     near-black background — lean into it and let the lit face read bright
     and moonlit instead of the same muted gold as on a pale theme. */
  :global(:root[data-dark]) .lit {
    fill: color-mix(in srgb, white 85%, var(--accent-gold) 15%);
  }
  :global(:root[data-dark]) .glyph {
    filter: drop-shadow(0 0 8px color-mix(in srgb, white 45%, transparent));
  }
</style>
