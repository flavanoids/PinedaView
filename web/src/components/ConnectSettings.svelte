<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  Settings → Connect: every outside service the display talks to. What's
  already set up (by hand, in config.toml) shows as connected; anything else
  opens into the form that hooks it up. One row open at a time.
-->
<script lang="ts">
  import {
    ProtocolError,
    type CalendarChoice,
    type ConnectionStatus,
  } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import Group from "./settings/Group.svelte";
  import Scope from "./settings/Scope.svelte";

  const settings = useSettings();
  const client = settings.client;

  const GROUPS = [
    ["calendars", "Calendars"],
    ["home", "Home"],
    ["music", "Music"],
    ["maps", "Maps"],
  ] as const;

  const CALENDAR_TYPE = {
    "apple-calendar": "apple",
    "google-calendar": "google",
    "calendar-links": "ics",
  } as const;
  type CalendarBackend = keyof typeof CALENDAR_TYPE;
  const isCalendar = (id: string): id is CalendarBackend => id in CALENDAR_TYPE;

  let rows = $state<ConnectionStatus[]>([]);
  let loaded = $state(false);
  let openId = $state<string | null>(null);
  let busy = $state(false);
  let error = $state("");
  let form = $state<Record<string, string>>({});
  let choices = $state<CalendarChoice[] | null>(null);

  const open = $derived(rows.find((r) => r.id === openId));

  async function refresh(): Promise<void> {
    rows = await client.listConnections();
    loaded = true;
  }
  $effect(() => {
    void refresh().catch(() => (loaded = true));
  });

  async function loadChoices(id: CalendarBackend): Promise<void> {
    choices = null;
    try {
      choices = await client.calendarChoices(id);
    } catch (e) {
      error = reason(e);
    }
  }

  function toggle(row: ConnectionStatus): void {
    error = "";
    choices = null;
    if (openId === row.id) {
      openId = null;
      return;
    }
    openId = row.id;
    form = Object.fromEntries(
      Object.entries(row.values ?? {}).map(([k, v]) => [
        k,
        v == null ? "" : String(v),
      ]),
    );
    if (isCalendar(row.id) && row.connected) void loadChoices(row.id);
  }

  function reason(e: unknown): string {
    return e instanceof ProtocolError && e.detail
      ? e.detail
      : "Couldn't reach the server. Try again.";
  }

  /** Run a connect/disconnect, show its outcome, and refresh the rows. */
  async function run(
    work: () => Promise<unknown>,
    done: string,
  ): Promise<boolean> {
    busy = true;
    error = "";
    try {
      await work();
      settings.flash(done);
      await refresh();
      return true;
    } catch (e) {
      error = reason(e);
      return false;
    } finally {
      busy = false;
    }
  }

  const v = (key: string) => (form[key] ?? "").trim();

  async function submit(id: string): Promise<void> {
    switch (id) {
      case "apple-calendar":
        await run(async () => {
          choices = await client.connectAppleCalendar({
            apple_id: v("apple_id"),
            password: v("password"),
          });
        }, "Connected");
        return;
      case "calendar-links":
        if (
          await run(
            () =>
              client.addCalendarLink({
                url: v("url"),
                label: v("label") || null,
              }),
            "Calendar added",
          )
        ) {
          form = {};
          await loadChoices("calendar-links");
        }
        return;
      case "home-assistant":
        if (
          await run(
            () => client.connect(id, { url: v("url"), token: v("token") }),
            "Connected",
          )
        )
          form = { ...form, token: "" };
        return;
      case "antigua":
        await run(
          () =>
            client.connect(id, {
              url: v("url"),
              fallback_url: v("fallback_url") || null,
            }),
          "Connected",
        );
        return;
      case "cameras":
        await run(() => client.connect(id, { go2rtc: v("go2rtc") }), "Saved");
        return;
      case "airplay":
        await run(
          () =>
            client.connect(id, {
              host: v("host"),
              port: Number(v("port")) || 1883,
            }),
          "Connected",
        );
        return;
      case "google-maps":
        if (
          await run(
            () => client.setSecret("google_maps", v("key")),
            "Key saved",
          )
        )
          form = {};
        return;
    }
  }

  async function disconnect(id: string): Promise<void> {
    const work = {
      "apple-calendar": () => client.disconnectAppleCalendar(),
      "google-calendar": () => client.disconnectGoogleCalendar(),
      "home-assistant": () => client.disconnect("home-assistant"),
      antigua: () => client.disconnect("antigua"),
      airplay: () => client.disconnect("airplay"),
      "google-maps": () => client.deleteSecret("google_maps"),
    }[id];
    if (work && (await run(work, "Disconnected"))) choices = null;
  }

  async function saveChoices(id: CalendarBackend): Promise<void> {
    if (!choices) return;
    const type = CALENDAR_TYPE[id];
    await run(
      () =>
        client.setCalendarSources(
          (choices ?? []).map((c) => ({
            calendarId: c.id,
            label: c.name,
            color: c.color ?? null,
            selected: c.selected ?? false,
            type,
          })),
        ),
      "Saved",
    );
  }

  async function removeLink(linkId: string): Promise<void> {
    if (await run(() => client.removeCalendarLink(linkId), "Removed"))
      await loadChoices("calendar-links");
  }

  function status(row: ConnectionStatus): string {
    if (row.problem) return row.problem;
    if (row.detail) return row.detail;
    if (row.connected) return "Connected";
    return row.available ? "Not connected" : "Needs a one-time server setup";
  }

  const canDisconnect = (row: ConnectionStatus) =>
    row.connected && row.id !== "cameras" && row.id !== "calendar-links";
