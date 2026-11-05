<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import Card from "../components/Card.svelte";
  import { idleAirplayMessage } from "../lib/airplayMessages";
  import { coverTint } from "../lib/coverTint";
  import { formatDuration } from "../lib/format";
  import {
    loadingDetail,
    loadingElapsed,
    loadingEyebrow,
    loadingHeadline,
    loadingPercent,
    type Loading,
  } from "../lib/loadingProgress";
  import { clock } from "../lib/time.svelte";
  import type { CardProps } from "./types";
  import { pick } from "./types";

  interface Track {
    title?: string;
    artist?: string;
    album?: string;
    genre?: string;
    year?: string;
    /** The casting device's own name ("Living Room iPhone"), when it sends one. */
    source?: string;
    playing?: boolean;
    /** Wall-clock start of the current play position (ISO 8601) — the
        airplay-bridge's anchor, computed once from shairport-sync's `prgr`
        RTP timestamps. Elapsed time then just ticks locally off `clock.now`,
        the same "server sends a target, client counts down" split as the
        Countdown/Timer cards, so a smooth bar needs no per-second traffic. */
    started_at?: string;
    /** Static fallback for a bridge that only ever sends one snapshot. */
    position_s?: number;
    duration_s?: number;
    coverRev?: number;
    /** Antigua getting something ready for this speaker (speaker/loading). */
    loading?: Loading;
  }

  let { view, hero }: CardProps = $props();
  const base = import.meta.env.VITE_API_URL ?? "";
  const track = $derived(pick<Track>(view, "nowPlaying"));

  // `playing` is absent (not `false`) whenever the bridge has metadata but no
  // confirmed live playback state — treat that the same as paused instead of
  // defaulting to "now playing" for a track we have no live confirmation of.
  const paused = $derived(track?.playing !== true);
  const trackKey = $derived(`${track?.title ?? ""}|${track?.artist ?? ""}`);

  const coverUrl = $derived(
    track?.coverRev ? `${base}/api/nowplaying/cover?v=${track.coverRev}` : null,
  );

  // The panel over the blurred art is tinted with the cover's own average
  // colour, so it reads as part of the record rather than generic grey
  // glass. One 1×1 canvas draw per track — no per-frame cost, and far
  // cheaper on the Pi than a backdrop-filter re-blurring behind a progress
  // bar that changes every second.
  let tint = $state<string | undefined>(undefined);
  $effect(() => {
    const url = coverUrl;
    if (!url) return;
    let live = true;
    void coverTint(url).then((t) => {
      if (live && t) tint = t;
    });
    return () => {
      live = false;
    };
  });

  // While playing, count up from `started_at` on every clock tick; while
  // paused, freeze at whatever that math last produced instead of continuing
  // to advance against the wall clock.
  let frozenElapsed = $state(0);
  let wasPaused = false;
  const liveElapsed = $derived(
    track?.started_at
      ? (clock.now.getTime() - new Date(track.started_at).getTime()) / 1000
      : (track?.position_s ?? 0),
  );
  $effect(() => {
    // Only capture on the false→true edge — `liveElapsed` ticks every
    // second regardless of `paused`, so re-running this on every tick (the
    // effect depends on both) would just keep mirroring the live value
    // instead of freezing it.
    if (paused && !wasPaused) frozenElapsed = liveElapsed;
    wasPaused = paused;
  });
  const elapsed = $derived(paused ? frozenElapsed : liveElapsed);

  const progress = $derived(
    track?.duration_s
      ? Math.min(1, Math.max(0, elapsed / track.duration_s))
      : 0,
  );
  const timeLabel = $derived(
    track?.duration_s
      ? `${formatDuration(Math.min(elapsed, track.duration_s))} / ${formatDuration(track.duration_s)}`
      : null,
  );

  // A single's "album" is usually just the track title again ("Song -
  // Single") — repeating it only costs the panel a line it may not have.
  const album = $derived(
    track?.album && track.title && track.album.startsWith(track.title)
      ? undefined
      : track?.album,
  );
  const meta = $derived([album, track?.year].filter(Boolean).join(" · "));

  // A paused track can't be told apart from "AirPlay ended ages ago and
  // nobody sent a clean teardown" (some shairport-sync setups never do) —
  // both just look like frozen metadata forever. Rather than guess, show
  // the idle prompt below for anything not actively playing.
  const idleMessage = $derived(idleAirplayMessage(clock.now));

  const loading = $derived(track?.loading);
  const loadPct = $derived(loading ? loadingPercent(loading, clock.now) : 0);
  const loadSecs = $derived(loading ? loadingElapsed(loading, clock.now) : 0);
