<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { tick, untrack } from "svelte";
  import type { CardView, Theme } from "@pinedaview/protocol";

  import { a11y } from "../lib/a11y.svelte";
  import { FACES } from "../lib/clockface.svelte";
  import { modal } from "../lib/modal";
  import { provideSettings, SettingsState } from "../lib/settings.svelte";
  import { cellMotionOn } from "../lib/cellMotion";
  import { motion } from "../lib/tier.svelte";
  import AccessibilitySettings from "./AccessibilitySettings.svelte";
  import AppearanceSettings from "./AppearanceSettings.svelte";
  import CardsSettings from "./CardsSettings.svelte";
  import ConnectSettings from "./ConnectSettings.svelte";
  import Help from "./Help.svelte";
  import NightSettings from "./NightSettings.svelte";
  import PhotosSettings from "./PhotosSettings.svelte";
  import ScreensSettings from "./ScreensSettings.svelte";
  import Section from "./Section.svelte";
  import ServerSettings from "./ServerSettings.svelte";
  import TimersSettings from "./TimersSettings.svelte";
  import TimeWeatherSettings from "./TimeWeatherSettings.svelte";
  import "./settings/settings.css";

  interface Props {
    deviceId: string;
    canEditLayout: boolean;
    onEditLayout: () => void;
    onClose: () => void;
    onRunSetup: () => void;
  }
  let { deviceId, canEditLayout, onEditLayout, onClose, onRunSetup }: Props =
    $props();

  // The sheet is mounted per opening, so the id it starts with is the one.
  const settings = provideSettings(new SettingsState(untrack(() => deviceId)));
  let cards = $state<CardView[]>([]);
  let themes = $state<Theme[]>([]);
  let version = $state("");
  let connected = $state<number | null>(null);
  let running = $state<number | null>(null);
  let failed = $state(false);
  $effect(() => {
    settings.load().catch(() => (failed = true));
    void settings.client.listCards().then((c) => (cards = c));
    void settings.client.listThemes().then((t) => (themes = t.themes));
    void settings.client.health().then((h) => (version = h.app_version));
    refreshCounts();
  });

  /** The connection and timer counts in the section summaries; they change
      inside their sections, so they're read again as sections close. */
  function refreshCounts(): void {
    void settings.client
      .listConnections()
      .then((list) => (connected = list.filter((c) => c.connected).length))
      .catch(() => {});
    void settings.client
      .listTimers()
      .then((list) => (running = list.length))
      .catch(() => {});
  }

  // Line icons for the section tiles, iOS Settings style: white on a colour.
  const ICONS = {
    appearance:
      '<circle cx="12" cy="12" r="8.5"/><circle cx="8.5" cy="10" r="1.2"/><circle cx="12" cy="7.5" r="1.2"/><circle cx="15.5" cy="10" r="1.2"/><path d="M12 20.5c1.4 0 1.7-1.6 1-2.6-.6-.9 0-2.4 1.4-2.4h2.1"/>',
    time: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/>',
    connect:
      '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    cards:
      '<rect x="4" y="4" width="9" height="9" rx="2"/><rect x="15" y="4" width="5" height="9" rx="1.5"/><rect x="4" y="15" width="16" height="5" rx="1.5"/>',
    photos:
      '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="m4 17 5-4.5 3.5 3 2.5-2 5 4"/>',
    night: '<path d="M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z"/>',
    timers:
      '<circle cx="12" cy="13.5" r="7"/><path d="M12 13.5V10M10 3h4M18.5 7l1.2-1.2"/>',
    accessibility:
      '<circle cx="12" cy="4.8" r="1.6"/><path d="M5 8.5c2.3.7 4.6 1 7 1s4.7-.3 7-1M12 9.5v4.5m0 0-3 6.5m3-6.5 3 6.5"/>',
    screens:
      '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>',
    server:
      '<rect x="4" y="4" width="16" height="6" rx="1.5"/><rect x="4" y="14" width="16" height="6" rx="1.5"/><path d="M8 7h.01M8 17h.01"/>',
    help: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6M12 17h.01"/>',
  } as const;

  const SECTIONS = [
    {
      id: "appearance",
      title: "Appearance",
      group: "display",
      tint: "#af52de",
      terms:
        "theme colour color accent font typeface clock face background wallpaper image sunset night animated interface size",
    },
    {
      id: "cards",
      title: "Cards & layout",
      group: "display",
      tint: "#ff9500",
      terms:
        "cards rearrange order layout featured hero large rotation speed pace quotes news headlines filter hide words commute radar",
    },
    {
      id: "photos",
      title: "Photos",
      group: "display",
      tint: "#ff2d55",
      terms:
        "photo frame slideshow upload rotate reorder shuffle newest crop fit guests approve review background",
    },
    {
      id: "night",
      title: "Night & sleep",
      group: "display",
      tint: "#5856d6",
      terms:
        "night clock sleep bedtime dim dimming brightness screen off blackout schedule tap",
    },
    {
      id: "time",
      title: "Time & weather",
      group: "info",
      tint: "#0a84ff",
      terms:
        "weather location city zip units temperature fahrenheit celsius 12-hour 24-hour clock date format countdown morning",
    },
    {
      id: "connect",
      title: "Connect",
      group: "info",
      tint: "#30b0c7",
      terms:
        "connect integrations accounts calendar apple icloud google proton ics link home assistant antigua alarms cameras go2rtc airplay music mqtt maps key",
    },
    {
      id: "timers",
      title: "Timers",
      group: "info",
      tint: "#34c759",
      terms: "timer countdown kitchen minutes sound chime bell beep",
    },
    {
      id: "accessibility",
      title: "Accessibility",
      group: "system",
      tint: "#007aff",
      terms:
        "motion contrast text size transparency announce screen reader reduce lite",
    },
    {
      id: "screens",
      title: "Screens & profiles",
      group: "system",
      tint: "#8e8e93",
      terms:
        "device screen name profile pair remove identify lock mirror copy settings",
    },
    {
      id: "server",
      title: "Backup & server",
      group: "system",
      tint: "#636366",
      terms:
        "backup export import restore api key google maps https tailscale certificate setup version about",
    },
    {
      id: "help",
      title: "Help",
      group: "system",
      tint: "#8e8e93",
      terms: "help how to guide troubleshoot support",
    },
  ] as const;
  type SectionId = (typeof SECTIONS)[number]["id"];
  const GROUPS = ["display", "info", "system"] as const;

  const UNITS = { imperial: "°F", metric: "°C" } as const;

  // A glance at each section's current state, beside its title.
  const summaries = $derived.by((): Partial<Record<SectionId, string>> => {
    const config = settings.config;
    const profile = settings.profile;
    const screen = settings.screen;
    const out: Partial<Record<SectionId, string>> = {};
    if (profile) {
      const theme = themes.find((t) => t.name === profile.theme)?.label;
      const face = FACES.find((f) => f.id === profile.clock_face)?.label;
      out.appearance = [theme, face].filter(Boolean).join(" · ");
      out.cards = `${profile.pace[0]?.toUpperCase()}${profile.pace.slice(1)} pace`;
      out.photos =
        profile.photo_hold_s >= 60
          ? `${profile.photo_hold_s / 60} min each`
          : `${profile.photo_hold_s} s each`;
    }
    if (screen) {
      out.night = screen.night_clock
        ? screen.night_clock_hold
          ? "Showing now"
          : "On"
        : "Off";
    }
    if (config) {
      out.time = [
        config.location_label || config.location_query,
        UNITS[config.units],
        config.time_format === "24h" ? "24-hour" : "12-hour",
      ].join(" · ");
    }
    if (connected !== null)
      out.connect = connected ? `${connected} connected` : "None yet";
    if (running) out.timers = `${running} running`;
    const access = [
      motion.choice === "lite" && "Reduced motion",
      a11y.largerText && "Larger text",
      a11y.highContrast && "High contrast",
      a11y.reduceTransparency && "Less transparency",
    ].filter(Boolean);
    out.accessibility = access.length ? access.join(" · ") : "Standard";
    out.screens =
      settings.activeScreens.length > 1
        ? `${settings.activeScreens.length} screens`
        : (settings.screen?.name ?? "");
    if (version) out.server = `Version ${version}`;
    return out;
  });

  let query = $state("");
  let open = $state<Record<string, boolean>>({});
  let body = $state<HTMLElement>();

  /** One setting found by search: its name, where it lives, and its row. */
  interface Found {
    key: string;
    label: string;
    hint: string;
    section: SectionId;
    row: HTMLElement;
  }
  let found = $state<Found[]>([]);

  // Every panel stays rendered (closed ones just hidden), so search can read
  // the setting names straight off the page rather than keep a second list.
  $effect(() => {
    const q = query.trim().toLowerCase();
    void settings.profile;
    void settings.screen;
    if (!q || !body) {
      found = [];
      return;
    }
    void tick().then(() => {
      if (!body) return;
      const rows = [...body.querySelectorAll<HTMLElement>("[data-field]")];
      found = rows.flatMap((row, i) => {
        const label = row.querySelector(".label")?.textContent?.trim() ?? "";
        const hint = row.querySelector(".hint")?.textContent?.trim() ?? "";
        const section = row.closest<HTMLElement>("[data-section]")?.dataset
          .section as SectionId | undefined;
        if (!section || !`${label} ${hint}`.toLowerCase().includes(q))
          return [];
        return [{ key: `${section}-${i}`, label, hint, section, row }];
      });
    });
  });

  const shown = $derived.by((): Set<SectionId> => {
    const q = query.trim().toLowerCase();
    if (!q) return new Set(SECTIONS.map((s) => s.id));
    return new Set(
      SECTIONS.filter((s) =>
        `${s.title} ${s.terms}`.toLowerCase().includes(q),
      ).map((s) => s.id),
    );
  });

  function title(id: SectionId): string {
    return SECTIONS.find((s) => s.id === id)?.title ?? "";
  }

  function toggle(id: string): void {
    open[id] = !open[id];
    if (!open[id]) refreshCounts();
  }

  /** Go to a setting search found: open its section and point at the row. */
  async function reveal(item: Found): Promise<void> {
    query = "";
    open[item.section] = true;
    await tick();
    item.row.scrollIntoView({ block: "center", behavior: "smooth" });
    item.row.classList.remove("found");
    void item.row.offsetWidth;
    item.row.classList.add("found");
  }

  // With Cards & layout open on a wide screen, the sheet steps aside and the
  // dimming lifts, so the dashboard behind it can be watched rearranging
  // itself as the switches change. The sheet glides to its new side.
  let viewport = $state(
    typeof window === "undefined" ? 1280 : window.innerWidth,
  );
  let sheet = $state<HTMLElement>();
  const docked = $derived(
    !!open.cards && settings.editingHere && !query.trim() && viewport >= 1100,
  );
  let sheetFrom: DOMRect | null = null;
  $effect.pre(() => {
    void docked;
    sheetFrom = sheet?.getBoundingClientRect() ?? null;
  });
  $effect(() => {
    void docked;
    const el = sheet;
    const from = sheetFrom;
    if (!el || !from || typeof el.animate !== "function") return;
    if (!cellMotionOn()) return;
    const dx = from.left - el.getBoundingClientRect().left;
    if (Math.abs(dx) < 1) return;
    el.animate([{ transform: `translateX(${dx}px)` }, { transform: "none" }], {
      duration: 460,
      easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    });
  });

  // Pull the sheet down by its top to put it away, as on a phone.
  let drag = $state<{ y0: number; t0: number; dy: number } | null>(null);
  function dragStart(e: PointerEvent): void {
    if (e.button !== 0 || (e.target as HTMLElement).closest("button")) return;
    drag = { y0: e.clientY, t0: e.timeStamp, dy: 0 };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function dragMove(e: PointerEvent): void {
    if (drag) drag.dy = Math.max(0, e.clientY - drag.y0);
  }
  function dragEnd(e: PointerEvent): void {
    if (!drag) return;
    const { dy, t0 } = drag;
    const fast = dy / Math.max(1, e.timeStamp - t0) > 0.6;
    drag = null;
    if (dy > 140 || (fast && dy > 40)) onClose();
  }
</script>

<svelte:window bind:innerWidth={viewport} />

<div class="scrim" class:docked use:modal={{ onClose }}>
  <button
    type="button"
    class="backdrop"
    tabindex="-1"
    aria-label="Close settings"
    onclick={onClose}
  ></button>

  <div
    class="sheet settings-sheet"
    bind:this={sheet}
    class:dragging={drag !== null}
    style:transform={drag?.dy ? `translateY(${drag.dy}px)` : undefined}
    role="dialog"
    aria-modal="true"
    aria-labelledby="settings-title"
    tabindex="-1"
  >
    <div
      role="presentation"
      class="top"
      onpointerdown={dragStart}
      onpointermove={dragMove}
      onpointerup={dragEnd}
      onpointercancel={() => (drag = null)}
    >
      <div class="grip" aria-hidden="true"></div>
      <div class="head">
        <h2 id="settings-title">Settings</h2>
        <button class="done" onclick={onClose}>Done</button>
      </div>
    </div>

    {#if settings.activeScreens.length > 1}
      <label class="target" class:away={!settings.editingHere}>
        <span>Editing</span>
        <select bind:value={settings.targetId}>
          {#each settings.activeScreens as d (d.id)}
            <option value={d.id}
              >{d.name}{d.id === deviceId ? " (this screen)" : ""}</option
            >
          {/each}
        </select>
      </label>
    {/if}

    <input
      class="search"
      type="search"
      placeholder="Search settings"
      aria-label="Search settings"
      bind:value={query}
    />

    <div class="body" bind:this={body}>
      {#if failed}
        <p class="none" role="alert">
          Couldn't load your settings. Check that the server is running, then
          open Settings again.
        </p>
      {/if}

      {#if query.trim() && found.length}
        <ul class="found" aria-label="Matching settings">
          {#each found as item (item.key)}
            <li>
              <button type="button" onclick={() => reveal(item)}>
                <span class="found-label">{item.label}</span>
                <span class="found-where">{title(item.section)}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}

      {#each GROUPS as group (group)}
        <div
          class="group"
          hidden={!SECTIONS.some(
            (s) =>
              s.group === group &&
              (shown.has(s.id) || found.some((f) => f.section === s.id)),
          )}
        >
          {#each SECTIONS.filter((s) => s.group === group) as s (s.id)}
            <Section
              id={s.id}
              title={s.title}
              hint={summaries[s.id]}
              icon={ICONS[s.id]}
              tint={s.tint}
              open={open[s.id] ?? false}
              hidden={!shown.has(s.id) &&
                !found.some((f) => f.section === s.id)}
              onToggle={() => toggle(s.id)}
            >
              {#if s.id === "appearance"}
                <AppearanceSettings />
              {:else if s.id === "time"}
                <TimeWeatherSettings />
              {:else if s.id === "connect"}
                <ConnectSettings />
              {:else if s.id === "cards"}
                <CardsSettings
                  {cards}
                  canEditLayout={canEditLayout && settings.editingHere}
                  {onEditLayout}
                />
              {:else if s.id === "photos"}
                <PhotosSettings />
              {:else if s.id === "night"}
                <NightSettings />
              {:else if s.id === "timers"}
                <TimersSettings />
              {:else if s.id === "accessibility"}
                <AccessibilitySettings />
              {:else if s.id === "screens"}
                <ScreensSettings />
              {:else if s.id === "server"}
                <ServerSettings {onRunSetup} />
              {:else}
                <Help />
              {/if}
            </Section>
          {/each}
        </div>
      {/each}
      {#if query.trim() && shown.size === 0 && found.length === 0}
        <p class="none">
          Nothing matches “{query.trim()}”. Try a simpler word, like “clock” or
          “photo”.
        </p>
      {/if}
    </div>

    {#if settings.notice}
      <p
        class="notice"
        class:error={settings.notice.error}
        class:actionable={!!settings.notice.action}
        role={settings.notice.error ? "alert" : "status"}
      >
        {settings.notice.text}
        {#if settings.notice.action}
          <button type="button" onclick={() => settings.act()}
            >{settings.notice.action.label}</button
          >
        {/if}
      </p>
    {/if}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding-inline: var(--frame-x, 0px);
    padding-block: var(--frame-y, 0px);
    z-index: 40;
  }
  .backdrop {
    position: absolute;
    inset: 0;
    border: none;
    padding: 0;
    background: color-mix(in srgb, var(--stage) 55%, black);
    cursor: pointer;
  }
  .docked {
    justify-content: flex-end;
    padding-right: calc(
      max(var(--space-3), env(safe-area-inset-right)) + var(--frame-x, 0px)
    );
  }
  .docked .backdrop {
    opacity: 0.3;
  }
  @media (prefers-reduced-motion: no-preference) {
    .backdrop {
      transition: opacity var(--dur-mid) ease;
    }
  }
  .sheet {
    position: relative;
    width: min(600px, 100%);
    /* A fixed height, so typing a search doesn't make the sheet jump. */
    height: calc(92dvh - 2 * var(--frame-y, 0px));
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-3)
      max(var(--space-3), env(safe-area-inset-bottom));
    border-radius: 24px 24px 0 0;
    background: var(--stage);
    color: var(--on-stage);
  }
  .sheet:not(.dragging) {
    transition: transform var(--dur-fast) var(--ease-spring);
  }
  .top {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: calc(-1 * var(--space-3)) calc(-1 * var(--space-3)) 0;
    padding: var(--space-3) var(--space-3) 0;
    touch-action: none;
    cursor: grab;
  }
  .grip {
    width: 36px;
    height: 4px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--on-stage) 25%, transparent);
    align-self: center;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .head h2 {
    font-size: var(--type-md);
    font-weight: 600;
  }
  .done {
    min-height: 2.75rem;
    padding: 0 var(--space-2);
    border: none;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--type-sm);
    font-weight: 600;
    cursor: pointer;
  }
  .done:active {
    opacity: 0.6;
  }
  .target {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--type-sm);
    color: var(--on-stage-soft);
  }
  .target select {
    flex: 1;
  }
  /* Editing another screen: tinted, so nobody thinks it's this one. */
  .target.away {
    padding: 6px 6px 6px 12px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    color: var(--on-stage);
  }
  .search {
    font: inherit;
    font-size: var(--type-sm);
    min-height: 2.75rem;
    padding: 0 16px;
    border-radius: var(--radius-pill);
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    background: color-mix(in srgb, var(--on-stage) 5%, transparent);
    color: var(--on-stage);
  }
  .body {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  .group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .group[hidden] {
    display: none;
  }
  .group + .group {
    margin-top: var(--space-3);
  }
  /* One run of rows, rounded at the ends only, like an inset table. */
  .group > :global(.section) {
    border-radius: 4px;
  }
  .group > :global(.section:first-child) {
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
  }
  .group > :global(.section:last-child) {
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
  }
  .found {
    list-style: none;
    margin: 0 0 var(--space-3);
    padding: 0;
    border-radius: 14px;
    background: color-mix(in srgb, var(--on-stage) 5%, transparent);
    overflow: hidden;
  }
  .found li + li {
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 9%, transparent);
  }
  .found button {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    width: 100%;
    padding: 10px var(--space-3);
    border: none;
    background: none;
    color: var(--on-stage);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .found button:active {
    background: color-mix(in srgb, var(--on-stage) 6%, transparent);
  }
  .found-label {
    font-size: var(--type-sm);
    font-weight: 500;
  }
  .found-where {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  .none {
    font-size: var(--type-sm);
    color: var(--on-stage-soft);
    padding: var(--space-2);
  }
  .notice {
    position: absolute;
    left: 50%;
    bottom: max(var(--space-4), env(safe-area-inset-bottom));
    transform: translateX(-50%);
    max-width: calc(100% - 2 * var(--space-3));
    padding: 8px 16px;
    border-radius: var(--radius-pill);
    background: var(--on-stage);
    color: var(--stage);
    font-size: var(--type-sm);
    font-weight: 500;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
    pointer-events: none;
  }
  .notice.actionable {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-right: 6px;
    pointer-events: auto;
  }
  .notice button {
    min-height: 2.25rem;
    padding: 0 12px;
    border: none;
    border-radius: var(--radius-pill);
    background: none;
    color: var(--accent);
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }
  .notice.error {
    background: #c9363c;
    color: #fff;
  }
</style>
