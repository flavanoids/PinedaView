<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { components } from "@pinedaview/protocol";

  import { fade } from "svelte/transition";

  import { deflate, inflate } from "../lib/balloon";
  import { loadGuess } from "../lib/loadGuess";

  type Takeover = components["schemas"]["Takeover"];
  type Camera = components["schemas"]["CameraTakeover"];

  interface Props {
    takeover: Takeover;
  }
  let { takeover }: Props = $props();

  const card = $derived(takeover.card as Camera);
  const src = $derived(
    `/api/cameras/${encodeURIComponent(card.camera)}/stream.mp4`,
  );
  const pipSrc = $derived(
    card.pip_camera
      ? `/api/cameras/${encodeURIComponent(card.pip_camera)}/stream.mp4`
      : undefined,
  );
  // "Identifying…" pulses until whoever's watching names who it is.
  const pending = $derived(card.caption.endsWith("…"));
  const totalMs = $derived(
    Date.parse(takeover.expires_at) - Date.parse(takeover.shown_at),
  );
  const leftMs = $derived(
    Math.max(0, Date.parse(takeover.expires_at) - Date.now()),
  );

  // A battery camera takes a moment to wake and start sending, and the
  // stream can drop; keep asking until it plays, for as long as it's up.
  let video: HTMLVideoElement | undefined = $state();
  let live = $state(false);
  // While it connects: a ring and a percentage that follow a guess at the
  // wait (lib/loadGuess), since the camera can't say how far along it is.
  // Restarts if the stream drops and it reconnects.
  let since = $state(performance.now());
  let now = $state(performance.now());
  let done = $state(false); // video arrived: 100%, then the overlay fades
  const percent = $derived(done ? 100 : loadGuess(now - since));
  let played = $state(false); // the video has shown a picture at least once

  // Behind the ring: the camera's latest snapshot (from HA's event push or
  // recent capture), shown crisp and full-frame so the user sees who arrived
  // immediately in <500ms rather than waiting 4-8s for the live video stream.
  let backdrop: HTMLCanvasElement | undefined = $state();
  let hasBackdrop = $state(false);
  $effect(() => {
    const c = backdrop;
    if (!c) return;
    const img = new Image();
    img.onload = () => {
      const ctx = c.getContext("2d");
      if (!ctx || !img.naturalWidth) return;
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0, c.width, c.height);
      hasBackdrop = true;
    };
    // Fresh snapshot cache-buster: uses exact takeover shown_at timestamp or now,
    // ensuring the fresh event snapshot displays immediately.
    const v = Date.parse(takeover.shown_at) || Date.now();
    img.src = `/api/home-cams/${encodeURIComponent(card.camera)}.jpg?v=${v}`;
    return () => (img.onload = null);
  });
  $effect(() => {
    if (live && !done) return;
    const tick = setInterval(() => (now = performance.now()), 100);
    return () => clearInterval(tick);
  });
  $effect(() => {
    const el = video;
    const url = src;
    if (!el) return;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      live = false;
      done = false;
      since = now = performance.now();
      el.src = `${url}?t=${Date.now()}`;
      el.play()?.catch(() => {});
    };
    const again = () => {
      clearTimeout(retry);
      retry = setTimeout(load, 1500);
    };
    const playing = () => {
      done = true;
      played = true;
      setTimeout(() => (live = true), 250); // let 100% show for a moment
    };
    el.addEventListener("error", again);
    el.addEventListener("ended", again);
    el.addEventListener("playing", playing);
    load();
    return () => {
      clearTimeout(retry);
      el.removeEventListener("error", again);
      el.removeEventListener("ended", again);
      el.removeEventListener("playing", playing);
      // Drop the connection so the server stops relaying.
      el.removeAttribute("src");
      el.load();
    };
  });

  // ── Picture-in-Picture secondary camera (e.g. garage) ──
  let pipVideo: HTMLVideoElement | undefined = $state();
  let pipLive = $state(false);
  let pipSince = $state(performance.now());
  let pipNow = $state(performance.now());
  let pipDone = $state(false);
  const pipPercent = $derived(pipDone ? 100 : loadGuess(pipNow - pipSince));
  let pipPlayed = $state(false);

  let pipBackdrop: HTMLCanvasElement | undefined = $state();
  let hasPipBackdrop = $state(false);
  $effect(() => {
    const c = pipBackdrop;
    const pipCam = card.pip_camera;
    if (!c || !pipCam) return;
    const img = new Image();
    img.onload = () => {
      const ctx = c.getContext("2d");
      if (!ctx || !img.naturalWidth) return;
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0, c.width, c.height);
      hasPipBackdrop = true;
    };
    const v = Date.parse(takeover.shown_at) || Date.now();
    img.src = `/api/home-cams/${encodeURIComponent(pipCam)}.jpg?v=${v}`;
    return () => (img.onload = null);
  });
  $effect(() => {
    if ((pipLive && !pipDone) || !card.pip_camera) return;
    const tick = setInterval(() => (pipNow = performance.now()), 100);
    return () => clearInterval(tick);
  });
  $effect(() => {
    const el = pipVideo;
    const url = pipSrc;
    if (!el || !url) return;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      pipLive = false;
      pipDone = false;
      pipSince = pipNow = performance.now();
      el.src = `${url}?t=${Date.now()}`;
      el.play()?.catch(() => {});
    };
    const again = () => {
      clearTimeout(retry);
      retry = setTimeout(load, 1500);
    };
    const playing = () => {
      pipDone = true;
      pipPlayed = true;
      setTimeout(() => (pipLive = true), 250);
    };
    el.addEventListener("error", again);
    el.addEventListener("ended", again);
    el.addEventListener("playing", playing);
    load();
    return () => {
      clearTimeout(retry);
      el.removeEventListener("error", again);
      el.removeEventListener("ended", again);
      el.removeEventListener("playing", playing);
      el.removeAttribute("src");
      el.load();
    };
  });
