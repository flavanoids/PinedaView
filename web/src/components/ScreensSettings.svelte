<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Device } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import Switch from "./settings/Switch.svelte";

  const settings = useSettings();
  const client = settings.client;
  const origin = location.origin;

  let newProfile = $state("");
  let copying = $state<Record<string, string>>({});
  let removing = $state<string | null>(null);
  let clearingStale = $state(false);

  async function removeStale(stale: Device[]): Promise<void> {
    let removed = 0;
    for (const device of stale) {
      try {
        await client.unpairDevice(device.id);
        removed += 1;
      } catch {
        /* reported below */
      }
    }
    clearingStale = false;
    await settings.load();
    settings.flash(
      removed === stale.length
        ? `Removed ${removed} old screens`
        : `Removed ${removed} of ${stale.length}. Try again for the rest.`,
      removed !== stale.length,
    );
  }

  async function update(
    device: Device,
    patch: Parameters<typeof client.updateDevice>[1],
  ): Promise<void> {
    const updated = await settings.save(() =>
      client.updateDevice(device.id, patch),
    );
    if (updated)
      settings.devices = settings.devices.map((d) =>
        d.id === device.id ? updated : d,
      );
  }

  async function copyFrom(device: Device): Promise<void> {
    const source = copying[device.id];
    if (!source) return;
    const from = settings.devices.find((d) => d.id === source)?.name ?? "";
    const updated = await settings.save(
      () => client.copyScreen(device.id, source),
      `Copied ${from}'s settings`,
    );
    if (updated) {
      copying[device.id] = "";
      await settings.load();
    }
  }

  async function remove(device: Device): Promise<void> {
    if (
      await settings.attempt(
        () => client.unpairDevice(device.id),
        `${device.name} removed`,
      )
    ) {
      removing = null;
      await settings.load();
    }
  }

  async function addProfile(): Promise<void> {
    const name = newProfile.trim();
    if (!name) return;
    const made = await settings.save(
      () => client.createProfile(name, settings.profile?.id),
      `Profile “${name}” added`,
    );
    if (made) {
      newProfile = "";
      await settings.load();
    }
  }

  function lastSeen(iso: string | null | undefined): string {
    if (!iso) return "Never connected";
    const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 2) return "Online now";
    if (mins < 60) return `Last seen ${mins} min ago`;
    const hours = Math.round(mins / 60);
    if (hours < 48) return `Last seen ${hours} h ago`;
    return `Last seen ${Math.round(hours / 24)} days ago`;
  }
</script>

<Group
  title="Screens"
  description="Every browser showing this dashboard. Add one by opening {origin} on it."
