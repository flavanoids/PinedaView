<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { createClient, type components } from "@pinedaview/protocol";
  import { untrack } from "svelte";
  import { cubicInOut } from "svelte/easing";

  type Takeover = components["schemas"]["Takeover"];
  type Choices = components["schemas"]["RecipeChoicesTakeover"];

  interface Props {
    takeover: Takeover;
  }
  let { takeover }: Props = $props();

  const client = createClient(import.meta.env.VITE_API_URL ?? "");
  const card = $derived(takeover.card as Choices);

  // A picture none of whose sources worked leaves its recipe; a recipe
  // with none left keeps its column, letter and title.
  let failed = $state<Record<string, boolean>>({});
  let loaded = $state<Record<string, boolean>>({});
  let retried = $state<Record<string, boolean>>({});

  const columns = $derived(
    card.choices.map((c) => {
      const photos = (c.images ?? []).filter((id) => !failed[id]).slice(0, 4);
      return { ...c, hero: photos[0] ?? null, more: photos.slice(1) };
    }),
  );
  const active = $derived(card.highlight?.toUpperCase() ?? null);
  const heading = $derived(
    card.dish.charAt(0).toUpperCase() + card.dish.slice(1),
  );
  const letters = $derived(card.choices.map((c) => `“${c.id}”`));
  const asked = $derived(
    letters.length < 3
      ? letters.join(" or ")
      : `${letters.slice(0, -1).join(", ")} or ${letters.at(-1)}`,
  );

  // The bar drains over whatever time is left, as on the collage.
  const firstExpiry = untrack(() => takeover.expires_at);
  const totalMs = $derived(
    Date.parse(takeover.expires_at) - Date.parse(takeover.shown_at),
  );
  const leftMs = $derived(
    Math.max(0, Date.parse(takeover.expires_at) - Date.now()),
  );
  const drainFrom = $derived(
    takeover.expires_at !== firstExpiry || totalMs <= 0 ? 1 : leftMs / totalMs,
  );

  // The server fetches and shrinks each picture (image_proxy); shown_at
  // keys the browser cache to this card, since ids repeat between cards.
  function picture(id: string, size: "thumb" | "full"): string {
    const v = encodeURIComponent(takeover.shown_at);
    const again = retried[id] ? "&again=1" : "";
    return `/api/takeover/images/${encodeURIComponent(id)}?size=${size}&v=${v}${again}`;
  }

  // One more try before a picture leaves.
  function missing(id: string): void {
    if (retried[id]) {
      failed[id] = true;
      return;
    }
    setTimeout(() => (retried[id] = true), 1500);
  }

  // "serves 8" → 8 servings; "makes 1 loaf" → 1 loaf, what it makes.
  function serves(text: string | undefined): { value: string; label: string } {
    const t = (text ?? "").trim();
    if (!t) return { value: "—", label: "servings" };
    const m = /^(serves|makes|yields?)\s+(.+)$/i.exec(t);
    if (!m) return { value: t, label: "servings" };
    const what = m[2]!;
    const bare = /^[\d\s/–-]+$/.test(what);
    if (m[1]!.toLowerCase() === "serves" || bare) {
      return { value: what, label: "servings" };
    }
    // "12 slices" won't fit big: the count big, "slices" under it.
    const n = /^([\d/–-]+)\s+(.+)$/.exec(what);
    return n && what.length > 6
      ? { value: n[1]!, label: n[2]! }
      : { value: what, label: "makes" };
  }

  function ratings(n: number): string {
    const short =
      n >= 1000 ? `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k` : `${n}`;
    return `${short.replace(".0k", "k")} ratings`;
  }

  function minutes(total: number): string {
    if (total < 60) return `${total} min`;
    const h = Math.floor(total / 60);
    const m = total % 60;
    return m ? `${h}h ${m}m` : `${h} hr`;
  }

  function leave(_node: HTMLElement) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return { duration: 0 };
    }
    return {
      duration: 420,
      easing: cubicInOut,
      css: (t: number) =>
        `opacity: ${t}; transform: scale(${0.97 + 0.03 * t});`,
    };
  }

  function dismiss(): void {
    void client.clearTakeover().catch(() => {});
  }
</script>

