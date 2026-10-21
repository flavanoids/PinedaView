<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import {
    createClient,
    type CardView,
    type Device,
    type LayoutSnapshot,
    type Profile,
    type Theme,
  } from "@pinedaview/protocol";

  import { getLayout, resolveTier } from "../layouts/resolve";
  import {
    addBrick,
    columnCount,
    fromStack,
    pack,
    removeBrick,
    rowCount,
    sameLayout,
    setSize,
    shift,
    sizeOf,
    swap,
    TINT_SLOT,
    toBricks,
    UNIT,
    type Bricks,
    type Grid,
    type GridItem,
    type Size,
  } from "../lib/grid";
  import Dialog from "./Dialog.svelte";
  import GridThumb from "./GridThumb.svelte";
  import { layoutWarnings, type ScreenSize } from "./warnings";

  const client = createClient(import.meta.env.VITE_API_URL ?? "");

  // Cards that feed others and have no face of their own.
  const NO_FACE = new Set(["daily-content"]);

  // Cards that step aside on some days; their spot stays put but empty.
  const SOMETIMES_EMPTY: Record<string, string> = {
    radar: "Hides on dry days — its spot stays empty until rain is likely.",
    "on-this-day":
      "Only shows on days with a photo from this date — otherwise its spot stays empty.",
  };

  const SIZES: { size: Size; label: string }[] = [
    { size: "s", label: "Small" },
    { size: "m", label: "Medium" },
    { size: "l", label: "Large" },
  ];
  const SIZE_NAME: Record<Size, string> = {
    s: "Small",
    m: "Medium",
    l: "Large",
  };

  let phase = $state<"loading" | "pick" | "ready" | "error">("loading");
  let screenId = $state(
    new URLSearchParams(location.search).get("screen") ?? "",
  );
  let devices = $state<Device[]>([]);
  let profiles = $state<Profile[]>([]);
  let cards = $state<CardView[]>([]);
  let themes = $state<Theme[]>([]);
  let photoThumb = $state("");

  const device = $derived(devices.find((d) => d.id === screenId));
  const profile = $derived(
    profiles.find((p) => p.id === device?.profile_id) ?? profiles[0],
  );
  const theme = $derived(themes.find((t) => t.name === profile?.theme));
  const tier = $derived(
    resolveTier(
      getLayout(device?.layout ?? profile?.layout ?? "wide_grid"),
      device?.viewport_w ?? 1280,
    ),
  );
  const screen = $derived<ScreenSize>({
    width: device?.viewport_w ?? null,
    height: device?.viewport_h ?? null,
    fills: !!device?.locked && tier.id === "wide",
  });
  const placeable = $derived(
    cards.filter((c) => c.status === "ready" && !NO_FACE.has(c.id)),
  );

  const EMPTY: Bricks = {
    cells: 4,
    heroW: 2,
    heroH: 2,
    hero: null,
    side: "left",
    pieces: [],
  };
  /** What's on the screen now (null = the automatic layout). */
  let saved = $state<Grid | null>(null);
  /** Where this editing session started; "unsaved" means different from it. */
  let baseline = $state<Bricks>(EMPTY);
  let draft = $state<Bricks>(EMPTY);
  let undoStack = $state<Bricks[]>([]);
  let redoStack = $state<Bricks[]>([]);
  let selected = $state<string | null>(null);
  let saving = $state(false);
  /** The draft as the screen will draw it. */
  const grid = $derived(pack(draft));
  const edited = $derived(!sameLayout(grid, pack(baseline)));
  /** The editor redraws a saved layout at this screen's sizes, so what it
   *  shows can differ from what the screen has; then Save puts it there. */
  const dirty = $derived(edited || (!!saved && !sameLayout(grid, saved)));

  // ── loading ────────────────────────────────────────────────────────────
  async function load(): Promise<void> {
    try {
      const [ds, ps, cs, ts] = await Promise.all([
        client.listDevices(),
        client.listProfiles(),
        client.listCards(),
        client.listThemes(),
      ]);
      devices = ds;
      profiles = ps;
      cards = cs;
      themes = ts.themes;
      if (!ds.some((d) => d.id === screenId)) {
        const only = recent.length === 1 ? recent[0] : undefined;
        if (!only) {
          phase = "pick";
          return;
        }
        screenId = only.id;
      }
      await openScreen();
      void client.listPhotos().then((list) => {
        const first = list[0];
        if (first) photoThumb = client.photoThumbUrl(first.name);
      });
    } catch {
      phase = "error";
    }
  }

  async function openScreen(): Promise<void> {
    const d = devices.find((x) => x.id === screenId);
    if (!d) return;
    const url = new URL(location.href);
    url.searchParams.set("screen", d.id);
    history.replaceState(null, "", url);
    saved = d.grid ?? null;
    const start = saved ? asBricks(d, saved) : await automatic(d);
    baseline = start;
    draft = start;
    undoStack = [];
    redoStack = [];
    selected = null;
    phase = "ready";
  }

  function tierOf(d: Device) {
    const p = profiles.find((x) => x.id === d.profile_id);
    return resolveTier(
      getLayout(d.layout ?? p?.layout ?? "wide_grid"),
      d.viewport_w ?? 1280,
    );
  }

  /** A saved grid, read back as bricks at this screen's Large size. */
  function asBricks(d: Device, g: Grid): Bricks {
    const t = tierOf(d);
    return toBricks(g, t.heroColSpan, t.heroRowSpan);
  }

  /** The automatic layout this screen shows now, as starting bricks. */
  async function automatic(d: Device): Promise<Bricks> {
    const p = profiles.find((x) => x.id === d.profile_id);
    const view = await client.view(d.id).catch(() => null);
    const ok = new Set(placeable.map((c) => c.id));
    const stack = (d.card_stack ?? p?.card_stack ?? []).filter(
      (c) => ok.has(c) && !(d.cards_off ?? []).includes(c),
    );
    const pinned = d.hero_card ?? p?.hero_card ?? null;
    const shown =
      view?.hero.kind === "card" ? (view.hero.card ?? null) : pinned;
    const hero = shown && stack.includes(shown) ? shown : (stack[0] ?? null);
    const t = tierOf(d);
    return fromStack(
      stack,
      hero,
      columnCount(t.columns),
      t.heroColSpan,
      t.heroRowSpan,
    );
  }

  void load();

  // ── editing ────────────────────────────────────────────────────────────
  /** Cards that just clicked into a new spot, for the little snap. */
  let snapped = $state<string[]>([]);
  function commit(next: Bricks, say?: string): void {
    if (sameLayout(pack(next), grid)) return;
    const before = grid;
    undoStack = [...undoStack.slice(-49), draft];
    redoStack = [];
    draft = next;
    snapped = moved(before, pack(next));
    setTimeout(() => (snapped = []), 300);
    if (say) announce(say);
  }
  /** Cards whose spot changed between two layouts. */
  function moved(a: Grid, b: Grid): string[] {
    return b.items
      .filter((i) => {
        const o = a.items.find((x) => x.card === i.card);
        return !o || o.x !== i.x || o.y !== i.y || o.w !== i.w || o.h !== i.h;
      })
      .map((i) => i.card);
  }
  function undo(): void {
    const prev = undoStack.at(-1);
    if (!prev) return;
    redoStack = [...redoStack, draft];
    undoStack = undoStack.slice(0, -1);
    draft = prev;
    announce("Undone");
  }
  function redo(): void {
    const next = redoStack.at(-1);
    if (!next) return;
    undoStack = [...undoStack, draft];
    redoStack = redoStack.slice(0, -1);
    draft = next;
    announce("Redone");
  }

  function name(card: string): string {
    return (
      cards.find((c) => c.id === card)?.name ??
      card.replace(/-/g, " ").replace(/^./, (m) => m.toUpperCase())
    );
  }
  function tint(card: string): string {
    const slot = TINT_SLOT[card] ?? "generic";
    return (
      theme?.cards[slot] ??
      theme?.cards.generic ??
      theme?.cards.weather ??
      "#3a3732"
    );
  }

  const selSize = $derived(selected ? sizeOf(draft, selected) : undefined);
  const selIndex = $derived(draft.pieces.findIndex((p) => p.card === selected));
  /** Room beside the Large card to put it on either side. */
  const canSide = $derived(draft.heroW < draft.cells);
  const tray = $derived(
    placeable.filter((c) => !grid.items.some((i) => i.card === c.id)),
  );
  const warnings = $derived(
    layoutWarnings(
      grid,
      screen,
      name,
      // The listing marks the kitchen screen; the Device type predates it.
      !!(device as { home?: boolean } | undefined)?.home,
    ),
  );

  function resize(card: string, size: Size): void {
    const old = draft.hero;
    const swapped = size === "l" && old && old !== card;
    commit(
      setSize(draft, card, size),
      swapped
        ? `${name(card)} is Large; ${name(old)} took its old spot`
        : `${name(card)} is ${SIZE_NAME[size]}`,
    );
  }
  function setSide(side: "left" | "right"): void {
    commit({ ...draft, side }, `Large card on the ${side}`);
  }
  function reorder(card: string, by: -1 | 1): void {
    commit(
      shift(draft, card, by),
      `${name(card)} moved ${by < 0 ? "earlier" : "later"}`,
    );
  }
  function add(card: string): void {
    commit(addBrick(draft, card), `${name(card)} added`);
    selected = card;
  }
  function remove(card: string): void {
    const doIt = () => {
      const before = draft;
      commit(removeBrick(draft, card));
      selected = null;
      say(`${name(card)} removed.`, {
        label: "Undo",
        run: () => commit(before, `${name(card)} is back`),
      });
    };
    if (card === "photo") {
      ask({
        title: "Remove the photo card?",
        lines: [
          "The QR code for these settings lives on the photo card. Without it you'll need to type the settings address on your phone to get back here.",
        ],
        confirm: "Remove it",
        danger: true,
        run: doIt,
      });
    } else doIt();
  }

  // ── the canvas: drag a card onto another to trade spots ─────────────────
  let canvasEl = $state<HTMLElement>();
  let canvasW = $state(0);
  let viewportH = $state(800);
  // Tiles glide when they move, but not into place on first paint (they'd
  // animate in from the pre-measure width).
  let settled = $state(false);
  $effect(() => {
    if (canvasW > 0 && !settled) requestAnimationFrame(() => (settled = true));
  });
  const unitW = $derived(canvasW / grid.cols);
  const rows = $derived(Math.max(UNIT, rowCount(grid.items)));
  // A wall display splits its height evenly between the rows, so the preview
  // keeps the screen's shape; a scrolling screen just stacks rows.
  const aspect = $derived(
    screen.fills && screen.width && screen.height
      ? screen.height / screen.width
      : null,
  );
  const unitH = $derived(
    aspect ? (canvasW * aspect) / rows : Math.max(26, unitW * 0.75),
  );
  const canvasH = $derived(rows * unitH);

  let drag = $state<{
    card: string;
    x0: number;
    y0: number;
    dx: number;
    dy: number;
    live: boolean;
    /** The card it would trade spots with if dropped now. */
    over: string | null;
  } | null>(null);

  function onDown(e: PointerEvent, item: GridItem) {
    if (e.button !== 0) return;
    e.stopPropagation();
    drag = {
      card: item.card,
      x0: e.clientX,
      y0: e.clientY,
      dx: 0,
      dy: 0,
      live: false,
      over: null,
    };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onMove(e: PointerEvent): void {
    if (!drag || !canvasEl) return;
    const dx = e.clientX - drag.x0;
    const dy = e.clientY - drag.y0;
    if (!drag.live && Math.hypot(dx, dy) < 8) return;
    drag.live = true;
    drag.dx = dx;
    drag.dy = dy;
    const r = canvasEl.getBoundingClientRect();
    const ux = (e.clientX - r.left) / unitW;
    const uy = (e.clientY - r.top) / unitH;
    const hit = grid.items.find(
      (i) => ux >= i.x && ux < i.x + i.w && uy >= i.y && uy < i.y + i.h,
    );
    drag.over = hit && hit.card !== drag.card ? hit.card : null;
  }
  function onUp(): void {
    if (drag?.live && drag.over) {
      const { card, over } = drag;
      commit(
        swap(draft, card, over),
        `${name(card)} and ${name(over)} swapped`,
      );
      selected = card;
    } else if (drag && !drag.live) {
      selected = selected === drag.card ? null : drag.card;
    }
    drag = null;
  }

  function onTileKey(e: KeyboardEvent, item: GridItem): void {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      selected = selected === item.card ? null : item.card;
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      remove(item.card);
    }
  }

  // ── messages, dialogs, toasts ──────────────────────────────────────────
  let live = $state("");
  function announce(text: string): void {
    live = text;
  }

  let dialog = $state<{
    title: string;
    lines: string[];
    confirm: string;
    cancel?: string;
    danger?: boolean;
    run: () => void | Promise<void>;
  } | null>(null);
  function ask(d: NonNullable<typeof dialog>): void {
    dialog = d;
  }

  let toast = $state<{
    text: string;
    action?: { label: string; run: () => void };
  } | null>(null);
  let toastTimer: ReturnType<typeof setTimeout> | undefined;
  function say(text: string, action?: { label: string; run: () => void }) {
    clearTimeout(toastTimer);
    toast = { text, action };
    toastTimer = setTimeout(() => (toast = null), action ? 9000 : 4000);
  }

  // ── saving & the other big actions ─────────────────────────────────────
  async function put(id: string, grid: Grid | null): Promise<Device> {
    const d = await client.setGrid(id, grid);
    devices = devices.map((x) => (x.id === d.id ? d : x));
    return d;
  }

  function save(): void {
    const stops = warnings.filter((w) => w.level === "stop");
    if (stops.length) {
      ask({
        title: "Save it anyway?",
        lines: stops.map((w) => w.text),
        confirm: "Save anyway",
        run: doSave,
      });
    } else void doSave();
  }
  async function doSave(): Promise<void> {
    if (!device) return;
    saving = true;
    const before = saved;
    try {
      await put(device.id, grid);
      saved = grid;
      baseline = draft;
      say(`Saved — ${device.name} is updating now.`, {
        label: "Undo",
        run: () => void restoreSaved(before),
      });
    } catch {
      say("Couldn't save — check the connection and try again.");
    } finally {
      saving = false;
    }
  }
  async function restoreSaved(g: Grid | null): Promise<void> {
    if (!device) return;
    try {
      await put(device.id, g);
      saved = g;
      const back = g ? asBricks(device, g) : await automatic(device);
      baseline = back;
      commit(back);
      say("Put back the way it was.");
    } catch {
      say("Couldn't undo that — check the connection.");
    }
  }

  function goAutomatic(): void {
    ask({
      title: "Let the screen arrange itself?",
      lines: [
        "The screen goes back to placing cards automatically. This layout is kept under Earlier layouts in case you want it back.",
      ],
      confirm: "Go automatic",
      danger: true,
      run: async () => {
        if (!device) return;
        try {
          await put(device.id, null);
          saved = null;
          const auto = await automatic(device);
          baseline = auto;
          draft = auto;
          undoStack = [];
          redoStack = [];
          say("The screen is arranging itself again.");
        } catch {
          say("Couldn't change that — check the connection.");
        }
      },
    });
  }

  function undoAll(): void {
    ask({
      title: "Undo all your changes?",
      lines: ["The layout goes back to how it is on the screen now."],
      confirm: "Undo all",
      cancel: "Keep editing",
      danger: true,
      run: () => {
        commit(baseline, "All changes undone");
        selected = null;
      },
    });
  }

  // Copy to another screen.
  let copyOpen = $state(false);
  let copyTo = $state("");
  // Only screens that have shown up lately: every browser that ever opened
  // the dashboard is paired, so the full list is mostly long-gone tabs.
  const RECENT_MS = 30 * 24 * 3600 * 1000;
  const recent = $derived(
    devices.filter(
      (d) => !!d.last_seen && Date.now() - Date.parse(d.last_seen) < RECENT_MS,
    ),
  );
  const otherScreens = $derived(recent.filter((d) => d.id !== screenId));
  /** Name plus size, since most screens are just called "Screen". */
  function screenLabel(d: Device): string {
    return d.viewport_w && d.viewport_h
      ? `${d.name} · ${d.viewport_w}×${d.viewport_h}`
      : d.name;
  }
  async function doCopy(): Promise<void> {
    const target = devices.find((d) => d.id === copyTo);
    copyOpen = false;
    if (!target) return;
    const before = target.grid ?? null;
    try {
      await put(target.id, grid);
      say(`Copied to ${target.name}.`, {
        label: "Undo",
        run: () =>
          void put(target.id, before).then(
            () => say(`${target.name} is back how it was.`),
            () => say("Couldn't undo that — check the connection."),
          ),
      });
    } catch {
      say(`Couldn't copy to ${target.name} — check the connection.`);
    }
  }

  // Earlier layouts.
  let historyOpen = $state(false);
  let snapshots = $state<LayoutSnapshot[] | null>(null);
  async function openHistory(): Promise<void> {
    historyOpen = true;
    snapshots = null;
    snapshots = await client.gridHistory(screenId).catch(() => []);
  }
  async function useSnapshot(s: LayoutSnapshot): Promise<void> {
    historyOpen = false;
    if (!device) return;
    const next = s.grid ? asBricks(device, s.grid) : await automatic(device);
    commit(next, "Earlier layout loaded");
    selected = null;
    say("Loaded. Press Save to put it on the screen.");
  }
  function when(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function leave(e: MouseEvent): void {
    if (!edited) return;
    e.preventDefault();
    const href = (e.currentTarget as HTMLAnchorElement).href;
    ask({
      title: "Leave without saving?",
      lines: ["Your changes haven't been put on the screen yet."],
      confirm: "Leave",
      danger: true,
      run: () => {
        baseline = draft; // let beforeunload through
        location.href = href;
      },
    });
  }

  const menuHref = $derived(
    `/menu${screenId ? `?screen=${encodeURIComponent(screenId)}` : ""}`,
  );
</script>

<svelte:window
  bind:innerHeight={viewportH}
  onbeforeunload={(e) => {
    if (edited) e.preventDefault();
  }}
  onkeydown={(e) => {
    if (dialog || copyOpen || historyOpen) return;
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === "z") {
      e.preventDefault();
      if (e.shiftKey) redo();
      else undo();
    } else if (e.key === "Escape") {
      if (drag) drag = null;
      else selected = null;
    }
  }}
