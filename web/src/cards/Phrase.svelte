<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import Cycler from "../components/Cycler.svelte";
  import { fitText } from "../lib/fitText";
  import type { CardProps, DailyContentData } from "./types";
  import { pick } from "./types";
  import { paced } from "../lib/prefs.svelte";

  let { view, stale, hero }: CardProps = $props();
  const word = $derived(pick<DailyContentData>(view, "dailyContent")?.word);
  const languages = $derived(word?.languages ?? []);

  // Legacy PHRASE_CYCLE_SECONDS was 15s.
  const CYCLE_MS = 15_000;
</script>

<Card accent="phrase" {stale} {hero} fill>
  {#if languages.length}
    <Cycler count={languages.length} intervalMs={paced(CYCLE_MS)} fill>
      {#snippet item(i)}
        {@const lang = languages[i]}
        {#if lang}
          <!-- Sized per phrase: a short one grows to fill the tile, a long
               one shrinks until it and its translation fit. -->
          <div
            class="fit"
            class:hero-fit={hero}
            use:fitText={{
              min: hero ? 1.3 : 0.9,
              max: hero ? 4.2 : 3,
              maxOfWidth: hero ? 0.2 : 0.13,
              key: `${lang.text}|${word?.english}`,
            }}
          >
            {#if hero}
              <span class="lang-tag">{lang.code ?? "Phrase of the day"}</span>
            {/if}
            <span
              class="term"
              lang={lang.code}
              dir={lang.dir === "rtl" ? "rtl" : null}>{lang.text}</span
            >
            {#if hero && lang.pron}
              <span class="pron">/{lang.pron}/</span>
            {/if}
            <span class="en">{word?.english}</span>
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
    /* Size containment: fits the row's height rather than growing it (see
       Affirmation's .fit), with a floor for a card alone in its row. */
    container-type: size;
    min-height: 30cqi;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.4em;
    overflow: hidden;
  }
  /* A panel that fills its screen sets the row's height, which on a tall
     screen is less than this floor: fit the row instead. */
  :global(.stage.fills) .fit {
    min-height: 0;
  }
  .lang-tag {
    font-size: max(0.45em, var(--type-caption));
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--on-card-soft);
    font-weight: var(--weight-label);
  }
  .term {
    font-size: 1em;
    font-weight: var(--weight-label);
    line-height: 1.12;
    text-wrap: balance;
  }
  .pron {
    font-size: max(0.45em, var(--type-sm));
    font-style: italic;
    color: var(--accent);
  }
  .en {
    /* Tracks the phrase, but never below readable. */
    font-size: max(0.55em, var(--type-sm));
    line-height: 1.3;
    text-wrap: balance;
    color: var(--on-card-soft);
  }
  .waiting {
    color: var(--on-card-faint);
  }
</style>