<div class="choices" style:--left={`${leftMs}ms`} out:leave|global>
  <header>
    <div class="title">
      <p class="kicker">Recipes</p>
      <h1>{heading}</h1>
    </div>
    <p class="hint">
      <span>Which one would you like?</span>
      <span class="say">Say <strong>{asked}</strong></span>
    </p>
    <button type="button" class="close" onclick={dismiss} aria-label="Close">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    </button>
  </header>

  <main style:--n={columns.length}>
    {#each columns as c, i (c.id)}
      <article
        class="choice"
        class:lit={active === c.id.toUpperCase()}
        style:--i={i}
        aria-label={`Recipe ${c.id}: ${c.title}`}
      >
        <div class="photos" class:alone={c.more.length === 0}>
          <div class="hero" class:loaded={c.hero && loaded[c.hero]}>
            {#if c.hero}
              <img
                class="backdrop"
                src={picture(c.hero, "thumb")}
                alt=""
                aria-hidden="true"
                decoding="async"
              />
              <img
                class="photo"
                src={picture(c.hero, "full")}
                alt={c.title}
                decoding="async"
                onload={() => c.hero && (loaded[c.hero] = true)}
                onerror={() => c.hero && missing(c.hero)}
              />
            {:else}
              <!-- No photo from its site: a plate, so the column isn't a blank. -->
              <svg class="nophoto" viewBox="0 0 64 64" aria-hidden="true">
                <circle cx="32" cy="32" r="17" />
                <circle cx="32" cy="32" r="11" />
                <path
                  d="M8 14v12a4 4 0 0 0 4 4v20M12 14v10M16 14v12a4 4 0 0 1-4 4"
                />
                <path d="M54 50V14c-4 2-6 8-6 16h6" />
              </svg>
            {/if}
            <span class="badge">{c.id}</span>
          </div>
          {#if c.more.length}
            <div class="more" style:--m={c.more.length}>
              {#each c.more as id (id)}
                <div class="thumb" class:loaded={loaded[id]}>
                  <img
                    class="photo"
                    src={picture(id, "thumb")}
                    alt=""
                    decoding="async"
                    onload={() => (loaded[id] = true)}
                    onerror={() => missing(id)}
                  />
                </div>
              {/each}
            </div>
          {/if}
        </div>
        <div class="about">
          <h2>{c.title}</h2>
          {#if c.source}<p class="source">{c.source}</p>{/if}
          <dl class="stats">
            <div>
              <dt>{c.rating_count ? ratings(c.rating_count) : "rating"}</dt>
              <dd class:none={!c.rating}>
                {#if c.rating}<span class="star">★</span>
                  {c.rating.toFixed(1)}{:else}—{/if}
              </dd>
            </div>
            <div>
              <dt>total time</dt>
              <dd class:none={!c.total_min}>
                {c.total_min ? minutes(c.total_min) : "—"}
              </dd>
            </div>
            <div>
              <dt>{serves(c.servings).label}</dt>
              <dd class:none={!c.servings}>{serves(c.servings).value}</dd>
            </div>
          </dl>
        </div>
      </article>
    {/each}
  </main>

  {#key takeover.expires_at}
    <div class="drain" aria-hidden="true" style:--from={drainFrom}></div>
  {/key}
</div>

<style>
  .choices {
    position: fixed;
    inset: 0;
    z-index: 25;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    gap: var(--space-3);
    padding: calc(
        max(var(--space-4), env(safe-area-inset-top)) + var(--frame-y, 0px)
      )
      calc(
        max(var(--space-4), env(safe-area-inset-right)) + var(--frame-x, 0px)
      )
      calc(var(--space-4) + var(--frame-y, 0px))
      calc(max(var(--space-4), env(safe-area-inset-left)) + var(--frame-x, 0px));
    background: var(--stage);
    color: var(--on-stage);
    font-family: var(--font-body);
    overflow: hidden;
    user-select: none;
  }

  header {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    min-width: 0;
  }
  .title {
    flex: 1;
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
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: calc(var(--type-lg) * 0.8);
    line-height: 1.1;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .hint {
    margin: 0;
    flex-shrink: 0;
    display: grid;
    justify-items: end;
    gap: 0.15em;
    color: var(--on-stage);
    font-size: var(--type-sm);
    font-weight: var(--weight-label);
  }
  .say {
    color: var(--on-stage-soft);
    font-size: var(--type-caption);
    font-weight: normal;
  }
  .say strong {
    color: var(--on-stage);
    font-weight: var(--weight-label);
  }
  .close {
    flex-shrink: 0;
    display: grid;
    place-items: center;
    width: calc(2.6rem * var(--ui-scale));
    aspect-ratio: 1;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: color-mix(in srgb, var(--on-stage) 10%, transparent);
    color: var(--on-stage-soft);
    cursor: pointer;
  }
  .close svg {
    width: 45%;
    fill: none;
    stroke: currentColor;
    stroke-width: 2.4;
    stroke-linecap: round;
  }

  /* One column per recipe; on a portrait screen, one row each with the
     photos beside the words. */
  main {
    display: grid;
    grid-template-columns: repeat(var(--n), minmax(0, 1fr));
    grid-template-rows: minmax(0, 1fr) auto;
    column-gap: var(--space-4);
    min-height: 0;
  }
  /* The rows are shared, so the photos line up across the recipes even
     when one's words take an extra line. */
  .choice {
    display: grid;
    grid-row: span 2;
    grid-template-rows: subgrid;
    gap: var(--space-2);
    min-width: 0;
    min-height: 0;
    padding: var(--space-2);
    border-radius: calc(var(--radius-card) + var(--space-2));
    background: color-mix(in srgb, var(--on-stage) 5%, var(--stage));
    transition:
      box-shadow var(--dur-normal) ease,
      background var(--dur-normal) ease;
  }
  .lit {
    box-shadow: 0 0 0 0.2rem var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, var(--stage));
  }

  .photos {
    display: grid;
    grid-template-rows: minmax(0, 3fr) minmax(0, 1fr);
    gap: var(--space-2);
    min-height: 0;
  }
  .photos.alone {
    grid-template-rows: minmax(0, 1fr);
  }
  .more {
    display: grid;
    grid-template-columns: repeat(var(--m), minmax(0, 1fr));
    gap: var(--space-2);
    min-height: 0;
  }
  .hero,
  .thumb {
    position: relative;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    border-radius: var(--radius-card);
    background: color-mix(in srgb, var(--on-stage) 8%, var(--stage));
  }

  .nophoto {
    position: absolute;
    inset: 0;
    margin: auto;
    width: 40%;
    max-height: 60%;
    fill: none;
    stroke: color-mix(in srgb, var(--on-stage) 22%, transparent);
    stroke-width: 2.2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .backdrop {
    filter: blur(1.4rem) saturate(1.2) brightness(0.7);
    transform: scale(1.15);
  }
  .photo {
    opacity: 0;
    transition: opacity var(--dur-slow) ease;
  }
  .loaded .photo {
    opacity: 1;
  }

  .badge {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    display: grid;
    place-items: center;
    width: calc(3rem * var(--ui-scale));
    aspect-ratio: 1;
    border-radius: 50%;
    background: rgb(0 0 0 / 0.55);
    box-shadow: 0 0 0 0.12em rgb(255 255 255 / 0.35);
    color: #fff;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: var(--type-lg);
    line-height: 1;
    transition:
      background var(--dur-normal) ease,
      color var(--dur-normal) ease;
  }
  .lit .badge {
    background: var(--accent);
    color: var(--stage);
  }

  .about {
    container-type: inline-size;
    display: grid;
    /* The stats sit on the bottom, level across the recipes, whether or
       not a title takes two lines. */
    grid-template-rows: auto auto 1fr;
    gap: 0.25em;
    padding: 0 var(--space-1, 0.25rem) var(--space-1, 0.25rem);
    min-width: 0;
  }
  h2 {
    margin: 0;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: var(--type-md);
    line-height: 1.15;
    text-wrap: balance;
  }
  .source {
    margin: 0;
    color: var(--on-stage-soft);
    font-size: var(--type-caption);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  /* The headline numbers: how it rates, how long it takes, how much it
     makes, in the same places on every recipe so they compare at a glance. */
  .stats {
    margin: var(--space-2) 0 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr) minmax(0, 1fr);
    align-self: end;
    gap: var(--space-2);
  }
  .stats > div {
    display: grid;
    gap: 0.1em;
    min-width: 0;
    padding: var(--space-2);
    border-radius: var(--radius-card);
    background: color-mix(in srgb, var(--on-stage) 7%, var(--stage));
  }
  dd {
    order: -1;
    margin: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    /* Sized to the column: the kiosk's frame and wide display faces
       leave less room than the theme's type scale assumes. */
    font-size: min(var(--type-md), 7cqi);
    line-height: 1.1;
  }
  dd.none {
    color: var(--on-stage-soft);
    font-weight: normal;
  }
  .star {
    color: var(--accent);
  }
  dt {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: var(--on-stage-soft);
    font-size: min(var(--type-caption), 4.4cqi);
  }

  .drain {
    position: absolute;
    left: 0;
    right: 0;
    bottom: var(--frame-y, 0px);
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

  @media (orientation: portrait) {
    main {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: repeat(var(--n), minmax(0, 1fr));
      row-gap: var(--space-4);
    }
    .choice {
      grid-row: auto;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      grid-template-rows: minmax(0, 1fr);
      gap: var(--space-3);
    }
    .about {
      align-self: center;
      min-height: 0;
    }
    /* Side by side, as on a wide screen (stacked, they stood taller than
       the photo's row and ran into the next recipe), each as wide as what
       it says: no fixed share fits "2.3k ratings", "6h 20m" and
       "servings" all at once. */
    .stats {
      grid-template-columns: repeat(3, auto);
      justify-content: start;
    }
  }

  @media (prefers-reduced-motion: no-preference) {
    .choices {
      animation: rise var(--dur-mid) var(--ease-spring) both;
    }
    /* The recipes arrive one after another, A first. */
    .choice {
      animation: arrive var(--dur-slow) var(--ease-spring) both;
      animation-delay: calc(var(--i) * 90ms);
    }
    .hero .photo {
      animation: drift 40s linear both;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .drain {
      animation: none;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: scale(0.985);
    }
  }
  @keyframes arrive {
    from {
      opacity: 0;
      transform: translateY(1.5vh) scale(0.97);
    }
  }
  @keyframes drift {
    from {
      transform: scale(1.02);
    }
    to {
      transform: scale(1.08) translate(-1%, -0.8%);
    }
  }
</style>
