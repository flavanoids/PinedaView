<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import Cycler from "../components/Cycler.svelte";
  import { fitText } from "../lib/fitText";
  import type { CardProps, DailyContentData } from "./types";
  import { pick } from "./types";
  import { paced } from "../lib/prefs.svelte";

  let { view, stale, hero }: CardProps = $props();
  const daily = $derived(pick<DailyContentData>(view, "dailyContent"));
  const quotes = $derived(
    daily?.affirmations?.length
      ? daily.affirmations
      : daily?.affirmation
        ? [daily.affirmation]
        : [],
  );
  // Longer dwell than the phrase card — a quote takes longer to read.
  const CYCLE_MS = 27_000;

  // The card adds its own curly quotes, so drop any the text came with.
  const unquoted = (text: string) =>
    text.trim().replace(/^["“”']+|["“”']+$/g, "");
</script>

<Card accent="affirmation" {stale} {hero} fill>
  {#if quotes.length}
    <Cycler
      count={quotes.length}
      intervalMs={paced(CYCLE_MS)}
      dots={false}
      fill
    >
      {#snippet item(i)}
        {@const q = quotes[i]}
        {#if q}
          <!-- Sized per quote: "When they go low, we go high." fills the
               tile; a three-sentence one shrinks until the whole quote and
               its author fit — no clamping, nothing cut off. -->
          <div
            class="fit"
            use:fitText={{ min: 0.8, max: 2.6, maxOfWidth: 0.1, key: q.text }}
          >
            <p class="quote">“{unquoted(q.text ?? "")}”</p>
            <p class="by">
              — {q.author ?? "Unknown"}{#if q.year}, {q.year}{/if}
            </p>
          </div>
        {/if}
      {/snippet}
    </Cycler>
  {:else}
    <span class="waiting">…</span>
  {/if}
</Card>

<style>
  .fit {
    flex: 1;
    /* Size containment: the quote never grows its row (on tablets and phones
       rows are content-sized, so fitted text would just make the card
       taller) — it fits the height the row already has, with a floor for a
       card that's alone in its row. */
    container-type: size;
    min-height: 50cqi;
    display: flex;
    flex-direction: column;
    gap: 0.6em;
    overflow: hidden;
  }
  /* The quote centred in the space above the author, who sits at the
     bottom. Two inks from the theme's own quote-card color (applyTheme):
     a near-neutral one for the words, the card's hue for the author. */
  .quote {
    margin-block: auto;
    font-size: 1em;
    font-weight: var(--weight-body);
    font-style: italic;
    line-height: 1.32;
    text-wrap: pretty;
    color: var(--quote-ink, var(--on-card));
  }
  .by {
    flex: none;
    font-size: max(0.5em, var(--type-caption));
    font-weight: var(--weight-label);
    color: var(--quote-by, var(--on-card-soft));
  }
  .waiting {
    color: var(--on-card-faint);
  }
</style>
