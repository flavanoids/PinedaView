<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { fade, fly } from "svelte/transition";
  import type { components } from "@pinedaview/protocol";

  import { fitText } from "../lib/fitText";
  import { stepLadder } from "../lib/stepLadder";

  type Takeover = components["schemas"]["Takeover"];
  type Recipe = components["schemas"]["RecipeTakeover"];

  interface Props {
    takeover: Takeover;
  }
  let { takeover }: Props = $props();

  // App shows a camera card with CameraTakeover instead.
  const card = $derived(takeover.card as Recipe);
  // A household guide (Antigua's howto) reads as one, not as a recipe.
  const guide = $derived(card.kind === "howto");
  // Steps once there's one being read, unless Antigua says otherwise.
  const stage = $derived(
    card.stage ?? (card.current_step != null ? "steps" : "ingredients"),
  );
  const current = $derived(
    Math.min(card.current_step ?? 0, Math.max(card.steps.length - 1, 0)),
  );
  const meta = $derived(
    [
      card.source,
      card.servings,
      card.total_min ? minutes(card.total_min) : "",
    ].filter(Boolean),
  );
  // Ingredient indexes count lines across the groups, in order.
  const groups = $derived.by(() => {
    let start = 0;
    return card.ingredients.map((g) => {
      const at = start;
      start += g.items.length;
      return { ...g, start: at };
    });
  });
  const lit = $derived(new Set(card.current_ingredients ?? []));
  const checked = $derived(new Set(card.checked ?? []));
  const skipped = $derived(new Set(card.skipped ?? []));
  const swaps = $derived(
    new Map((card.swaps ?? []).map((s) => [s.index, s.use])),
  );
  // Text identity, not object identity: every update is a fresh copy.
  const stepsKey = $derived(card.steps.join("\n"));
  // The bar drains over whatever time is left — a re-shown recipe or a
  // reconnect mid-way starts it part-drained, not full.
  const totalMs = $derived(
    Date.parse(takeover.expires_at) - Date.parse(takeover.shown_at),
  );
  const leftMs = $derived(
    Math.max(0, Date.parse(takeover.expires_at) - Date.now()),
  );

  // Moving between the ingredient list and the steps rearranges the whole
  // body, so it fades in rather than jumping.
  let body: HTMLDivElement | undefined = $state();
  let lastStage: string | undefined;
  $effect(() => {
    const now = stage;
    if (lastStage !== undefined && lastStage !== now && body) {
      body.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 320,
        easing: "ease-out",
      });
    }
    lastStage = now;
  });

  function minutes(n: number): string {
    if (n < 60) return `${n} min`;
    const h = Math.floor(n / 60);
    const m = n % 60;
    return m ? `${h} hr ${m} min` : `${h} hr`;
  }
</script>

<div
  class="takeover"
  data-stage={stage}
  role="dialog"
  aria-modal="true"
  aria-label={`${guide ? "How to" : "Recipe"}: ${card.title}`}
  in:fly={{ y: 24, duration: 320 }}
  out:fade={{ duration: 200 }}
