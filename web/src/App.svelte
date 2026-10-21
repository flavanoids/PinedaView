<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { untrack } from "svelte";
  import { applyFont, applyTheme } from "@pinedaview/tokens";
  import { createClient, type Theme } from "@pinedaview/protocol";

  import AlarmTakeover from "./components/AlarmTakeover.svelte";
  import Alternate from "./components/Alternate.svelte";
  import CameraTakeover from "./components/CameraTakeover.svelte";
  import ImageCollageTakeover from "./components/ImageCollageTakeover.svelte";
  import DriftBackground from "./components/DriftBackground.svelte";
  import NightClock from "./components/NightClock.svelte";
  import Overlay from "./components/Overlay.svelte";
  import RoundStage from "./components/RoundStage.svelte";
  import Stage from "./components/Stage.svelte";
  import StatusPill from "./components/StatusPill.svelte";
  import Takeover from "./components/Takeover.svelte";
  import { pick, type WeatherData } from "./cards/types";
  import { a11y, initA11y, KEY as A11Y_KEY } from "./lib/a11y.svelte";
  import {
    clockFace,
    initClockFace,
    isClockFace,
    KEY as CLOCKFACE_KEY,
    resolvePhotoClock,
    takeLegacyPhotoClock,
  } from "./lib/clockface.svelte";
  import { Connection } from "./lib/connection.svelte";
  import { dayTints } from "./lib/daypart";
  import {
    ensureDevice,
    KEY as DEVICE_KEY,
    reportViewport,
  } from "./lib/device";
  import {
    display,
    initDisplay,
    KEY as DISPLAY_KEY,
    type DisplaySize,
  } from "./lib/display.svelte";
  import { enterEdit } from "./lib/edit.svelte";
  import { initIdle } from "./lib/idle.svelte";
  import { initPlatform, platform, PLATFORM_KEY } from "./lib/platform.svelte";
  import { previewId, startMirror } from "./lib/preview.svelte";
  import { fade } from "svelte/transition";
  import { readLocal, writeLocal } from "./lib/storage";
  import { parseClockTime } from "./lib/format";
  import { clock, startClock, stopClock } from "./lib/time.svelte";
  import { frame } from "./lib/frame.svelte";
  import { isNightClock } from "./lib/nightClock";
  import { applyPrefs, prefs } from "./lib/prefs.svelte";
  import { chimeForFinishedTimers } from "./lib/timerSound.svelte";
  import {
    initMotion,
    motion,
    MOTION_KEY,
    type MotionChoice,
  } from "./lib/tier.svelte";
  import { reset as resetWizard } from "./lib/wizard.svelte";
  import { shuffle } from "./lib/shuffle.svelte";

  const baseUrl = import.meta.env.VITE_API_URL ?? "";
  const client = createClient(baseUrl);

  let connection = $state<Connection | undefined>();
  let deviceId = $state<string>("");
  let error = $state<string | undefined>();
  /** When the next try to reach the server is due (ms epoch). */
  let retryAt = $state(0);
  const retryIn = $derived(
    Math.max(0, Math.ceil((retryAt - clock.now.getTime()) / 1000)),
  );
  let themes = $state<Theme[]>([]);
  let settingsOpen = $state(false);
  // Settings and the setup wizard load when first opened, not at start-up:
  // a kiosk can run for weeks without either, so it shouldn't parse them.
  const settingsSheet = () => import("./components/Settings.svelte");
  const setupWizard = () => import("./components/Wizard.svelte");
  const welcomeScreen = () => import("./components/Welcome.svelte");

  // Small hours (see lib/nightClock): a lone clock on black replaces the
  // dashboard — unless the screen has it switched off, or all the time when
  // it's held on. A tap shows the dashboard for a while (Settings → Night &
  // sleep), then it's back.
  let peekUntil = $state(0);

  const sleeping = $derived.by(() => {
    const view = connection?.view;
    if (!view?.night_clock) return false;
    const due =
      view.night_clock_hold ||
      isNightClock(clock.now, {
        weeknightStart: prefs.night_weeknight_start,
        weekendStart: prefs.night_weekend_start,
        end: prefs.night_end,
      });
    return due && clock.now.getTime() >= peekUntil;
  });

  // Hands-free ambient cycle (Option C): when resting on the photo clock / night clock,
  // periodically reveal the dashboard so the card queue rotates for peek_s seconds.
  $effect(() => {
    if (!prefs.dynamic_shuffle || !sleeping || settingsOpen) return;
    const intervalMs = Math.max(60_000, (prefs.ambient_cycle_m ?? 5) * 60_000);
    const timer = setTimeout(() => {
      peekUntil = Date.now() + (prefs.peek_s ?? 60) * 1000;
    }, intervalMs);
    return () => clearTimeout(timer);
  });

  // Pause dynamic shuffle whenever settings is open
  $effect(() => {
    if (settingsOpen) shuffle.pause();
    else shuffle.resume();
  });
  let setupNeeded = $state(false);

  // A full-screen card (Antigua's recipe) over the dashboard or the night
  // clock. The server takes it down at expires_at; the client check covers a
  // dropped stream and a cached view from before a reload.
  const takeover = $derived.by(() => {
    const t = connection?.view?.takeover;
    return t && Date.parse(t.expires_at) > clock.now.getTime() ? t : null;
  });

  // Day-part tint (lib/daypart): amber around sunrise/sunset, indigo at night.
  // minuteOfDay is a primitive, so the 1 s tick doesn't re-run the tint math.
  const minuteOfDay = $derived(
    clock.now.getHours() * 60 + clock.now.getMinutes(),
  );
  const today = $derived(
    connection?.view
      ? pick<WeatherData>(connection.view, "weather")?.forecast?.[0]
      : undefined,
  );
  // Glass themes keep their own wallpaper; the drift would paint over it.
  const drifting = $derived(
    !!connection?.view?.animated_background &&
      themes.find((t) => t.name === connection?.view?.theme)?.surface !==
        "glass",
  );
  const tints = $derived(
    dayTints(
      minuteOfDay,
      parseClockTime(today?.sunrise),
      parseClockTime(today?.sunset),
    ),
  );

  // Optional spoken updates (Accessibility → Announce updates).
  let announcement = $state("");
  $effect(() => {
    const view = connection?.view;
    if (!a11y.announceUpdates || !view) return;
    const parts: string[] = [];
    if (view.alert)
      parts.push(`Alert: ${view.alert.event}. ${view.alert.headline}`);
    if (view.state === "playing") parts.push("Now playing");
    announcement = parts.join(". ");
  });

  // A custom theme was made or edited since the list was fetched: fetch it
  // again so the new colours show without a reload.
  let themesRev: number | undefined;
  $effect(() => {
    const view = connection?.view;
    if (!view || themesRev === view.theme_rev) return;
    const known = themes.some((t) => t.name === view.theme);
    const first = themesRev === undefined;
    themesRev = view.theme_rev;
    if (first && known) return;
    void client.listThemes().then(
      (list) => (themes = list.themes),
      () => {},
    );
  });

  // Formatting, timings and the night schedule (lib/prefs) for every card.
  $effect(() => {
    applyPrefs(connection?.view?.prefs);
  });

  // A timer that ran out plays this screen's chime (Settings → Timers).
  $effect(() => {
    chimeForFinishedTimers(connection?.view?.data?.timer);
  });

  let activeThemeName = "";
  $effect(() => {
    const view = connection?.view;
    if (!view) return;
    const theme = themes.find((candidate) => candidate.name === view.theme);
    const themeChanged =
      activeThemeName !== "" && activeThemeName !== view.theme;
    activeThemeName = view.theme ?? "";

    const apply = () => {
      if (theme) applyTheme(theme);
      // The profile's accent colour wins over the theme's (Appearance).
      if (theme && view.prefs?.accent) {
        document.documentElement.style.setProperty(
          "--accent",
          view.prefs.accent,
        );
      }
      // The profile's font wins; a theme of your own can bring one too.
      applyFont(view.font ?? theme?.font);
      document.documentElement.dataset.layout = view.layout;
      frame.inset = (view.frame_inset ?? 0) / 100;
      document.documentElement.style.setProperty(
        "--frame-x",
        `${view.frame_inset ?? 0}vw`,
      );
      clockFace.pushed = isClockFace(view.clock_face) ? view.clock_face : null;

      // Liquid Glass wallpaper: pin the URL to the revision so a new upload
      // repaints live displays. rev 0 (or a non-glass theme) → the CSS gradient.
      // With "every theme" on, a solid theme shows it too (styles/base.css).
      const root = document.documentElement;
      const everywhere =
        !!view.prefs?.wallpaper_everywhere && view.wallpaper_rev > 0;
      root.toggleAttribute(
        "data-wallpaper",
        everywhere && theme?.surface !== "glass",
      );
      if (
        (theme?.surface === "glass" || everywhere) &&
        view.wallpaper_rev > 0
      ) {
        root.style.setProperty(
          "--glass-wallpaper",
          `url("/api/wallpaper?v=${view.wallpaper_rev}")`,
        );
        // Heavier after dark so a bright daytime photo doesn't glare at night.
        root.style.setProperty(
          "--glass-scrim",
          root.dataset.dark
            ? "rgba(8, 10, 24, 0.58)"
            : "rgba(18, 22, 38, 0.28)",
        );
      } else {
        root.style.removeProperty("--glass-wallpaper");
        root.style.removeProperty("--glass-scrim");
      }
    };

    if (
      themeChanged &&
      typeof document !== "undefined" &&
      typeof document.startViewTransition === "function" &&
      motion.tier !== "lite" &&
      !motion.reduced
    ) {
      document.startViewTransition(() => {
        apply();
      });
    } else {
      apply();
    }
  });

  // The Photo Clock's settings used to stay in this browser; hand them to
  // the server the first time it has none, so Settings anywhere can see them.
  let legacyChecked = false;
  $effect(() => {
    const view = connection?.view;
    if (legacyChecked || previewId || !deviceId || !view) return;
    legacyChecked = true;
    if (view.photo_clock) return;
    const legacy = takeLegacyPhotoClock();
    if (legacy) void client.updateDevice(deviceId, { photo_clock: legacy });
  });

  // Tell the server how this screen draws itself, for the phone menu's live
  // miniature (lib/preview). Again whenever any of it changes.
  let lookSent = "";
  $effect(() => {
    if (previewId || !deviceId) return;
    const look = {
      clock_face: clockFace.face,
      pi: platform.isPi,
      scale: display.scale,
    };
    const key = JSON.stringify(look);
    if (key === lookSent) return;
    lookSent = key;
    void client.reportLook(deviceId, look);
  });

  // One-time kiosk provisioning for screens with no touch/mouse input: a
  // launch URL like `/?reduceTransparency=1&motion=standard` seeds the same
  // localStorage the Accessibility/Display settings write to, *before*
  // init*() reads it — so an unreachable screen never needs its toggle
  // flipped by hand. This writes raw storage rather than calling the live
  // setA11y/setMotionChoice setters: those also stamp <html> synchronously,
  // which the boot $effect below would track as a dependency and re-trigger
  // itself over (Svelte throws effect_update_depth_exceeded).
  function seedKioskParams(): void {
    const params = new URLSearchParams(location.search);
    if (params.has("reduceTransparency")) {
      const reduceTransparency = params.get("reduceTransparency") !== "0";
      let saved: Record<string, unknown> = {};
      try {
        saved = JSON.parse(readLocal(A11Y_KEY) ?? "{}");
      } catch {
        saved = {};
      }
      writeLocal(A11Y_KEY, JSON.stringify({ ...saved, reduceTransparency }));
    }
    const motionParam = params.get("motion") as MotionChoice | null;
    if (
      motionParam === "auto" ||
      motionParam === "lite" ||
      motionParam === "standard" ||
      motionParam === "rich"
    ) {
      writeLocal(MOTION_KEY, motionParam);
    }
    const sizeParam = params.get("size") as DisplaySize | null;
    if (
      sizeParam === "auto" ||
      sizeParam === "s" ||
      sizeParam === "m" ||
      sizeParam === "l" ||
      sizeParam === "xl"
    ) {
      writeLocal(DISPLAY_KEY, sizeParam);
    }
    const clockParam = params.get("clock");
    if (isClockFace(clockParam)) {
      writeLocal(CLOCKFACE_KEY, clockParam);
    }
    const piParam = params.get("pi");
    if (piParam === "1" || piParam === "0") {
      writeLocal(PLATFORM_KEY, piParam);
    }
    // A kiosk that fails over between a primary and a standby server pins its
    // id here, so it's the same screen (and keeps its card stack) on either.
    const deviceParam = params.get("device");
    if (deviceParam && /^[0-9a-f]{16}$/.test(deviceParam)) {
      writeLocal(DEVICE_KEY, deviceParam);
    }
  }

  // A kiosk display boots the moment the compositor is up — often a beat before
  // pineda-web is answering requests, or straight through a service restart.
  // The SSE stream reconnects itself; this initial handshake didn't, so one
  // transient "Failed to fetch" used to latch the fatal screen until someone
  // reloaded the browser by hand. Retry with backoff instead, and clear the
  // banner once we're through.
  //
  // `stopped`/`retry`/`attempt` live *inside* the effect (not at component
  // scope) on purpose: initPlatform/initA11y/initDisplay/initMotion each read
  // a bit of reactive state to decide what to stamp on <html>, which makes
  // this effect re-run itself once right after the initial commit (the same
  // mechanism seedKioskParams works around above, just one layer short of the
  // effect_update_depth_exceeded case). A component-scope `stopped` flag would
  // have its cleanup set it true on that extra run and never reset it, so the
  // in-flight connect() from the first run — and every run after — would see
  // stopped=true forever and never call conn.start(). Scoping it per-run means
  // each run's cleanup only ever cancels *that run's* in-flight connect().
  $effect(() => {
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;
    let stopMirror: (() => void) | undefined;
    let stopViewport: (() => void) | undefined;

    async function connect(): Promise<void> {
      if (stopped) return;
      try {
        const [id, themeList, config] = await Promise.all([
          previewId ?? ensureDevice(client),
          client.listThemes(),
          client.getConfig(),
        ]);
        if (stopped) return;
        deviceId = id;
        themes = themeList.themes;
        setupNeeded = !previewId && !config.setup_complete;
        const conn = new Connection(baseUrl, id);
        conn.start();
        connection = conn;
        if (previewId) stopMirror = startMirror(client, previewId);
        else stopViewport = reportViewport(baseUrl, id);
        error = undefined;
        attempt = 0;
      } catch (cause) {
        error =
          cause instanceof Error ? cause.message : "Could not reach the server";
        attempt += 1;
        const delay = Math.min(30_000, 1000 * 2 ** Math.min(attempt, 5));
        retryAt = Date.now() + delay;
        retry = setTimeout(() => void connect(), delay);
      }
    }

    // Untracked: the inits read the state they stamp, and the preview's
    // mirror writes that state (Pi mode, scale) on every poll. Tracked, each
    // write re-ran this effect, which reconnected and restarted the mirror in
    // a tight loop that crashed iOS Safari.
    const stopIdle = untrack(() => {
      if (!previewId) seedKioskParams();
      initPlatform();
      initA11y();
      initDisplay();
      initMotion();
      initClockFace();
      startClock();
      void connect();
      return initIdle();
    });
    return () => {
      stopped = true;
      clearTimeout(retry);
      stopMirror?.();
      stopViewport?.();
      connection?.stop();
      stopClock();
      stopIdle();
    };
  });