/>

<svelte:head>
  <title>Arrange the screen</title>
</svelte:head>

<div class="builder">
  <div class="page">
    <header>
      <a class="back" href={menuHref} onclick={leave}>
        <svg viewBox="0 0 24 24" aria-hidden="true"
          ><path d="M15 6l-6 6 6 6" /></svg
        >
        Settings
      </a>
      {#if phase === "ready" && device}
        <h1>Arrange <span>{device.name}</span></h1>
        <p class="hint">
          Tap a card to change its size or remove it. Drag one onto another to
          swap them.
        </p>
      {:else}
        <h1>Arrange a screen</h1>
      {/if}
    </header>

    {#if phase === "loading"}
      <p class="status">Loading…</p>
    {:else if phase === "error"}
      <p class="status">
        Couldn't reach the display server.
        <button type="button" class="link" onclick={() => location.reload()}
          >Try again</button
        >
      </p>
    {:else if phase === "pick"}
      <p class="status">Which screen do you want to arrange?</p>
      <ul class="pick">
        {#each recent as d (d.id)}
          <li>
            <button
              type="button"
              onclick={() => {
                screenId = d.id;
                void openScreen();
              }}>{screenLabel(d)}</button
            >
          </li>
        {:else}
          <li class="status">No screens are paired yet.</li>
        {/each}
      </ul>
    {:else}
      <div class="workspace">
        <!-- Keep the preview in view while the controls below scroll, as
             long as it's short enough to leave room for them. -->
        <div class="stagecol" class:pin={canvasH < viewportH * 0.45}>
          {#if warnings.length}
            <ul class="warnings" aria-label="Things to check">
              {#each warnings as w (w.text)}
                <li class:stop={w.level === "stop"}>
                  {#if w.card}
                    <button
                      type="button"
                      class="link"
                      onclick={() => (selected = w.card ?? null)}
                      >{w.text}</button
                    >
                  {:else}
                    {w.text}
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}

          <div class="frame">
            <div
              class="canvas"
              class:settled
              bind:this={canvasEl}
              bind:clientWidth={canvasW}
              style:height="{canvasH}px"
              style:--uw="{unitW}px"
              style:--uh="{unitH}px"
              style:--stud="{Math.min(unitW, unitH) * 0.13}px"
              role="presentation"
              onpointerdown={() => (selected = null)}
            >
              {#each grid.items as item (item.card)}
                {@const lifted = drag?.live && drag.card === item.card}
                {@const sel = selected === item.card}
                {@const size = sizeOf(draft, item.card) ?? "s"}
                <button
                  type="button"
                  class="tile"
                  class:sel
                  class:lifted
                  class:target={drag?.over === item.card}
                  class:snap={snapped.includes(item.card) && !drag}
                  class:photo={item.card === "photo" && !!photoThumb}
                  style:left="{item.x * unitW}px"
                  style:top="{item.y * unitH}px"
                  style:width="{item.w * unitW}px"
                  style:height="{item.h * unitH}px"
                  style:transform={lifted && drag
                    ? `translate(${drag.dx}px, ${drag.dy}px) scale(1.03)`
                    : undefined}
                  style:--tile={tint(item.card)}
                  style:--thumb={item.card === "photo" && photoThumb
                    ? `url("${photoThumb}")`
                    : undefined}
                  aria-pressed={sel}
                  aria-label="{name(item.card)}, {SIZE_NAME[
                    size
                  ]}. Enter for size and order, Delete to remove."
                  onpointerdown={(e) => onDown(e, item)}
                  onpointermove={onMove}
                  onpointerup={onUp}
                  onpointercancel={() => (drag = null)}
                  onkeydown={(e) => onTileKey(e, item)}
                >
                  <span class="tname">{name(item.card)}</span>
                  <span class="tsize">{SIZE_NAME[size]}</span>
                </button>
                {#if sel && !drag?.live}
                  <button
                    type="button"
                    class="drop"
                    style:left="{(item.x + item.w) * unitW}px"
                    style:top="{item.y * unitH}px"
                    aria-label="Remove {name(item.card)} from the screen"
                    onpointerdown={(e) => e.stopPropagation()}
                    onclick={() => remove(item.card)}
                    ><svg viewBox="0 0 24 24"
                      ><path d="M7 7l10 10M17 7L7 17" /></svg
                    ></button
                  >
                {/if}
              {/each}
              {#if grid.items.length === 0}
                <p class="empty">Add a card from the list below.</p>
              {/if}
            </div>
          </div>
        </div>

        <aside class="side">
          <section class="panel" aria-label="Selected card">
            {#if selected && selSize}
              {@const card = selected}
              <div class="selhead">
                <h2>{name(card)}</h2>
                <button
                  type="button"
                  class="x"
                  aria-label="Done with {name(card)}"
                  onclick={() => (selected = null)}>Done</button
                >
              </div>

              <div class="sizes" role="radiogroup" aria-label="Size">
                {#each SIZES as o (o.size)}
                  <button
                    type="button"
                    role="radio"
                    aria-checked={selSize === o.size}
                    disabled={o.size === "m" && draft.cells < 2}
                    onclick={() => resize(card, o.size)}
                  >
                    <span class="brick {o.size}" aria-hidden="true"></span>
                    {o.label}
                  </button>
                {/each}
              </div>
              {#if selSize === "l"}
                <p class="soft">
                  The one big spot — countdowns and weather alerts show up here
                  too.
                </p>
              {:else if !draft.hero}
                <p class="soft">
                  Nothing is Large right now. Countdowns and weather alerts
                  borrow the first card's spot.
                </p>
              {/if}

              {#if selSize === "l" && canSide}
                <div class="row2" role="radiogroup" aria-label="Side">
                  <span class="label">Sits on the</span>
                  <div class="seg">
                    {#each ["left", "right"] as const as side (side)}
                      <button
                        type="button"
                        role="radio"
                        aria-checked={draft.side === side}
                        onclick={() => setSide(side)}
                        >{side === "left" ? "Left" : "Right"}</button
                      >
                    {/each}
                  </div>
                </div>
              {:else if selSize !== "l"}
                <div class="row2">
                  <span class="label">Order</span>
                  <div class="seg">
                    <button
                      type="button"
                      disabled={selIndex <= 0}
                      onclick={() => reorder(card, -1)}
                      ><svg viewBox="0 0 24 24" aria-hidden="true"
                        ><path d="M15 6l-6 6 6 6" /></svg
                      >Earlier</button
                    >
                    <button
                      type="button"
                      disabled={selIndex >= draft.pieces.length - 1}
                      onclick={() => reorder(card, 1)}
                      >Later<svg viewBox="0 0 24 24" aria-hidden="true"
                        ><path d="M9 6l6 6-6 6" /></svg
                      ></button
                    >
                  </div>
                </div>
              {/if}
              {#if SOMETIMES_EMPTY[card]}
                <p class="soft">{SOMETIMES_EMPTY[card]}</p>
              {/if}
              <button type="button" class="remove" onclick={() => remove(card)}
                >Remove {name(card)} from the screen</button
              >
            {:else}
              <p class="soft nothing">
                Tap a card on the screen above to change its size or remove it.
              </p>
            {/if}
          </section>

          <section class="panel">
            <h2>Add a card</h2>
            {#if tray.length}
              <ul class="tray">
                {#each tray as c (c.id)}
                  <li>
                    <button
                      type="button"
                      style:--tile={tint(c.id)}
                      onclick={() => add(c.id)}
                      ><span aria-hidden="true">+</span> {c.name}</button
                    >
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="soft">Every card is already on the screen.</p>
            {/if}
          </section>

          <section class="panel more">
            <h2>More</h2>
            <button type="button" class="row" onclick={openHistory}>
              Earlier layouts
              <small>Bring back a layout you saved before</small>
            </button>
            {#if otherScreens.length}
              <button
                type="button"
                class="row"
                onclick={() => {
                  copyTo = "";
                  copyOpen = true;
                }}
              >
                Copy to another screen
                <small>Give another screen this same layout</small>
              </button>
            {/if}
            {#if saved}
              <button type="button" class="row" onclick={goAutomatic}>
                Let the screen arrange itself
                <small>Go back to the automatic layout</small>
              </button>
            {/if}
          </section>
        </aside>
      </div>

      <div class="bar">
        <div class="undo">
          <button
            type="button"
            aria-label="Undo"
            title="Undo"
            disabled={!undoStack.length}
            onclick={undo}
            ><svg viewBox="0 0 24 24"
              ><path d="M9 14L4 9l5-5" /><path
                d="M4 9h10a6 6 0 0 1 0 12h-3"
              /></svg
            ></button
          >
          <button
            type="button"
            aria-label="Redo"
            title="Redo"
            disabled={!redoStack.length}
            onclick={redo}
            ><svg viewBox="0 0 24 24"
              ><path d="M15 14l5-5-5-5" /><path
                d="M20 9H10a6 6 0 0 0 0 12h3"
              /></svg
            ></button
          >
        </div>
        <span class="state" class:dirty aria-live="polite"
          >{edited
            ? "Not saved yet"
            : dirty
              ? "Save to put this on the screen"
              : saved
                ? "Saved"
                : "Automatic layout"}</span
        >
        {#if edited}
          <button type="button" class="ghostbtn" onclick={undoAll}
            >Undo all</button
          >
        {/if}
        <button
          type="button"
          class="save"
          disabled={!dirty || saving}
          onclick={save}>{saving ? "Saving…" : "Save"}</button
        >
      </div>
    {/if}

    <div class="visually-hidden" role="status" aria-live="polite">{live}</div>

    {#if toast}
      <div class="toast" role="status">
        <span>{toast.text}</span>
        {#if toast.action}
          {@const action = toast.action}
          <button
            type="button"
            onclick={() => {
              toast = null;
              action.run();
            }}>{action.label}</button
          >
        {/if}
      </div>
    {/if}
  </div>

  {#if dialog}
    {@const d = dialog}
    <Dialog
      title={d.title}
      confirm={d.confirm}
      cancel={d.cancel}
      danger={d.danger}
      onCancel={() => (dialog = null)}
      onConfirm={() => {
        dialog = null;
        void d.run();
      }}
    >
      {#each d.lines as line (line)}<p>{line}</p>{/each}
    </Dialog>
  {/if}

  {#if copyOpen}
    <Dialog
      title="Copy to which screen?"
      confirm="Copy"
      disabled={!copyTo}
      onCancel={() => (copyOpen = false)}
      onConfirm={() => void doCopy()}
    >
      <p>That screen's layout gets replaced with this one.</p>
      <div class="choices">
        {#each otherScreens as d (d.id)}
          <label>
            <input
              type="radio"
              name="copy-to"
              value={d.id}
              bind:group={copyTo}
            />
            {screenLabel(d)}
          </label>
        {/each}
      </div>
    </Dialog>
  {/if}

  {#if historyOpen}
    <Dialog
      title="Earlier layouts"
      confirm="Close"
      onCancel={() => (historyOpen = false)}
      onConfirm={() => (historyOpen = false)}
    >
      {#if snapshots === null}
        <p>Loading…</p>
      {:else if snapshots.length === 0}
        <p>
          Nothing yet — every time you save, the layout it replaces lands here.
        </p>
      {:else}
        <p>
          Pick one to load it. Nothing changes on the screen until you save.
        </p>
        <ul class="history">
          {#each snapshots as s (s.id)}
            <li>
              <button type="button" onclick={() => void useSnapshot(s)}>
                <GridThumb grid={s.grid ?? null} {tint} />
                <span>
                  {s.grid ? "Your layout" : "Automatic layout"}
                  <small>Replaced {when(s.saved_at)}</small>
                </span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </Dialog>
  {/if}
</div>

<style>
  /* The dashboard pins body to the viewport (overflow hidden); this page
     scrolls like a normal one. Extra specificity to win over base.css. */
  :global(html body),
  :global(html:has(.builder)) {
    height: auto;
    overflow: visible;
  }
  :global(#app) {
    height: auto;
    min-height: 100dvh;
  }
  .builder {
    --ink: #f4efe5;
    --ink-rgb: 244, 239, 229;
    --accent: #e7a34a;
    --soft: rgba(var(--ink-rgb), 0.62);
    --faint: rgba(var(--ink-rgb), 0.38);
    --wash: rgba(var(--ink-rgb), 0.07);
    --rule: rgba(var(--ink-rgb), 0.13);
    --display: "Fraunces", "Iowan Old Style", Georgia, serif;
    color-scheme: dark;
    min-height: 100dvh;
  }
  .page {
    background: #000;
    color: var(--ink);
    font:
      1rem/1.45 -apple-system,
      BlinkMacSystemFont,
      "Segoe UI",
      Roboto,
      Helvetica,
      Arial,
      sans-serif;
    -webkit-tap-highlight-color: transparent;
    max-width: 72rem;
    margin: 0 auto;
    padding: max(16px, env(safe-area-inset-top))
      max(16px, env(safe-area-inset-right))
      calc(96px + env(safe-area-inset-bottom))
      max(16px, env(safe-area-inset-left));
  }
  :global(:root:has(.builder)) {
    background: #000;
  }
  button {
    font: inherit;
    color: inherit;
    cursor: pointer;
  }
  button:disabled {
    cursor: default;
  }
  svg {
    width: 22px;
    height: 22px;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  header {
    margin-bottom: 14px;
  }
  .back {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: 44px;
    margin-left: -6px;
    color: var(--soft);
    text-decoration: none;
  }
  h1 {
    margin: 2px 0 2px;
    font: 500 clamp(1.6rem, 6vw, 2.2rem) / 1.1 var(--display);
  }
  h1 span {
    color: var(--accent);
  }
  .hint,
  .soft {
    margin: 0;
    color: var(--soft);
  }
  .status {
    color: var(--soft);
  }
  .link {
    background: none;
    border: none;
    padding: 0;
    text-align: left;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .pick {
    list-style: none;
    padding: 0;
    display: grid;
    gap: 8px;
  }
  .pick button {
    width: 100%;
    min-height: 52px;
    border: none;
    border-radius: 14px;
    background: var(--wash);
    text-align: left;
    padding: 0 16px;
    font-size: 1.1rem;
  }

  .workspace {
    display: grid;
    gap: 16px;
  }
  @media (min-width: 900px) {
    .workspace {
      grid-template-columns: minmax(0, 1fr) 20rem;
      align-items: start;
    }
  }

  .stagecol.pin {
    position: sticky;
    top: 0;
    z-index: 5;
    margin: 0 -4px;
    padding: max(8px, env(safe-area-inset-top)) 4px 8px;
    background: #000;
  }
  .warnings {
    list-style: none;
    margin: 0 0 10px;
    padding: 0;
    display: grid;
    gap: 6px;
  }
  .warnings li {
    padding: 8px 12px;
    border-radius: 12px;
    background: rgba(231, 163, 74, 0.1);
    color: #f1c98d;
    font-size: 0.92rem;
  }
  .warnings li.stop {
    background: rgba(226, 89, 74, 0.14);
    color: #f6a99f;
  }

  .frame {
    padding: 7px;
    border-radius: 18px;
    background: #050505;
    box-shadow:
      0 0 0 1px var(--rule),
      0 18px 40px -22px rgba(0, 0, 0, 0.55);
  }
  .canvas {
    position: relative;
    border-radius: 11px;
    /* A baseplate: one stud per grid unit, showing wherever a spot is free. */
    background-color: #0d0c0a;
    background-image: radial-gradient(
      circle,
      rgba(var(--ink-rgb), 0.11) 0 var(--stud),
      transparent calc(var(--stud) + 1px)
    );
    background-size: var(--uw) var(--uh);
    transition: height 160ms ease;
    overflow: hidden;
    touch-action: pan-y;
  }
  .tile {
    position: absolute;
    padding: 0;
    border: 3px solid #0d0c0a;
    border-radius: 12px;
    background: var(--tile);
    /* A brick's lit top edge. */
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
    color: #fff;
    overflow: hidden;
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
  }
  .canvas.settled .tile {
    transition:
      left 200ms cubic-bezier(0.3, 1.3, 0.5, 1),
      top 200ms cubic-bezier(0.3, 1.3, 0.5, 1),
      width 200ms cubic-bezier(0.3, 1.3, 0.5, 1),
      height 200ms cubic-bezier(0.3, 1.3, 0.5, 1),
      box-shadow 160ms ease;
  }
  .tile.photo {
    background:
      var(--thumb) center / cover,
      var(--tile);
  }
  .tile.photo .tname,
  .tile.photo .tsize {
    right: auto;
    max-width: calc(100% - 28px);
    background: rgba(0, 0, 0, 0.45);
    border-radius: 6px;
    padding: 1px 6px;
  }
  .tile:focus-visible {
    outline: 3px solid var(--ink);
    outline-offset: -6px;
  }
  .tile.sel {
    box-shadow:
      inset 0 0 0 3px var(--accent),
      0 0 0 1px var(--accent);
    z-index: 2;
  }
  .tile.lifted {
    z-index: 4;
    transition: none;
    box-shadow:
      inset 0 0 0 3px var(--accent),
      0 20px 36px -10px #000;
    opacity: 0.94;
    cursor: grabbing;
  }
  .tile.target {
    box-shadow:
      inset 0 0 0 3px var(--ink),
      inset 0 0 0 999px rgba(0, 0, 0, 0.35);
  }
  /* The click of a brick going down. */
  .canvas.settled .tile.snap {
    animation: snap 260ms ease-out;
  }
  @keyframes snap {
    40% {
      scale: 0.95;
    }
    100% {
      scale: 1;
    }
  }
  .tname,
  .tsize {
    position: absolute;
    left: 8px;
    right: 8px;
    text-align: left;
    line-height: 1.15;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .tname {
    top: 6px;
    font-size: clamp(11px, 1.6vw, 15px);
    font-weight: 600;
  }
  .tsize {
    bottom: 5px;
    right: auto;
    font-size: clamp(10px, 1.3vw, 12px);
    opacity: 0.75;
  }
  /* Remove badge, hanging off the selected card's top-right corner. */
  .drop {
    position: absolute;
    z-index: 3;
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    margin: -6px 0 0 -38px;
    padding: 0;
    border: none;
    background: none;
  }
  .drop::before {
    content: "";
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    background: #f4efe5;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  }
  .drop svg {
    position: relative;
    width: 16px;
    height: 16px;
    stroke: #17150f;
    stroke-width: 2.6;
  }
  .empty {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    margin: 0;
    color: var(--soft);
  }

  .side {
    display: grid;
    gap: 12px;
  }
  .panel {
    padding: 14px;
    border-radius: 18px;
    background: var(--wash);
  }
  .panel h2 {
    margin: 0 0 10px;
    font: 500 1.15rem/1.2 var(--display);
  }
  .selhead {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .selhead h2 {
    margin: 0;
  }
  .x {
    min-height: 40px;
    padding: 0 14px;
    border: none;
    border-radius: 999px;
    background: var(--wash);
  }
  .nothing {
    padding: 6px 0;
  }
  .label {
    font-size: 0.9rem;
    color: var(--soft);
  }
  .sizes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    margin: 12px 0 8px;
  }
  .sizes button {
    display: grid;
    justify-items: center;
    align-content: center;
    grid-template-rows: 26px auto;
    gap: 6px;
    min-height: 72px;
    border: none;
    border-radius: 14px;
    background: rgba(var(--ink-rgb), 0.08);
  }
  .sizes button[aria-checked="true"] {
    background: var(--accent);
    color: #1a1206;
    font-weight: 600;
  }
  .sizes button:disabled {
    opacity: 0.3;
  }
  /* Little brick glyphs: one cell, two wide, two by two. */
  .brick {
    --b: 11px;
    /* Glyphs sit on a common baseline so the labels line up. */
    align-self: end;
    height: var(--b);
    width: var(--b);
    border-radius: 3px;
    background: currentColor;
    opacity: 0.85;
  }
  .brick.m {
    width: calc(var(--b) * 2 + 2px);
  }
  .brick.l {
    width: calc(var(--b) * 2 + 2px);
    height: calc(var(--b) * 2 + 2px);
  }
  .sizes button:not([aria-checked="true"]) .brick {
    opacity: 0.5;
  }
  .row2 {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin: 12px 0;
  }
  .seg {
    display: flex;
    gap: 4px;
    padding: 3px;
    border-radius: 999px;
    background: rgba(var(--ink-rgb), 0.08);
  }
  .seg button {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: 40px;
    padding: 0 14px;
    border: none;
    border-radius: 999px;
    background: none;
  }
  .seg button svg {
    width: 18px;
    height: 18px;
  }
  .seg button[aria-checked="true"] {
    background: var(--ink);
    color: #17150f;
    font-weight: 600;
  }
  .seg button:disabled {
    opacity: 0.3;
  }
  .panel .soft + .soft {
    margin-top: 6px;
  }
  .remove {
    width: 100%;
    min-height: 48px;
    margin-top: 14px;
    border: 1px solid rgba(226, 89, 74, 0.5);
    border-radius: 12px;
    background: none;
    color: #f6a99f;
  }
  .tray {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .tray button {
    min-height: 44px;
    padding: 0 14px 0 10px;
    border: none;
    border-radius: 999px;
    background: color-mix(in srgb, var(--tile) 55%, transparent);
  }
  .tray span {
    font-weight: 700;
    margin-right: 2px;
  }
  .more .row {
    display: grid;
    width: 100%;
    gap: 1px;
    padding: 10px 0;
    border: none;
    border-top: 1px solid var(--rule);
    background: none;
    text-align: left;
  }
  .more .row:first-of-type {
    border-top: none;
  }
  .more small,
  .history small {
    display: block;
    color: var(--soft);
  }

  .bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px max(16px, env(safe-area-inset-right))
      max(10px, env(safe-area-inset-bottom))
      max(16px, env(safe-area-inset-left));
    background: rgba(10, 9, 7, 0.92);
    backdrop-filter: blur(12px);
    border-top: 1px solid var(--rule);
  }
  .undo {
    display: flex;
    gap: 4px;
  }
  .undo button {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border: none;
    border-radius: 12px;
    background: var(--wash);
  }
  .undo button:disabled {
    opacity: 0.3;
  }
  .state {
    flex: 1;
    min-width: 0;
    font-size: 0.9rem;
    color: var(--soft);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .ghostbtn,
  .save {
    min-height: 44px;
    padding: 0 18px;
    border: none;
    border-radius: 999px;
    font-weight: 600;
  }
  .ghostbtn {
    background: var(--wash);
  }
  .save {
    padding: 0 26px;
    background: var(--accent);
    color: #1a1206;
  }
  .save:disabled {
    opacity: 0.35;
  }

  .toast {
    position: fixed;
    left: 50%;
    bottom: calc(76px + env(safe-area-inset-bottom));
    z-index: 30;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 14px;
    width: max-content;
    max-width: calc(100% - 32px);
    padding: 10px 10px 10px 16px;
    border-radius: 14px;
    background: #f4efe5;
    color: #17150f;
    box-shadow: 0 12px 30px -10px #000;
  }
  .toast button {
    min-height: 36px;
    padding: 0 14px;
    border: none;
    border-radius: 999px;
    background: #17150f;
    color: #f4efe5;
    font-weight: 600;
  }

  .choices {
    display: grid;
    gap: 4px;
  }
  .choices label {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    color: var(--ink);
  }
  .choices input {
    width: 20px;
    height: 20px;
    accent-color: var(--accent);
  }
  .history {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 6px;
  }
  .history button {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 8px;
    border: none;
    border-radius: 12px;
    background: var(--wash);
    text-align: left;
    color: var(--ink);
  }

  @media (max-width: 420px) {
    .state.dirty {
      display: none;
    }
    .bar .ghostbtn {
      margin-left: auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .canvas.settled .tile,
    .canvas {
      transition: none;
    }
    .canvas.settled .tile.snap {
      animation: none;
    }
  }
</style>
