<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { delayBand, etaFrom, mapsUrl } from "../lib/format";
  import { clock } from "../lib/time.svelte";
  import type { CardProps, CommuteData } from "./types";
  import { pick } from "./types";

  let { view, stale, hero }: CardProps = $props();
  const commute = $derived(pick<CommuteData>(view, "commute"));
  const routes = $derived(commute?.routes ?? []);
  const duringRush = $derived(commute?.duringRush ?? false);
  // Past a handful of stops the two-line-per-route layout overflows a normal
  // cell — collapse each route to one line so every destination still shows.
  const compact = $derived(routes.length > 3 && !hero);
</script>

<Card accent="generic" {stale} {hero}>
  {#if routes.length === 0}
    <span class="waiting"
      >Add a destination in Settings › Cards & layout › Card options.</span
    >
  {:else}
    <span class="eyebrow">Commute</span>
    <ul class="routes" class:emphasized={duringRush} class:compact>
      {#each routes as route (route.label)}
        <li class="route">
          <a
            class="label"
            href={mapsUrl(route.address)}
            target="_blank"
            rel="noopener"
            aria-label="Directions to {route.label}"
          >
            {route.label}
          </a>
          <span class="times">
            <span class="minutes" data-band={delayBand(route.delayMinutes)}>
              {route.minutes}<i>min</i>
              {#if route.delayMinutes > 0}<i class="delay"
                  >+{route.delayMinutes}</i
                >{/if}
            </span>
            <span class="eta">→ {etaFrom(clock.now, route.minutes)}</span>
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</Card>

<style>
  .eyebrow {
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .routes {
    display: flex;
    flex-direction: column;
    margin-top: var(--space-2);
    list-style: none;
  }
  .route {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-2) 0;
  }
  /* Compact: one line per route — label · minutes · arrival, side by side. */
  .routes.compact .route {
    align-items: baseline;
    gap: var(--space-3);
    padding: var(--space-label) 0;
  }
  .routes.compact .times {
    flex-direction: row;
    align-items: baseline;
    gap: var(--space-2);
  }
  .routes.compact .minutes {
    font-size: var(--type-sm);
  }
  .routes.compact .label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* A hairline between each place/time pair — the same divider language as
     Weather's headline/metrics rule, so the two cards read as one system. */
  .route + .route {
    border-top: 1px solid color-mix(in srgb, var(--on-card) 25%, transparent);
  }
  .label {
    font-size: var(--type-sm);
    font-weight: var(--weight-label);
    color: var(--on-card-soft);
    text-decoration: none;
    text-underline-offset: 0.2em;
    /* Its own visual lane, distinct from the times column on the right. */
    flex: 1;
    min-width: 0;
  }
  .label:hover,
  .label:focus-visible {
    text-decoration: underline;
    color: var(--on-card);
  }
  .times {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
  }
  .eta {
    font-size: var(--type-caption);
    color: var(--on-card-faint);
  }
  .minutes {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: var(--type-md);
    white-space: nowrap;
  }
  .minutes i {
    font-style: normal;
    font-size: 0.65em;
    color: var(--on-card-faint);
    margin-left: 0.2em;
  }
  .minutes .delay {
    color: var(--on-card-faint);
  }
  /* During the configured rush window, the routes lead with the one that
     needs attention (sorted server-side) and read larger — the legacy app's
     "primary routes get the large ETA treatment" during the commute window. */
  .routes.emphasized .minutes {
    font-size: var(--type-lg);
  }
  .routes.emphasized .label {
    font-size: var(--type-md);
  }
  /* Ported from the legacy app's C_SEVERITY_MODERATE/HEAVY, which alias
     C_ACCENT_GOLD/RED — the same severity colors an alert or an AC card
     used there. */
  .minutes[data-band="slow"] .delay {
    color: var(--accent-gold);
  }
  .minutes[data-band="heavy"] .delay {
    color: var(--accent-red);
  }
  .waiting {
    color: var(--on-card-faint);
    font-size: var(--type-sm);
  }
</style>