</script>

<div
  class="camera"
  class:paired={!!card.pip_camera}
  role="dialog"
  aria-modal="true"
  aria-label={`Camera: ${card.title || card.camera}`}
  in:inflate|global
  out:deflate|global
>
  <canvas
    class="backdrop"
    class:shown={hasBackdrop}
    bind:this={backdrop}
    aria-hidden="true"
  ></canvas>
  <video bind:this={video} class:sharp={played} muted autoplay playsinline
  ></video>
  {#if !live}
    <div
      class="waking"
      role="progressbar"
      aria-label="Connecting to the camera"
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={percent}
      out:fade={{ duration: 300 }}
    >
      <svg class="ring" viewBox="0 0 120 120" aria-hidden="true">
        <circle class="track" cx="60" cy="60" r="52" />
        <circle
          class="fill"
          cx="60"
          cy="60"
          r="52"
          pathLength="100"
          style:stroke-dashoffset={100 - percent}
        />
        <circle class="spin" cx="60" cy="60" r="52" pathLength="100" />
      </svg>
      <p class="pct">{percent}%</p>
      <p class="what">
        Connecting to the {card.title.toLowerCase() || "camera"}…
      </p>
      <div class="load-bar" aria-hidden="true">
        <div class="load-fill" style:width={`${percent}%`}></div>
      </div>
    </div>
  {/if}

  <!-- "Live" only once it is: over the snapshot it's just the camera's name. -->
  <p class="tag">
    {#if played}<span class="dot" aria-hidden="true"></span><span class="live"
        >Live</span
      >{/if}<span class="title">{card.title || card.camera}</span>
  </p>

  {#if card.pip_camera}
    <div
      class="pip"
      role="region"
      aria-label={`Picture in picture: ${card.pip_title || card.pip_camera}`}
    >
      <canvas
        class="pip-backdrop"
        class:shown={hasPipBackdrop}
        bind:this={pipBackdrop}
        aria-hidden="true"
      ></canvas>
      <video
        bind:this={pipVideo}
        class="pip-video"
        class:sharp={pipPlayed}
        muted
        autoplay
        playsinline
      ></video>
      {#if !pipLive}
        <div
          class="pip-waking"
          role="progressbar"
          aria-label={`Connecting to ${card.pip_title || card.pip_camera}`}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={pipPercent}
          out:fade={{ duration: 250 }}
        >
          <div class="pip-waking-content">
            <svg class="pip-ring" viewBox="0 0 60 60" aria-hidden="true">
              <circle class="track" cx="30" cy="30" r="24" />
              <circle
                class="fill"
                cx="30"
                cy="30"
                r="24"
                pathLength="100"
                style:stroke-dashoffset={100 - pipPercent}
              />
              <circle class="spin" cx="30" cy="30" r="24" pathLength="100" />
            </svg>
            <p class="pip-pct">{pipPercent}%</p>
          </div>
          <p class="pip-what">
            Connecting to {card.pip_title?.toLowerCase() || card.pip_camera}…
          </p>
          <div class="pip-load-bar" aria-hidden="true">
            <div class="pip-load-fill" style:width={`${pipPercent}%`}></div>
          </div>
        </div>
      {/if}
      <p class="pip-tag">
        {#if pipPlayed}<span class="dot" aria-hidden="true"></span><span
            class="live">Live</span
          >{/if}<span class="title">{card.pip_title || card.pip_camera}</span>
      </p>
    </div>
  {/if}

  {#if card.caption}
    {#key card.caption}
      <p class="caption" class:pending>{card.caption}</p>
    {/key}
  {/if}

  {#key takeover.expires_at}
    <div
      class="drain"
      aria-hidden="true"
      style:--left={`${leftMs}ms`}
      style:--from={totalMs > 0 ? leftMs / totalMs : 1}
    ></div>
  {/key}
</div>

<style>
  /* Over everything but the dimmer (z 25). The
     whole screen is the video (letterboxed, never cropped: a face at the
     top of the doorbell's frame stays in); a small "Live" tag names the
     camera and who it is reads large along the bottom. It inflates out of
     the bottom-right corner and shrinks back into it (lib/balloon). */
  .camera {
    position: fixed;
    inset: 0;
    /* One above the other takeovers: shrinking away, it stays over the
       card it gives the screen back to. */
    z-index: 21;
    overflow: hidden;
    background: #000;
    color: #fff;
    font-family: var(--font-body);
    will-change: transform, opacity;
  }
  video,
  .backdrop {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
  .backdrop {
    opacity: 0;
    transition: opacity 0.4s ease-out;
  }
  .backdrop.shown {
    opacity: 1;
  }
  /* Hidden until the first picture, then it comes into focus over the
     blurred snapshot. Once seen it stays (a reconnect keeps its last frame). */
  video {
    opacity: 0;
    transition: opacity 0.6s ease-out;
  }
  video.sharp {
    opacity: 1;
  }
  @media (prefers-reduced-motion: reduce) {
    video,
    .backdrop {
      transition: none;
    }
  }
  .waking {
    position: absolute;
    inset: 0;
    display: grid;
    place-content: center;
    justify-items: center;
    gap: var(--space-3);
    margin: 0;
    color: rgb(255 255 255 / 0.85);
  }
  .ring {
    grid-area: 1 / 1;
    width: calc(9rem * var(--ui-scale));
    height: calc(9rem * var(--ui-scale));
    transform: rotate(-90deg);
    fill: none;
    stroke-width: 6;
    stroke-linecap: round;
  }
  .track {
    stroke: rgb(255 255 255 / 0.14);
  }
  .fill {
    stroke: var(--accent);
    stroke-dasharray: 100;
    transition: stroke-dashoffset 0.12s linear;
  }
  /* A short bright arc going round on top, so it reads as working even
     while the number creeps. */
  .spin {
    stroke: rgb(255 255 255 / 0.55);
    stroke-dasharray: 9 91;
    transform-origin: 60px 60px;
  }
  @media (prefers-reduced-motion: no-preference) {
    .spin {
      animation: spin 1.1s linear infinite;
    }
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  .pct {
    grid-area: 1 / 1;
    align-self: center;
    margin: 0;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: calc(2rem * var(--ui-scale));
    font-variant-numeric: tabular-nums;
    color: #fff;
  }
  .pct,
  .what {
    text-shadow: 0 1px 12px rgb(0 0 0 / 0.6);
  }
  .what {
    margin: 0;
    font-size: var(--type-md);
    font-weight: var(--weight-label);
  }
  .load-bar {
    width: calc(14rem * var(--ui-scale));
    height: calc(0.25rem * var(--ui-scale));
    background: rgb(255 255 255 / 0.18);
    border-radius: 999px;
    overflow: hidden;
    margin-top: calc(0.25rem * var(--ui-scale));
  }
  .load-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 999px;
    transition: width 0.12s linear;
  }

  /* ── Picture in Picture: garage camera in the top right corner ── */
  .pip {
    position: absolute;
    top: calc(
      max(var(--space-4), env(safe-area-inset-top)) + var(--frame-y, 0px)
    );
    right: calc(
      max(var(--space-4), env(safe-area-inset-right)) + var(--frame-x, 0px)
    );
    width: calc(min(30vw, 380px) * var(--ui-scale));
    aspect-ratio: 16 / 9;
    border-radius: calc(14px * var(--ui-scale));
    overflow: hidden;
    background: #000;
    box-shadow:
      0 12px 36px rgb(0 0 0 / 0.8),
      0 0 0 1px rgb(255 255 255 / 0.18);
    z-index: 2;
  }
  .pip-backdrop,
  .pip-video {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .pip-backdrop {
    opacity: 0;
    transition: opacity 0.4s ease-out;
  }
  .pip-backdrop.shown {
    opacity: 1;
  }
  .pip-video {
    opacity: 0;
    transition: opacity 0.6s ease-out;
  }
  .pip-video.sharp {
    opacity: 1;
  }
  @media (prefers-reduced-motion: reduce) {
    .pip-video,
    .pip-backdrop {
      transition: none;
    }
  }
  .pip-waking {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: calc(0.35rem * var(--ui-scale));
    padding: calc(0.5rem * var(--ui-scale));
    background: rgb(0 0 0 / 0.45);
    color: rgb(255 255 255 / 0.9);
    text-align: center;
  }
  .pip-waking-content {
    display: grid;
    place-content: center;
    justify-items: center;
  }
  .pip-ring {
    grid-area: 1 / 1;
    width: calc(3.4rem * var(--ui-scale));
    height: calc(3.4rem * var(--ui-scale));
    transform: rotate(-90deg);
    fill: none;
    stroke-width: 5;
    stroke-linecap: round;
  }
  .pip-pct {
    grid-area: 1 / 1;
    align-self: center;
    margin: 0;
    font-family: var(--font-display);
    font-weight: var(--weight-display);
    font-size: calc(0.95rem * var(--ui-scale));
    font-variant-numeric: tabular-nums;
    color: #fff;
    text-shadow: 0 1px 6px rgb(0 0 0 / 0.7);
  }
  .pip-what {
    margin: 0;
    font-size: calc(0.72rem * var(--ui-scale));
    font-weight: var(--weight-label);
    text-shadow: 0 1px 6px rgb(0 0 0 / 0.7);
    max-width: 90%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pip-load-bar {
    width: calc(8rem * var(--ui-scale));
    max-width: 80%;
    height: 3px;
    background: rgb(255 255 255 / 0.2);
    border-radius: 999px;
    overflow: hidden;
  }
  .pip-load-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 999px;
    transition: width 0.12s linear;
  }
  .pip-tag {
    position: absolute;
    bottom: calc(0.45rem * var(--ui-scale));
    left: calc(0.45rem * var(--ui-scale));
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.4em;
    padding: 0.3em 0.65em;
    border-radius: 999px;
    background: rgb(0 0 0 / 0.65);
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: calc(0.65rem * var(--ui-scale));
    text-transform: uppercase;
    letter-spacing: 0.06em;
    z-index: 3;
    pointer-events: none;
  }

  .tag {
    position: absolute;
    top: calc(
      max(var(--space-4), env(safe-area-inset-top)) + var(--frame-y, 0px)
    );
    left: calc(
      max(var(--space-4), env(safe-area-inset-left)) + var(--frame-x, 0px)
    );
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.5em;
    padding: 0.45em 0.95em;
    border-radius: 999px;
    background: rgb(0 0 0 / 0.55);
    font-family: var(--font-display);
    font-weight: var(--weight-label);
    font-size: var(--type-sm);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .live + .title {
    margin-left: 0.35em;
  }
  .title {
    text-transform: none;
    letter-spacing: 0;
    opacity: 0.9;
  }
  .dot {
    width: 0.6em;
    height: 0.6em;
    border-radius: 50%;
    background: #e5484d;
  }
  @media (prefers-reduced-motion: no-preference) {
    .dot {
      animation: blink 1.6s ease-in-out infinite;
    }
  }
  @keyframes blink {
    50% {
      opacity: 0.25;
    }
  }
  .caption {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    margin: 0;
    padding: var(--space-6, 4rem) calc(var(--space-5) + var(--frame-x, 0px))
      calc(var(--space-5) + var(--frame-y, 0px));
    background: linear-gradient(to top, rgb(0 0 0 / 0.7), transparent);
    font-size: calc(clamp(1.75rem, min(2.6vw, 4vh), 3.25rem) * var(--ui-scale));
    font-weight: var(--weight-label);
    line-height: 1.15;
    text-align: center;
    text-wrap: balance;
  }
  .caption.pending {
    color: rgb(255 255 255 / 0.75);
  }

  /* A tall screen: the picture keeps clear of the frame's lip, and with a
     second camera the two stack — the second one the screen's full width
     along the bottom, the caption just above it — rather than a corner
     inset over a letterboxed picture. */
  @media (orientation: portrait) {
    .camera > video,
    .camera > .backdrop {
      top: var(--frame-y, 0px);
      bottom: var(--frame-y, 0px);
      height: auto;
    }
    .camera.paired {
      --pip-h: calc((100vw - 2 * var(--space-4)) * 9 / 16);
      --pip-room: calc(var(--pip-h) + 2 * var(--space-4));
    }
    .camera.paired > video,
    .camera.paired > .backdrop {
      bottom: calc(var(--frame-y, 0px) + var(--pip-room));
    }
    .camera.paired .pip {
      top: auto;
      bottom: calc(var(--frame-y, 0px) + var(--space-4));
      left: var(--space-4);
      right: var(--space-4);
      width: auto;
    }
    .camera.paired .caption {
      bottom: var(--pip-room);
    }
  }
  @media (prefers-reduced-motion: no-preference) {
    .caption.pending {
      animation: breathe 1.4s ease-in-out infinite;
    }
  }
  @keyframes breathe {
    50% {
      opacity: 0.45;
    }
  }

  /* Time left, draining from right to left along the bottom edge. */
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
  @media (prefers-reduced-motion: reduce) {
    .drain {
      animation: none;
    }
  }
</style>