>
  {#each settings.activeScreens as device (device.id)}
    {@const here = device.id === settings.hereId}
    <article class="device" class:here>
      <header>
        <input
          class="name"
          aria-label="Screen name"
          value={device.name}
          onchange={(e) => {
            const name = e.currentTarget.value.trim();
            if (name) void update(device, { name });
          }}
        />
        {#if here}<span class="tag">This screen</span>{/if}
      </header>
      <p class="meta">
        {lastSeen(device.last_seen)}
        {#if device.viewport_w && device.viewport_h}
          · {device.viewport_w}×{device.viewport_h}
        {/if}
        {#if device.pair_code}· Code {device.pair_code}{/if}
      </p>

      <Field label="Profile" hint="Shares its look, cards and photo settings.">
        {#snippet children(id)}
          <select
            {id}
            value={device.profile_id}
            onchange={(e) =>
              update(device, { profile_id: e.currentTarget.value })}
          >
            {#each settings.profiles as profile (profile.id)}
              <option value={profile.id}>{profile.name}</option>
            {/each}
          </select>
        {/snippet}
      </Field>
      <Field
        label="Settings button"
        hint="Show the ⚙ button on that screen so it can be changed by touch."
      >
        {#snippet children(id)}
          <Switch
            {id}
            checked={!device.locked}
            onchange={(on) => update(device, { locked: !on })}
          />
        {/snippet}
      </Field>
      {#if settings.activeScreens.length > 1}
        <Field label="Mirror" hint="Show exactly what another screen shows.">
          {#snippet children(id)}
            <select
              {id}
              value={device.follow ?? ""}
              onchange={(e) =>
                update(device, { follow: e.currentTarget.value })}
            >
              <option value="">Off</option>
              {#each settings.activeScreens.filter((d) => d.id !== device.id) as other (other.id)}
                <option value={other.id}>{other.name}</option>
              {/each}
            </select>
          {/snippet}
        </Field>
        <Field
          label="Copy settings from"
          hint="Its cards, layout, brightness and night schedule. The name stays."
        >
          {#snippet children(id)}
            <select {id} bind:value={copying[device.id]}>
              <option value="">Choose a screen</option>
              {#each settings.activeScreens.filter((d) => d.id !== device.id) as other (other.id)}
                <option value={other.id}>{other.name}</option>
              {/each}
            </select>
            <button
              type="button"
              class="btn small"
              disabled={!copying[device.id]}
              onclick={() => copyFrom(device)}>Copy</button
            >
          {/snippet}
        </Field>
      {/if}

      <div class="actions">
        <button
          type="button"
          class="btn small"
          onclick={() =>
            settings.attempt(
              () => client.identifyDevice(device.id),
              `${device.name} is flashing`,
            )}>Identify</button
        >
        {#if !here}
          {#if removing === device.id}
            <span class="confirm">Remove {device.name}?</span>
            <button
              type="button"
              class="btn small"
              onclick={() => (removing = null)}>Keep</button
            >
            <button
              type="button"
              class="btn small danger"
              onclick={() => remove(device)}>Remove</button
            >
          {:else}
            <button
              type="button"
              class="btn small danger"
              onclick={() => (removing = device.id)}>Remove…</button
            >
          {/if}
        {/if}
      </div>
    </article>
  {/each}
</Group>

{#if settings.staleScreens.length}
  {@const stale = settings.staleScreens}
  <Group title="Not seen recently">
    <Field
      label={stale.length === 1
        ? "1 screen hasn't connected in 30 days"
        : `${stale.length} screens haven't connected in 30 days`}
      hint="Usually a browser that opened the dashboard once. Removing them is safe: a screen that comes back is simply paired again."
    >
      {#snippet children()}
        {#if clearingStale}
          <button
            type="button"
            class="btn small"
            onclick={() => (clearingStale = false)}>Keep</button
          >
          <button
            type="button"
            class="btn small danger"
            onclick={() => removeStale(stale)}>Remove {stale.length}</button
          >
        {:else}
          <button
            type="button"
            class="btn small"
            onclick={() => (clearingStale = true)}>Remove all…</button
          >
        {/if}
      {/snippet}
    </Field>
  </Group>
{/if}

<Group
  title="Profiles"
  description="A profile is a shared setup: theme, cards and photo settings. Screens on the same profile change together."
>
  <ul class="profiles">
    {#each settings.profiles as profile (profile.id)}
      {@const count = settings.devices.filter(
        (d) => d.profile_id === profile.id,
      ).length}
      <li>
        <span>{profile.name}</span>
        <span class="hint">{count === 1 ? "1 screen" : `${count} screens`}</span
        >
      </li>
    {/each}
  </ul>
  <form
    class="add"
    onsubmit={(e) => {
      e.preventDefault();
      void addProfile();
    }}
  >
    <input
      aria-label="New profile name"
      placeholder="New profile name"
      bind:value={newProfile}
    />
    <button type="submit" class="btn" disabled={!newProfile.trim()}
      >Add profile</button
    >
  </form>
  <p class="hint">
    A new profile starts as a copy of “{settings.profile?.name ?? "this"}”.
  </p>
</Group>

<style>
  .device {
    display: flex;
    flex-direction: column;
    margin: 10px 0;
    padding: 12px 14px;
    border-radius: 14px;
    background: color-mix(in srgb, var(--on-stage) 5%, transparent);
  }
  .device.here {
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .device > :global(.field + .field) {
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 9%, transparent);
  }
  header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .name {
    flex: 1;
    min-width: 0;
    padding: 2px 0;
    border: none;
    border-bottom: 1px solid transparent;
    background: none;
    color: var(--on-stage);
    font: inherit;
    font-size: var(--type-md);
    font-weight: 600;
  }
  .name:hover,
  .name:focus {
    border-bottom-color: color-mix(in srgb, var(--on-stage) 25%, transparent);
  }
  .tag {
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-size: var(--type-caption);
    font-weight: 600;
    background: color-mix(in srgb, var(--accent) 18%, transparent);
  }
  .meta {
    margin-bottom: 4px;
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  .actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 10px;
  }
  .confirm {
    font-size: var(--type-caption);
    margin-left: auto;
  }
  .profiles {
    list-style: none;
  }
  .profiles li {
    display: flex;
    justify-content: space-between;
    padding: 10px 0;
    font-size: var(--type-sm);
  }
  .add {
    display: flex;
    gap: var(--space-2);
    padding: 12px 0 6px;
  }
  .add input {
    flex: 1;
  }
</style>
