<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  Today's news, one story at a time: the server reads the outlets' feeds,
  sorts the stories into the household's beats (US, World, Good news,
  Houston, …) and the card cross-fades through them in turn. Each story sits
  over its own picture — blurred on the server, so the Pi only shows a small
  finished JPEG — under a scrim in the picture's own colour. Its QR opens
  the article at the outlet, precomputed so the swap rides the crossfade.
-->
<script lang="ts">
  import QRCode from "qrcode";
  import Card from "../components/Card.svelte";
  import Cycler from "../components/Cycler.svelte";
  import { fitText } from "../lib/fitText";
  import { clock } from "../lib/time.svelte";
  import type { CardProps, NewsData } from "./types";
  import { pick } from "./types";
  import { paced } from "../lib/prefs.svelte";

  let { view, stale, hero }: CardProps = $props();
  const stories = $derived(pick<NewsData>(view, "news")?.stories ?? []);
  const base = import.meta.env.VITE_API_URL ?? "";

  // A headline reads in a few seconds, but the QR needs time to be noticed
  // and scanned from across the room.
  const CYCLE_MS = 20_000;

  // One QR per story, rendered ahead of time so the crossfade shows a
  // finished code. Keyed on the joined URLs: it only reruns when the set of
  // stories changes, not on every view-model push.
  let qrs = $state<string[]>([]);
  const qrKey = $derived(stories.map((s) => s.url).join("\u0000"));
  $effect(() => {
    const urls = qrKey ? qrKey.split("\u0000") : [];
    let alive = true;
    void Promise.all(
      urls.map((u) =>
        QRCode.toString(u, {
          type: "svg",
          margin: 1,
          color: { light: "#0000" },
        }),
      ),
    )
      .then((svgs) => {
        if (alive) qrs = svgs;
      })
      .catch(() => {
        /* the headlines still cycle without a QR */
      });
    return () => {
      alive = false;
    };
  });

  /** "now", "40m", "3h", "2d" — how long ago the outlet published it. */
  function age(published: string, now: Date): string {
    const minutes = Math.max(
      0,
      Math.round((now.getTime() - Date.parse(published)) / 60_000),
    );
    if (minutes < 5) return "now";
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 48 * 60) return `${Math.round(minutes / 60)}h`;
    return `${Math.round(minutes / 1440)}d`;
  }
</script>