</script>

{#if connection?.view}
  {#if drifting}
    <DriftBackground />
  {/if}
  <!-- No transition: it steps once a minute by ≤ ~0.005, imperceptibly, where
       a transition would repaint the full viewport every frame on the Pi. -->
  <div class="daytint" aria-hidden="true">
    <span class="warm" style:opacity={tints.warm}></span>
    <span class="cool" style:opacity={tints.cool}></span>
  </div>
{/if}

{#if error && !connection}
  <div class="fatal" role="alert">
    <p>Can't reach the display server</p>
    <span
      >{retryIn > 0 ? `Trying again in ${retryIn} s` : "Trying again…"}. Check
      that the server is on and this device is on your home network.</span
    >
  </div>
{:else if connection?.view?.welcome && !previewId}
  {#await welcomeScreen() then { default: Welcome }}
    <Welcome {deviceId} />
  {/await}
  <Overlay brightness={1} blackout={false} identifyAt={connection.identifyAt} />
{:else if setupNeeded && deviceId}
  {#await setupWizard() then { default: Wizard }}
    <Wizard {deviceId} onDone={() => (setupNeeded = false)} />
  {/await}
{:else if connection?.view && sleeping && !settingsOpen}
  <NightClock
    font={connection.view.night_clock_font}
    color={connection.view.night_clock_color}
    tint={connection.view.night_clock_tint}
    photoClock={resolvePhotoClock(connection.view.photo_clock)}
    weather={pick<WeatherData>(connection.view, "weather")}
    units={connection.view.units}
    nowPlaying={pick(connection.view, "nowPlaying")}
    photo={connection.view.night_clock_hold &&
      connection.view.night_clock_photo}
    onWake={() => (peekUntil = Date.now() + prefs.peek_s * 1000)}
    held={connection.view.night_clock_hold}
    onLeave={() => {
      // A peek covers the round trip, and the small hours if it's late.
      peekUntil = Date.now() + prefs.peek_s * 1000;
      void client.updateDevice(deviceId, { night_clock_hold: false });
    }}
    onSettings={connection.view.locked || previewId
      ? undefined
      : () => (settingsOpen = true)}
  />
  <Overlay
    brightness={connection.view.brightness}
    blackout={connection.view.blackout}
    identifyAt={connection.identifyAt}
    name={connection.view.screen_name}
    colour={connection.view.screen_colour}
  />
{:else if connection?.view}
  <div class="stage-wrap" in:fade={{ duration: 360 }}>
    {#if connection.view.shape === "circle"}
      <RoundStage view={connection.view} />
    {:else if connection.view.alternate && !previewId}
      <Alternate view={connection.view} {deviceId} />
    {:else}
      <Stage view={connection.view} {deviceId} />
    {/if}
  </div>
  <Overlay
    brightness={connection.view.brightness}
    blackout={connection.view.blackout}
    identifyAt={connection.identifyAt}
    name={connection.view.screen_name}
    colour={connection.view.screen_colour}
  />
  {#if !connection.view.locked && !previewId}
    <button
      type="button"
      class="gear"
      aria-label="Settings"
      aria-haspopup="dialog"
      onclick={() => (settingsOpen = true)}
      ><span aria-hidden="true">⚙</span></button
    >
  {/if}
  {#if !previewId}<StatusPill
      status={connection.status}
      since={connection.view?.generated_at}
    />{/if}
  {#if a11y.announceUpdates}
    <div class="visually-hidden" role="status" aria-live="polite">
      {announcement}
    </div>
  {/if}
  {#if settingsOpen}
    {#await settingsSheet() then { default: Settings }}
      <Settings
        {deviceId}
        canEditLayout={!connection.view.locked}
        onEditLayout={() => {
          const v = connection?.view;
          if (!v) return;
          const hero = v.hero.kind === "card" ? (v.hero.card ?? null) : null;
          enterEdit(
            hero,
            v.cards.map((c) => c.id),
          );
          settingsOpen = false;
        }}
        onClose={() => (settingsOpen = false)}
        onRunSetup={() => {
          resetWizard();
          settingsOpen = false;
          setupNeeded = true;
        }}
      />
    {/await}
  {/if}
{:else}
  <div class="loading" role="status">
    <div class="loading-pulse" aria-hidden="true">
      <span class="loading-ring"></span>
      <span class="loading-dot"></span>
    </div>
    <span>Connecting…</span>
  </div>
{/if}

{#if takeover && !settingsOpen && !setupNeeded && !connection?.view?.welcome}
  {#key takeover.shown_at}
    {#if takeover.card.kind === "camera"}
      <CameraTakeover {takeover} />
    {:else if takeover.card.kind === "alarm"}
      <AlarmTakeover {takeover} />
    {:else if takeover.card.kind === "image_search"}
      <ImageCollageTakeover {takeover} />
    {:else}
      <Takeover {takeover} />
    {/if}
  {/key}
{/if}

<style>
  /* Above the wallpaper (canvas background), below all positioned chrome. */
  .stage-wrap {
    height: 100%;
    width: 100%;
  }
  .daytint {
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
  }
  .daytint span {
    position: absolute;
    inset: 0;
  }
  .daytint .warm {
    background: #ff9459; /* dawn/dusk amber */
  }
  .daytint .cool {
    background: #1b2152; /* moonlit indigo */
  }
  .fatal,
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    height: 100%;
    color: var(--on-stage-soft);
    font-size: var(--type-md);
  }
  .fatal p {
    color: var(--on-stage);
  }
  .fatal span,
  .loading span {
    font-size: var(--type-sm);
  }
  .loading-pulse {
    position: relative;
    width: calc(2.4rem * var(--ui-scale));
    height: calc(2.4rem * var(--ui-scale));
    display: grid;
    place-items: center;
  }
  .loading-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid color-mix(in srgb, var(--accent) 40%, transparent);
    animation: ring-pulse 2s cubic-bezier(0.16, 1, 0.3, 1) infinite;
  }
  .loading-dot {
    width: calc(0.6rem * var(--ui-scale));
    height: calc(0.6rem * var(--ui-scale));
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 14px var(--accent);
    animation: dot-breathe 2s ease-in-out infinite;
  }
  @keyframes ring-pulse {
    0% {
      transform: scale(0.6);
      opacity: 0.8;
    }
    100% {
      transform: scale(1.6);
      opacity: 0;
    }
  }
  @keyframes dot-breathe {
    0%,
    100% {
      transform: scale(0.85);
      opacity: 0.6;
    }
    50% {
      transform: scale(1.15);
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .loading-ring,
    .loading-dot {
      animation: none;
    }
  }
  .gear {
    position: fixed;
    top: max(var(--space-2), env(safe-area-inset-top));
    right: calc(
      max(var(--space-2), env(safe-area-inset-right)) + var(--frame-x, 0px)
    );
    width: var(--icon-tap);
    height: var(--icon-tap);
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: color-mix(in srgb, var(--on-stage) 10%, transparent);
    color: var(--on-stage-soft);
    font-size: calc(1rem * var(--ui-scale));
    cursor: pointer;
    opacity: 0.5;
    z-index: 12;
  }
  .gear:hover,
  .gear:focus-visible {
    opacity: 1;
  }
  @media (prefers-reduced-motion: no-preference) {
    .gear {
      transition: opacity var(--dur-fast) linear;
    }
  }
</style>
