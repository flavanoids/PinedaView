<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Backup } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import Scope from "./settings/Scope.svelte";

  interface Props {
    onRunSetup: () => void;
  }
  let { onRunSetup }: Props = $props();

  const settings = useSettings();
  const client = settings.client;

  let secretNames = $state<string[]>([]);
  let restoring = $state<Backup | null>(null);
  let restoreName = $state("");
  let busy = $state(false);

  async function refreshKeys(): Promise<void> {
    secretNames = (await client.listSecrets()).names;
  }
  $effect(() => {
    void refreshKeys().catch(() => {});
  });

  async function exportSettings(): Promise<void> {
    const backup = await settings.save(() => client.exportSettings(), "");
    if (!backup) return;
    const blob = new Blob([JSON.stringify(backup, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `pineda-settings-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    settings.flash("Backup downloaded");
  }

  async function chooseBackup(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as Backup;
      if (parsed?.format !== "pineda-settings") throw new Error("not a backup");
      restoring = parsed;
      restoreName = file.name;
    } catch {
      settings.flash("That file isn't a PinedaDisplay settings backup.", true);
    }
  }

  async function restore(): Promise<void> {
    if (!restoring) return;
    busy = true;
    const summary = await settings.save(
      () => client.restoreSettings(restoring as Backup),
      "",
    );
    busy = false;
    restoring = null;
    if (!summary) return;
    await settings.load();
    const skipped = summary.skipped_screens
      ? ` ${summary.skipped_screens} screen${summary.skipped_screens === 1 ? "" : "s"} in the file aren't paired here and were skipped.`
      : "";
    settings.flash(`Settings restored.${skipped}`);
  }
</script>

<Scope kind="home" />

<Group
  title="Backup"
  description="Save every setting — profiles, screens, card options and custom themes — to a file, or restore one. Photos and API keys aren't included."
>
  <div class="row">
    <button type="button" class="btn" onclick={exportSettings}
      >Download backup</button
    >
    <label class="btn">
      Restore from file…
      <input
        type="file"
        accept="application/json,.json"
        onchange={chooseBackup}
      />
    </label>
  </div>
  {#if restoring}
    <div class="confirm" role="alertdialog" aria-label="Restore settings">
      <p>
        Replace the current settings with <strong>{restoreName}</strong>, saved
        {new Date(restoring.exported_at).toLocaleString()}? Every screen changes
        straight away.
      </p>
      <div class="row">
        <button type="button" class="btn" onclick={() => (restoring = null)}
          >Cancel</button
        >
        <button
          type="button"
          class="btn primary"
          disabled={busy}
          onclick={restore}>{busy ? "Restoring…" : "Restore"}</button
        >
      </div>
    </div>
  {/if}
</Group>

<Group
  title="API keys"
  description="Keys are stored encrypted on the server and never shown again."
>
  {#each secretNames as name (name)}
    <div class="key">
      <span>{name.replace(/_/g, " ")}</span>
      <button
        type="button"
        class="btn small danger"
        onclick={async () => {
          if (
            await settings.attempt(
              () => client.deleteSecret(name),
              "Key removed",
            )
          )
            await refreshKeys();
        }}>Remove</button
      >
    </div>
  {/each}
</Group>

<Group title="Server">
  <Field
    label="Setup"
    hint="Walk through the first-run questions again. Nothing is lost."
  >
    {#snippet children()}
      <button type="button" class="btn" onclick={onRunSetup}>Run setup</button>
    {/snippet}
  </Field>
  <p class="hint note">
    To install the app or keep the screen awake, the dashboard needs HTTPS — a
    Tailscale address, a Caddy local certificate, or a real certificate. See
    Help.
  </p>
</Group>

<style>
  .row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding: 12px 0;
  }
  label.btn input {
    display: none;
  }
  .confirm {
    padding: 12px;
    margin-bottom: 12px;
    border-radius: 12px;
    font-size: var(--type-sm);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }
  .confirm .row {
    padding-bottom: 0;
    justify-content: flex-end;
  }
  .key {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    font-size: var(--type-sm);
    text-transform: capitalize;
  }
  .note {
    padding: 12px 0;
  }
</style>