</script>

<Card
  accent="nowPlaying"
  {hero}
  centered
  bleed={!!loading || !!(track?.title && !paused && coverUrl)}
>
  {#if loading}
    <div
      class="loading"
      class:hero
      class:failed={loading.stage === "failed"}
      role="status"
    >
      <span class="eyebrow">
        <span class="eq" data-ambient aria-hidden="true"
          ><i></i><i></i><i></i><i></i></span
        >
        {loadingEyebrow(loading)}
      </span>
      <span class="load-title" class:hero>{loadingHeadline(loading)}</span>
      {#if loading.stage === "starting" && loading.artist}
        <span class="load-artist">by {loading.artist}</span>
      {/if}
      {#if loading.stage !== "failed"}
        <div class="load-row">
          <div
            class="bar"
            role="progressbar"
            aria-label="Getting your music ready"
            aria-valuenow={loadPct}
          >
            <i style:width={`${loadPct}%`}></i>
          </div>
          <span class="pct"
            >{loadPct}%{#if loadSecs >= 5}<small>
                · {loadSecs}s</small
              >{/if}</span
          >
        </div>
      {/if}
      <span class="load-detail" aria-live="polite">
        {loadingDetail(loading, clock.now)}
      </span>
    </div>
  {:else if track?.title && !paused}
    <div class="sleeve" class:hero class:art={!!coverUrl} style:--tint={tint}>
      {#if coverUrl}
        {#key coverUrl}
          <img class="backdrop" src={coverUrl} alt="" decoding="async" />
        {/key}
      {/if}
      <div class="panel" class:hero>
        {#if track.source}
          <span class="source">
            <svg viewBox="0 0 24 24" class="airplay" aria-hidden="true">
              <rect x="2.5" y="3.5" width="19" height="14" rx="2.2" />
              <path d="M12 16.5 L18 23 L6 23 Z" />
            </svg>
            {track.source}
          </span>
        {/if}
        {#key trackKey}
          <span class="lines">
            <span class="title" class:hero>{track.title}</span>
            {#if track.artist}<span class="artist">{track.artist}</span>{/if}
            {#if meta}<span class="album">{meta}</span>{/if}
          </span>
        {/key}
        {#if timeLabel}
          <div
            class="bar"
            role="progressbar"
            aria-label="Track progress"
            aria-valuenow={Math.round(progress * 100)}
          >
            <i style:width={`${progress * 100}%`}></i>
          </div>
        {/if}
        <span class="time">
          <span class="eq" data-ambient aria-label="Now playing"
            ><i></i><i></i><i></i><i></i></span
          >
          {#if timeLabel}{timeLabel}{/if}
        </span>
      </div>
    </div>
  {:else}
    <div class="np idle" class:hero>
      <div class="cover-frame idle-icon" class:hero aria-hidden="true">
        <svg viewBox="0 0 24 24" class="airplay">
          <rect x="2.5" y="3.5" width="19" height="14" rx="2.2" />
          <path d="M12 16.5 L18 23 L6 23 Z" />
        </svg>
      </div>
      <div class="text">
        <span class="eyebrow">AirPlay</span>
        {#key idleMessage}
          <span class="lines">
            <span class="idle-msg" class:hero>{idleMessage}</span>
          </span>
        {/key}
      </div>
    </div>
  {/if}
</Card>

<style>
  .np {
    display: flex;
    gap: var(--space-3);
    align-items: center;
    min-width: 0;
  }
  /* A column stack (cover over text) leaves the hero's 2×2 cell — much wider
     than it is tall — with a strip of content against the top-left corner
     and the rest of the card empty. Lay the pair out side by side instead,
     so the text has the full remaining width to grow into. */
  .np.hero {
    flex-direction: row;
    align-items: center;
    gap: var(--space-4);
  }
  .np.hero .text {
    flex: 1 1 auto;
    min-width: 0;
  }
  /* On the wide trailing row the cover + text otherwise sit in a narrow strip
     against the left edge with the rest of the card empty — centre the group
     and let it breathe symmetrically instead. */
  @container (min-width: 34rem) {
    .np:not(.hero) {
      justify-content: center;
    }
    .np:not(.hero) .text {
      flex: 0 1 auto;
    }
  }

  /* Cover: springs down + dims when paused (like a lock-screen). */
  .cover-frame {
    flex: none;
    line-height: 0;
    border-radius: 10px;
    transition:
      transform var(--dur-mid) var(--ease-spring),
      filter var(--dur-mid) linear;
  }
  .cover-frame.hero {
    border-radius: 16px;
  }
  .text {
    display: flex;
    flex-direction: column;
    gap: var(--space-label);
    min-width: 0;
  }
  .lines {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    animation: lines-in var(--dur-mid) var(--ease-spring);
  }
  @keyframes lines-in {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
  }

  .eyebrow {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--type-caption);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
  }
  .eq {
    display: inline-flex;
    align-items: flex-end;
    gap: 2px;
    height: 0.8em;
  }
  .eq i {
    width: 2px;
    height: 40%;
    background: currentColor;
    border-radius: 1px;
    animation: eq 900ms ease-in-out infinite;
  }
  .eq i:nth-child(2) {
    animation-duration: 700ms;
  }
  .eq i:nth-child(3) {
    animation-duration: 1100ms;
  }
  .eq i:nth-child(4) {
    animation-duration: 820ms;
  }
  @keyframes eq {
    0%,
    100% {
      height: 30%;
    }
    50% {
      height: 100%;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .eq i {
      animation: none;
      height: 60%;
    }
  }
  :global(:root[data-motion="lite"]) .eq i {
    animation: none;
    height: 60%;
  }

  /* ── Playing: the blurred cover is the card, the panel is the label ───── */
  .sleeve {
    position: relative;
    flex: 1;
    align-self: stretch;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 0;
    overflow: hidden;
    border-radius: inherit;
    /* No art yet (or none at all): fall back to a neutral smoke so the
       panel's white text still has something dark behind it. */
    --panel: color-mix(in srgb, var(--tint, #2a2a2e) 55%, #000 45%);
  }
  .sleeve.art {
    padding: var(--space-4);
    background: var(--tint, #000);
  }
  .backdrop {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    /* A slight blur — the art stays recognisable, fine detail softens so
       the panel's text doesn't fight it. Scaled up past the edges so the
       blur's transparent fringe never shows at the card's corners. Its own
       compositor layer: rasterised once per track, then the progress bar
       and eq bars animate above it without re-blurring anything. */
    filter: blur(4px) saturate(1.15) brightness(0.85);
    transform: scale(1.06) translateZ(0);
    will-change: transform;
    animation: backdrop-in 900ms ease;
  }
  @keyframes backdrop-in {
    from {
      opacity: 0;
    }
  }

  .panel {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    width: fit-content;
    /* Grows with the title, but a short title still gets a progress bar
       long enough to read as one. */
    min-width: min(100%, 15rem);
    max-width: min(100%, 34rem);
    padding: var(--space-3) var(--space-4);
    border-radius: 18px;
    background: color-mix(in srgb, var(--panel) 78%, transparent);
    box-shadow:
      inset 0 0 0 1px rgba(255, 255, 255, 0.12),
      0 12px 32px -12px rgba(0, 0, 0, 0.55);
    /* Never taller than the tile: the text below is capped in lines, and
       this is the backstop for a tile shorter than even that. */
    max-height: 100%;
    min-height: 0;
    overflow: hidden;
    color: #fff;
    text-align: center;
    transition: background var(--dur-mid) linear;
  }
  .panel.hero {
    max-width: min(100%, 44rem);
    padding: var(--space-4) var(--space-5);
    border-radius: 24px;
  }

  /* Who's casting — a quiet label above the song, so a household of phones
     can tell whose music this is without it competing with the title. */
  .source {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-width: 0;
    font-size: var(--type-caption);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.64);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .source .airplay {
    flex: none;
    width: 1.1em;
    height: 1.1em;
    stroke: currentColor;
  }
  .source .airplay path {
    fill: currentColor;
  }
  .panel.hero .source {
    font-size: var(--type-sm);
  }

  .title {
    /* Arbitrary-length text, not a fixed-format reading — wrap instead of
       clip, and cap the size so a long title doesn't become a headline. */
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    line-height: 1.15;
    text-wrap: balance;
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }
  .artist,
  .album {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .title.hero {
    font-size: var(--type-xl);
  }
  .artist {
    font-size: var(--type-sm);
    color: rgba(255, 255, 255, 0.86);
  }
  .panel.hero .artist {
    font-size: var(--type-md);
  }
  .album {
    font-size: var(--type-caption);
    color: rgba(255, 255, 255, 0.64);
  }
  .panel.hero .album {
    font-size: var(--type-sm);
  }

  /* ── Loading: Antigua is fetching it. Fits the small grid card: one-line
     title, the bar, then the friendly line (clamped), nothing clipped. ── */
  .loading {
    flex: 1;
    align-self: stretch;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: var(--space-2);
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    padding: var(--space-3) var(--space-4);
    border-radius: inherit;
    color: #fff;
    background: radial-gradient(circle at 25% 15%, #3d3756, #17161d 75%);
  }
  .loading.failed {
    background: radial-gradient(circle at 25% 15%, #55302f, #1d1515 75%);
  }
  .loading .eyebrow {
    color: rgba(255, 255, 255, 0.7);
  }
  .load-title {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    line-height: 1.15;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .load-title.hero {
    font-size: var(--type-xl);
    white-space: normal;
  }
  .load-artist {
    font-size: var(--type-sm);
    color: rgba(255, 255, 255, 0.86);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .load-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .load-row .bar {
    flex: 1;
    height: 8px;
    border-radius: 4px;
  }
  .load-row .bar i {
    background: #b9a8ff;
    /* the clock ticks once a second: glide between ticks rather than step */
    transition: width 1s linear;
  }
  .pct {
    font-size: var(--type-sm);
    font-weight: var(--weight-label);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .pct small {
    font-size: var(--type-caption);
    font-weight: normal;
    color: rgba(255, 255, 255, 0.7);
  }
  .loading.failed .load-detail {
    -webkit-line-clamp: 3;
    line-clamp: 3;
  }
  .load-detail {
    font-size: var(--type-caption);
    line-height: 1.35;
    padding-bottom: 0.1em; /* descenders survive the clamp */
    color: rgba(255, 255, 255, 0.75);
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
  }

  /* ── Idle: AirPlay's waiting, not frozen on a stale track ──────────────── */
  .idle-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 5.5rem;
    height: 5.5rem;
    background: color-mix(in srgb, var(--on-card) 10%, transparent);
  }
  .idle-icon.hero {
    width: clamp(9rem, 18vw, 20rem);
    height: auto;
    aspect-ratio: 1;
  }
  @supports (container-type: inline-size) {
    .idle-icon {
      width: clamp(5.5rem, 20cqi, 22rem);
      height: auto;
      aspect-ratio: 1;
    }
  }
  .airplay {
    width: 45%;
    height: 45%;
    fill: none;
    stroke: var(--on-card-soft);
    stroke-width: 1.6;
    stroke-linejoin: round;
  }
  .airplay path {
    fill: var(--on-card-soft);
    stroke: none;
  }
  .idle-msg {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
    line-height: 1.3;
    text-wrap: balance;
    max-width: 26ch;
  }
  .idle-msg.hero {
    font-size: var(--type-lg);
    max-width: 20ch;
  }
  .bar {
    width: 100%;
    height: 4px;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.22);
    overflow: hidden;
  }
  .bar i {
    display: block;
    height: 100%;
    border-radius: inherit;
    /* The cover's own colour, lifted toward white so it stays visible on
       the darker panel made from the same colour. */
    background: color-mix(in srgb, var(--tint, #fff) 45%, #fff);
    transition: width var(--dur-mid) linear;
  }
  .time {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-variant-numeric: tabular-nums;
    font-size: var(--type-caption);
    color: rgba(255, 255, 255, 0.7);
  }
</style>