>
  <header>
    <p class="kicker">{guide ? "How to" : "Recipe"}</p>
    <h1>{card.title}</h1>
    {#if meta.length}
      <p class="meta">
        {#each meta as part, i (i)}
          {#if i > 0}<span class="dot" aria-hidden="true">·</span>{/if}
          <span>{part}</span>
        {/each}
      </p>
    {/if}
  </header>

  <div class="body" bind:this={body}>
    <aside class="ingredients" class:reading={lit.size > 0}>
      <h2>{guide ? "You'll need" : "Ingredients"}</h2>
      <div
        class="fit"
        use:fitText={stage === "steps"
          ? { min: 0.7, max: 1.8, maxOfWidth: 0.09, key: card }
          : { min: 1.15, max: 2.65, maxOfWidth: 0.057, key: card }}
      >
        {#each groups as group, g (g)}
          {#if group.name}<h3>{group.name}</h3>{/if}
          <ul>
            {#each group.items as item, i (i)}
              {@const n = group.start + i}
              <li
                class:lit={lit.has(n)}
                class:checked={checked.has(n)}
                class:skipped={skipped.has(n) && !swaps.has(n)}
              >
                {#if swaps.has(n)}
                  <span class="was">{item}</span>
                  <span class="use">→ {swaps.get(n)}</span>
                {:else}
                  {item}
                {/if}
              </li>
            {/each}
          </ul>
        {/each}
      </div>
    </aside>

    {#if stage === "steps" && card.steps.length}
      <div class="ticks" aria-hidden="true">
        {#each card.steps as _, i (i)}
          <i class:done={i < current} class:now={i === current}></i>
        {/each}
      </div>
      <ol
        class="ladder"
        aria-label={`Step ${current + 1} of ${card.steps.length}`}
        use:stepLadder={{ current, key: stepsKey }}
      >
        {#each card.steps as step, i (i)}
          <li
            class="step"
            data-step
            data-role={i === current ? "current" : "side"}
            aria-current={i === current ? "step" : undefined}
          >
            <span class="n" aria-hidden="true">{i + 1}</span>
            <p>{step}</p>
          </li>
        {/each}
        <li class="end" data-end aria-hidden="true">Last step</li>
        <li class="step" data-measure data-role="side" aria-hidden="true">
          <span class="n"></span>
          <p></p>
        </li>
      </ol>
    {:else if card.steps.length}
      <div class="preview">
        <h2>First up</h2>
        <div
          class="fit"
          use:fitText={{
            min: 1.2,
            max: 2,
            maxOfWidth: 0.07,
            key: card.steps[0],
          }}
        >
          <div class="step">
            <span class="n" aria-hidden="true">1</span>
            <p>{card.steps[0]}</p>
          </div>
        </div>
        <p class="count">
          {card.steps.length} step{card.steps.length === 1 ? "" : "s"}
        </p>
      </div>
    {/if}
  </div>

  <footer>
    {#if card.caution}
      <p class="caution">{card.caution}</p>
    {/if}
    <span>Say “stop the display” to go back</span>
  </footer>
  <div
    class="drain"
    aria-hidden="true"
    style:--left={`${leftMs}ms`}
    style:--from={totalMs > 0 ? leftMs / totalMs : 1}
  ></div>
</div>

<style>
  /* Full screen, over everything but the dimmer (Overlay, z 25), so
     brightness and blackout still apply. Solid stage colour on every theme —
     including glass — so nothing behind competes with the text.

     Two arrangements, after what Antigua is reading: the ingredient list
     large with step 1 previewed beside it, then the steps as a ladder (the
     one before, the one being read, the one after) beside a narrow rail of
     ingredients that lights up what the current step uses. */
  .takeover {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
    gap: var(--space-4);
    padding: max(var(--space-5), env(safe-area-inset-top))
      calc(
        max(var(--space-5), env(safe-area-inset-right)) + var(--frame-x, 0px)
      )
      var(--space-3)
      calc(max(var(--space-5), env(safe-area-inset-left)) + var(--frame-x, 0px));
    background: var(--stage);
    color: var(--on-stage);
    font-family: var(--font-body);
  }
  @media (prefers-reduced-motion: no-preference) {
    .takeover {
      animation: rise var(--dur-mid) var(--ease-spring) both;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(2vh) scale(0.985);
    }
  }

  header {
    display: grid;
    gap: var(--space-1);
    min-width: 0;
  }
  .kicker {
    margin: 0;
    color: var(--accent);
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: var(--type-sm);
  }
  h1 {
    margin: 0;
    /* Big enough to read across the kitchen; two lines at most (titles
       arrive trimmed — no site name, no "Recipe"). */
    font-size: calc(
      clamp(2.25rem, min(3.4vw, 5.2vh), 4.25rem) * var(--ui-scale)
    );
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    padding-bottom: 0.06em;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    line-height: 1.08;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .meta {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0 var(--space-2);
    color: var(--on-stage-soft);
    font-size: var(--type-md);
    font-weight: var(--weight-label);
  }
  .dot {
    color: var(--accent);
  }
  /* While the steps are up the title steps back to one quiet line, giving
     the ladder the height. */
  [data-stage="steps"] .kicker,
  [data-stage="steps"] .meta {
    display: none;
  }
  [data-stage="steps"] h1 {
    font-size: calc(clamp(1.5rem, min(1.9vw, 3vh), 2.5rem) * var(--ui-scale));
    -webkit-line-clamp: 1;
    line-clamp: 1;
    opacity: 0.8;
  }

  .body {
    display: grid;
    grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr);
    gap: calc(var(--space-5) * 1.4);
    min-height: 0;
  }
  [data-stage="steps"] .body {
    grid-template-columns: minmax(0, 0.43fr) auto minmax(0, 1fr);
    gap: var(--space-5);
  }
  /* A portrait screen stacks them, ingredients first. */
  @media (orientation: portrait) {
    .body,
    [data-stage="steps"] .body {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: minmax(0, 0.8fr) minmax(0, 1fr);
    }
    [data-stage="steps"] .body {
      grid-template-rows: minmax(0, 0.32fr) minmax(0, 1fr);
    }
    .ticks {
      display: none;
    }
  }

  h2 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: var(--type-sm);
  }
  .fit {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  /* ── ingredients ── */
  .ingredients {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: 0;
    min-width: 0;
    padding: var(--space-5) var(--space-5) var(--space-4);
    border-radius: var(--radius-card);
    background: var(--card-generic);
    color: var(--on-card);
  }
  /* On the panel the accent can be the panel's own colour (halloween's
     orange), so its labels, bullets and highlight use the panel's text
     colour. */
  .ingredients h2 {
    opacity: 0.8;
  }
  [data-stage="steps"] .ingredients h2 {
    display: none;
  }
  .ingredients .fit {
    line-height: 1.28;
    columns: 12em;
    column-gap: 1.4em;
    column-fill: auto;
    /* Room for the highlight band inside the clip. */
    padding: 0.25em 0.45em 0;
    margin: -0.25em -0.45em 0;
  }
  [data-stage="steps"] .ingredients .fit {
    columns: 10em;
    column-gap: 1em;
  }
  h3 {
    margin: 0.65em 0 0.2em;
    font-size: 0.78em;
    font-weight: var(--weight-label);
    opacity: 0.75;
    break-after: avoid;
  }
  h3:first-child {
    margin-top: 0;
  }
  ul {
    position: relative;
    z-index: 0;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  ul li {
    position: relative;
    padding: 0.16em 0 0.16em 0.9em;
    break-inside: avoid;
  }
  ul li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.72em;
    width: 0.34em;
    height: 0.34em;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.55;
  }
  /* The line being checked or asked about, or used by the step being read:
     a band behind it (absolutely placed, so the fitted text never reflows)
     and the rest stepped back. */
  li.lit::after {
    content: "";
    position: absolute;
    inset: -0.06em -0.4em;
    z-index: -1;
    border-radius: 0.4em;
    background: color-mix(in srgb, var(--on-card) 20%, transparent);
    box-shadow: inset 0.2em 0 0 var(--on-card);
  }
  li.checked {
    opacity: 0.62;
  }
  .reading li {
    opacity: 0.5;
  }
  .reading li.lit {
    opacity: 1;
  }
  .skipped,
  .was {
    text-decoration: line-through;
    text-decoration-thickness: 0.08em;
  }
  li.skipped {
    opacity: 0.45;
  }
  .was {
    opacity: 0.65;
  }
  .use {
    font-weight: var(--weight-label);
  }

  /* ── step 1, beside the ingredient list ── */
  .preview {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-height: 0;
    min-width: 0;
  }
  .preview h2 {
    color: var(--accent);
  }
  .preview .fit {
    flex: 0 1 auto;
    max-height: 70%;
    opacity: 0.62;
  }
  .preview .step {
    grid-template-columns: 1.25em minmax(0, 1fr);
    gap: 0.45em;
  }
  .count {
    margin: auto 0 0;
    color: var(--on-stage-soft);
    font-size: var(--type-md);
  }

  /* ── progress: one dot per step ── */
  .ticks {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: clamp(0.25rem, 1.25vh, 1rem);
    min-height: 0;
    /* Room for the current dot's 1.5x, which the clip would cut. */
    padding: 0 calc(0.3rem * var(--ui-scale));
    overflow: hidden;
  }
  .ticks i {
    flex: none;
    width: calc(0.875rem * var(--ui-scale));
    height: calc(0.875rem * var(--ui-scale));
    border-radius: 50%;
    box-shadow: inset 0 0 0 0.19em
      color-mix(in srgb, var(--on-stage) 40%, transparent);
    transition:
      background-color var(--dur-mid),
      transform var(--dur-mid);
  }
  .ticks i.done {
    background: color-mix(in srgb, var(--on-stage) 40%, transparent);
    box-shadow: none;
  }
  .ticks i.now {
    background: var(--accent);
    box-shadow: none;
    transform: scale(1.5);
  }

  /* ── the ladder (lib/stepLadder places every step) ── */
  .ladder {
    position: relative;
    min-height: 0;
    min-width: 0;
    margin: 0;
    padding: 0;
    list-style: none;
    overflow: hidden;
    /* Steps sliding on or off fade at the edges instead of being cut. */
    mask-image: linear-gradient(
      to bottom,
      transparent 0,
      #000 5%,
      #000 86%,
      transparent 100%
    );
    /* Keep each frame of the slide's layout inside the ladder. */
    contain: strict;
  }
  .step {
    display: grid;
    grid-template-columns: calc(5.5rem * var(--ui-scale)) minmax(0, 1fr);
    gap: calc(1.3rem * var(--ui-scale));
    line-height: 1.24;
    text-wrap: pretty;
  }
  .ladder .step,
  .end {
    position: absolute;
    left: 0;
    right: 0;
    opacity: 0;
    transition:
      top var(--dur-mid) cubic-bezier(0.2, 0.75, 0.25, 1),
      font-size var(--dur-mid) cubic-bezier(0.2, 0.75, 0.25, 1),
      opacity var(--dur-mid) linear;
  }
  .ladder:global([data-instant]) .step,
  .ladder:global([data-instant]) .end {
    transition: none;
  }
  /* The measuring copy never animates: mid-transition it reports the wrong
     height and the steps overlap. */
  .ladder .step[data-measure] {
    visibility: hidden;
    transition: none;
  }
  .n {
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    line-height: 1.24;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  .step p {
    margin: 0;
  }
  .step[data-role="current"] p {
    font-weight: 500;
  }
  .step[data-role="side"] .n {
    font-weight: 400;
  }
  .step[data-role="side"] p {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    overflow: hidden;
  }
  .end {
    padding-left: calc(6.8rem * var(--ui-scale));
    font-style: italic;
  }

  footer {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    color: var(--on-stage-faint, var(--on-stage-soft));
    font-size: var(--type-caption);
  }
  /* A guide's safety line: up the whole time, readable but not loud. */
  .caution {
    margin: 0;
    max-width: 60em;
    padding: 0.35em 0.9em;
    border-radius: 999px;
    box-shadow: inset 0 0 0 0.1em var(--accent);
    color: var(--on-stage);
    font-size: var(--type-sm);
    text-align: center;
    text-wrap: balance;
  }

  /* Time left, draining from right to left along the bottom edge. */
  .drain {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: calc(0.3rem * var(--ui-scale));
    background: var(--accent);
    transform-origin: left center;
    transform: scaleX(var(--from));
    animation: drain var(--left) linear forwards;
    opacity: 0.85;
  }
  @keyframes drain {
    from {
      transform: scaleX(var(--from));
    }
    to {
      transform: scaleX(0);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .drain {
      animation: none;
    }
  }
</style>