<Card accent="generic" {stale} {hero} bleed>
  {#if stories.length}
    <Cycler
      count={stories.length}
      intervalMs={paced(CYCLE_MS)}
      dots={false}
      fill
    >
      {#snippet item(i)}
        {@const story = stories[i]}
        {#if story}
          <div
            class="story"
            class:art={!!story.image}
            style:--tint={story.tint ?? undefined}
          >
            {#if story.image}
              <img
                class="backdrop"
                src={base + story.image}
                alt=""
                decoding="async"
              />
            {/if}
            <div class="layout">
              <!-- Only the headline is fitted: a short one grows to fill its
                   space, a long one shrinks until it fits. The QR sits
                   outside so it never gets squeezed off the card. -->
              <div
                class="words"
                use:fitText={{
                  min: 0.8,
                  max: 2.4,
                  maxOfWidth: 0.09,
                  key: story.title,
                }}
              >
                <p class="headline">{story.title}</p>
              </div>
              <p class="byline">
                <span class="beat">{story.beat}</span>
                <span class="source"
                  >{story.outlet} · {age(story.published, clock.now)}</span
                >
              </p>
              {#if qrs[i]}
                <!-- Same labelled code as the photo card's Settings QR, so
                     every code on the screen reads as one kind of thing:
                     a frosted plate behind the code, a label beneath. -->
                <a
                  class="qr"
                  href={story.url}
                  aria-label="Read the story at {story.outlet}"
                >
                  <!-- eslint-disable-next-line svelte/no-at-html-tags -- qrcode lib output -->
                  {@html qrs[i]}
                  <span class="qr-label" aria-hidden="true">Read</span>
                </a>
              {/if}
            </div>
          </div>
        {/if}
      {/snippet}
    </Cycler>
  {:else}
    <span class="waiting">…</span>
  {/if}
</Card>

<style>
  /* Size containment so the card fits its row rather than growing it, with
     a floor for a card alone in its row. The headline takes the space; the
     beat and outlet share a footer row with the QR, bottom-right. A wide
     cell gives the QR the full height on the right. */
  .story {
    position: relative;
    flex: 1;
    container-type: size;
    min-height: min(40cqi, 9rem);
    overflow: hidden;
    border-radius: inherit;
    padding: var(--space-4);
    /* With no picture the story reads in the card's own ink, like any
       other card. */
    --ink: var(--on-card);
    --ink-soft: var(--on-card-soft);
    --ink-faint: var(--on-card-faint);
  }
  /* Over a picture: white ink on a scrim made from the picture's own
     colour, darkest at the bottom where the byline sits. */
  .story.art {
    --ink: #fff;
    --ink-soft: rgba(255, 255, 255, 0.78);
    --ink-faint: rgba(255, 255, 255, 0.45);
    --shade: color-mix(in srgb, var(--tint, #2a2a2e) 45%, #000 55%);
    background: var(--shade);
    text-shadow: 0 1px 12px rgba(0, 0, 0, 0.35);
  }
  .story.art::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 1;
    background: linear-gradient(
      to bottom,
      color-mix(in srgb, var(--shade) 30%, transparent),
      color-mix(in srgb, var(--shade) 50%, transparent) 45%,
      color-mix(in srgb, var(--shade) 85%, transparent)
    );
  }
  /* Already blurred on the server — no CSS filter, nothing for the Pi to
     re-rasterise. Scaled a touch so the blur's soft edge stays off-card. */
  .backdrop {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: scale(1.04);
  }

  .layout {
    position: relative;
    z-index: 2;
    height: 100%;
    display: grid;
    grid-template:
      "words words" 1fr
      "byline qr" auto
      / 1fr auto;
    gap: var(--space-2) var(--space-3);
  }
  @container (min-aspect-ratio: 9 / 5) {
    .layout {
      grid-template:
        "words qr" 1fr
        "byline qr" auto
        / 1fr auto;
      column-gap: var(--space-4);
    }
  }

  .words {
    grid-area: words;
    min-height: 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    overflow: hidden;
  }
  /* The theme's display face carries the headline, a touch heavier than
     body copy so it holds up over a busy picture. */
  .headline {
    font-family: var(--font-display);
    font-size: 1em;
    font-weight: calc(var(--weight-body) + 100);
    line-height: 1.24;
    letter-spacing: -0.005em;
    text-wrap: pretty;
    color: var(--ink);
  }

  .byline {
    grid-area: byline;
    align-self: end;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px var(--space-2);
    min-width: 0;
    font-family: var(--font-body);
    font-size: var(--type-caption);
    line-height: 1.2;
    color: var(--ink-soft);
  }
  /* The beat as a small outlined tag, in whatever ink the story uses. */
  .beat {
    padding: 0.1em 0.6em 0.15em;
    border: 1px solid var(--ink-faint);
    border-radius: var(--radius-pill);
    font-weight: var(--weight-body);
  }
  .source {
    white-space: nowrap;
  }

  .qr {
    grid-area: qr;
    /* Never taller than a third of a stacked card, or most of a wide one. */
    justify-self: end;
    width: min(var(--qr-badge), 34cqh);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    text-decoration: none;
  }
  @container (min-aspect-ratio: 9 / 5) {
    .qr {
      align-self: end;
      width: min(var(--qr-badge), 62cqh);
    }
  }
  .qr :global(svg) {
    display: block;
    width: 100%;
    aspect-ratio: 1;
    height: auto;
    padding: 4px;
    background: rgba(255, 255, 255, 0.8);
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
  }
  /* Frosted over the (already blurred) story picture, like the photo
     card's code; the modules take the picture's darkened colour. */
  .qr :global(path) {
    stroke: color-mix(in srgb, var(--shade, #16161a) 70%, #000);
  }
  .qr-label {
    font-family: var(--font-body);
    font-size: var(--type-caption);
    font-weight: 600;
    line-height: 1.1;
    white-space: nowrap;
    color: var(--ink);
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.7);
  }
  .waiting {
    padding: var(--space-4);
    color: var(--on-card-faint);
  }
</style>