</script>

{#snippet input(key: string, label: string, type = "text", placeholder = "")}
  <label class="input">
    <span>{label}</span>
    <input
      {type}
      {placeholder}
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      bind:value={form[key]}
    />
  </label>
{/snippet}

{#snippet calendarList(id: CalendarBackend)}
  {#if choices === null}
    <p class="hint">Loading calendars…</p>
  {:else if choices.length === 0}
    <p class="hint">
      {id === "calendar-links"
        ? "No links yet."
        : "This account has no calendars."}
    </p>
  {:else}
    <ul class="calendars">
      {#each choices as choice (choice.id)}
        <li>
          <label>
            <input type="checkbox" bind:checked={choice.selected} />
            <span class="swatch" style:background={choice.color ?? undefined}
            ></span>
            <span class="cal-name">{choice.name}</span>
          </label>
          {#if id === "calendar-links"}
            <button
              type="button"
              class="btn small danger"
              disabled={busy}
              onclick={() => removeLink(choice.id)}>Remove</button
            >
          {/if}
        </li>
      {/each}
    </ul>
    <div class="actions">
      <button
        type="button"
        class="btn primary"
        disabled={busy}
        onclick={() => saveChoices(id)}>Show these</button
      >
    </div>
  {/if}
{/snippet}

{#snippet panel(row: ConnectionStatus)}
  <div class="panel" id="connect-{row.id}">
    {#if row.id === "apple-calendar"}
      {#if row.connected || choices}
        {@render calendarList("apple-calendar")}
      {:else}
        <p class="hint">
          Sign in with your Apple ID and an app-specific password — make one at
          <a href="https://account.apple.com" target="_blank" rel="noreferrer"
            >account.apple.com</a
          > under Sign-In and Security. Calendars other people share with you are
          included.
        </p>
        {@render input("apple_id", "Apple ID", "email", "you@icloud.com")}
        {@render input(
          "password",
          "App-specific password",
          "password",
          "abcd-efgh-ijkl-mnop",
        )}
      {/if}
    {:else if row.id === "google-calendar"}
      {#if row.connected}
        {@render calendarList("google-calendar")}
      {:else if row.available}
        <p class="hint">
          Google opens in a new tab. Come back here when it says Connected.
        </p>
        <div class="actions">
          <a
            class="btn primary"
            href="/connect-calendar"
            target="_blank"
            rel="noreferrer">Sign in with Google</a
          >
          <button type="button" class="btn" onclick={() => refresh()}
            >I'm back</button
          >
        </div>
      {:else}
        <p class="hint">
          Google only connects to a server it knows: this one needs a Google
          Cloud app and an HTTPS return address first. The install guide's
          Calendar section walks through it, once per server.
        </p>
      {/if}
    {:else if row.id === "calendar-links"}
      {#if row.connected}
        {@render calendarList("calendar-links")}
      {/if}
      <p class="hint">
        For calendars without a sign-in, like Proton: in Proton Calendar, open
        the calendar's settings, choose Share, and create a link with full view.
        Any calendar that gives you a link (often ending in .ics) works the same
        way.
      </p>
      {@render input("url", "Calendar link", "url", "https://…")}
      {@render input(
        "label",
        "Name (optional)",
        "text",
        "Taken from the calendar",
      )}
    {:else if row.id === "home-assistant"}
      <p class="hint">
        Your Home Assistant's address and a long-lived access token, from your
        profile page under Security. Nothing on the display uses it yet.
      </p>
      {@render input(
        "url",
        "Address",
        "url",
        "http://homeassistant.local:8123",
      )}
      {@render input(
        "token",
        "Access token",
        "password",
        row.connected ? "Saved — paste a new one to replace it" : "",
      )}
    {:else if row.id === "antigua"}
      <p class="hint">
        The voice assistant that keeps the household's alarms and reminders.
      </p>
      {@render input("url", "Address", "url", "http://127.0.0.1:9393")}
      {@render input("fallback_url", "Fallback address (optional)", "url")}
    {:else if row.id === "cameras"}
      <p class="hint">
        go2rtc relays the cameras' live video. Which cameras there are is still
        set in the server's config file.
      </p>
      {@render input(
        "go2rtc",
        "go2rtc address",
        "url",
        "http://127.0.0.1:1984",
      )}
    {:else if row.id === "airplay"}
      <p class="hint">
        The MQTT broker that shairport-sync reports the playing song to, with
        its cover.
      </p>
      {@render input("host", "Broker address", "text", "192.0.2.20")}
      {@render input("port", "Port", "number", "1883")}
    {:else if row.id === "google-maps"}
      <p class="hint">An API key for live drive times on the commute card.</p>
      {@render input(
        "key",
        "API key",
        "password",
        row.connected ? "Saved — paste a new key to replace it" : "",
      )}
    {/if}

    {#if error}<p class="error" role="alert">{error}</p>{/if}

    <div class="actions">
      {#if canDisconnect(row)}
        <button
          type="button"
          class="btn danger"
          disabled={busy}
          onclick={() => disconnect(row.id)}
          >{row.id === "google-maps" ? "Remove key" : "Disconnect"}</button
        >
      {/if}
      {#if !(row.id === "google-calendar" || (row.id === "apple-calendar" && (row.connected || choices)))}
        <button
          type="button"
          class="btn primary"
          disabled={busy}
          onclick={() => submit(row.id)}
          >{busy
            ? "Checking…"
            : row.id === "calendar-links"
              ? "Add calendar"
              : row.connected
                ? "Save"
                : "Connect"}</button
        >
      {/if}
    </div>
  </div>
{/snippet}

<Scope kind="home" />

{#if !loaded}
  <p class="hint">Checking connections…</p>
{:else}
  {#each GROUPS as [group, title] (group)}
    <Group {title}>
      {#each rows.filter((r) => r.group === group) as row (row.id)}
        <div class="service" class:open={openId === row.id}>
          <button
            type="button"
            class="head"
            aria-expanded={openId === row.id}
            aria-controls="connect-{row.id}"
            onclick={() => toggle(row)}
          >
            <span
              class="state"
              class:on={row.connected && !row.problem}
              class:warn={!!row.problem}
              aria-hidden="true"
            ></span>
            <span class="text">
              <span class="name">{row.name}</span>
              <span class="status" class:problem={!!row.problem}
                >{status(row)}</span
              >
            </span>
          </button>
          {#if openId === row.id && open}{@render panel(open)}{/if}
        </div>
      {/each}
    </Group>
  {/each}
  <p class="hint built-in">
    Weather, air quality, weather alerts, news and traffic cameras work without
    connecting anything.
  </p>
{/if}

<style>
  .service + .service {
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 10%, transparent);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 12px 0;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .state {
    flex: none;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1.5px solid color-mix(in srgb, var(--on-stage) 35%, transparent);
  }
  .state.on {
    border-color: #30a46c;
    background: #30a46c;
  }
  .state.warn {
    border-color: #f5a524;
    background: #f5a524;
  }
  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .name {
    font-size: var(--type-sm);
    font-weight: 600;
  }
  .status {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .status.problem {
    color: #f5a524;
    white-space: normal;
  }

  .panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 0 0 16px 22px;
  }
  .panel .hint {
    margin: 0;
  }
  .input {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  .input input {
    width: 100%;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: var(--space-2);
  }
  .error {
    margin: 0;
    font-size: var(--type-caption);
    color: #e5484d;
  }

  .calendars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .calendars li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .calendars label {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 2.5rem;
    min-width: 0;
    font-size: var(--type-sm);
    cursor: pointer;
  }
  .calendars input {
    accent-color: var(--accent);
    width: 1.1rem;
    height: 1.1rem;
  }
  .swatch {
    flex: none;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
    background: var(--accent);
  }
  .cal-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .built-in {
    margin: var(--space-3) 0 0;
  }
</style>
