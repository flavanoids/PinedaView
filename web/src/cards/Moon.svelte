<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import MoonGlyph from "../components/MoonGlyph.svelte";
  import type { CardProps, MoonData } from "./types";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const moon = $derived(pick<MoonData>(view, "moon"));
</script>

<Card accent="moon" {stale} {hero} fill={hero}>
  {#if moon}
    {#if hero}
      <div class="hero-moon">
        <div class="hero-eyebrow">Lunar Phase</div>
        <div class="hero-body">
          <div class="hero-glyph-frame">
            <MoonGlyph
              phase={moon.phase ?? 0}
              illumination={moon.illumination ?? 0}
            />
          </div>
          <div class="hero-info">
            <span class="hero-name">{moon.name ?? "Moon"}</span>
            <div class="hero-illumination">
              <span class="illum-val"
                >{Math.round(moon.illumination ?? 0)}%</span
              >
              <span class="illum-lbl">Illuminated</span>
            </div>
            <div class="phase-tag">
              {(moon.phase ?? 0) < 0.5 ? "Waxing" : "Waning"}
            </div>
          </div>
        </div>
      </div>
    {:else}
      <span class="glyph-frame">
        <MoonGlyph
          phase={moon.phase ?? 0}
          illumination={moon.illumination ?? 0}
        />
      </span>
      <span class="name">{moon.name ?? "Moon"}</span>
      <span class="sub">{Math.round(moon.illumination ?? 0)}% illuminated</span>
    {/if}
  {:else}
    <span class="waiting">…</span>
  {/if}
</Card>

<style>
  .glyph-frame {
    display: block;
    width: var(--type-xl);
    height: var(--type-xl);
  }
  .name {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    margin-top: var(--space-1);
  }
  .sub {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
  }
  .waiting {
    color: var(--on-card-faint);
  }

  /* Hero styling */
  .hero-moon {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    padding: var(--space-1) 0;
  }
  .hero-eyebrow {
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--on-card-soft);
    font-weight: var(--weight-label);
  }
  .hero-body {
    display: flex;
    align-items: center;
    gap: clamp(var(--space-4), 5cqi, var(--space-6));
    flex: 1;
  }
  .hero-glyph-frame {
    width: clamp(90px, 32cqi, 190px);
    height: clamp(90px, 32cqi, 190px);
    flex-shrink: 0;
  }
  .hero-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .hero-name {
    font-family: var(--font-display);
    font-size: clamp(var(--type-xl), 7cqi, var(--type-hero));
    font-weight: var(--weight-display);
    line-height: 1.1;
    letter-spacing: -0.02em;
    color: var(--on-card);
  }
  .hero-illumination {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }
  .illum-val {
    font-family: var(--font-display);
    font-size: var(--type-xl);
    font-weight: var(--weight-display);
    color: var(--on-card);
  }
  .illum-lbl {
    font-size: var(--type-sm);
    color: var(--on-card-soft);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .phase-tag {
    display: inline-flex;
    align-self: flex-start;
    padding: 3px 10px;
    border-radius: var(--radius-pill);
    background: color-mix(in srgb, var(--on-card) 12%, transparent);
    font-size: var(--type-caption);
    font-weight: 500;
    color: var(--on-card-soft);
  }
</style>
