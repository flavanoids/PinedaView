<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Per-card options (Settings → Cards & layout → Card options), drawn from
     each card's manifest. -->
<script lang="ts">
  import type { CardView } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import BeatsEditor from "./BeatsEditor.svelte";
  import Field from "./settings/Field.svelte";
  import Switch from "./settings/Switch.svelte";

  interface Props {
    cards: CardView[];
  }
  let { cards }: Props = $props();

  const settings = useSettings();
  const client = settings.client;
  // Calendars are chosen when one is connected (the phone menu), not typed.
  const MANAGED = new Set(["calendar.sources"]);
  const configurable = $derived(
    cards.filter((c) =>
      Object.keys(c.settings).some((key) => !MANAGED.has(`${c.id}.${key}`)),
    ),
  );

  let selectedId = $state("");
  let values = $state<Record<string, unknown>>({});
  const selected = $derived(configurable.find((c) => c.id === selectedId));
  const fields = $derived(
    Object.entries(selected?.settings ?? {}).filter(
      ([key]) => !MANAGED.has(`${selectedId}.${key}`),
    ),
  );

  $effect(() => {
    if (!selectedId && configurable[0]) selectedId = configurable[0].id;
  });
  $effect(() => {
    if (!selectedId) return;
    void client.getCardSettings(selectedId).then((s) => (values = s.values));
  });

  async function save(key: string, value: unknown): Promise<void> {
    values = { ...values, [key]: value };
    const id = selectedId;
    const next = values;
    await settings.attempt(() => client.setCardSettings(id, next));
  }

  // A list of "Label | Address" stops, or of plain strings (camera numbers).
  type Stop = { label?: string; address?: string };
  function isStops(list: unknown): boolean {
    return Array.isArray(list) && list.some((i) => i && typeof i === "object");
  }
  function listToText(list: unknown, stops: boolean): string {
    if (!Array.isArray(list)) return "";
    return list
      .map((item) =>
        stops && item && typeof item === "object"
          ? `${(item as Stop).label ?? ""} | ${(item as Stop).address ?? ""}`
          : String(item),
      )
      .join("\n");
  }
  function textToList(text: string, stops: boolean): unknown[] {
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (!stops) return lines;
    return lines
      .map((line) => line.split("|").map((s) => s.trim()))
      .filter((parts) => parts[1])
      .map((parts) => ({ label: parts[0] ?? "", address: parts[1] ?? "" }));
  }
  // Stops are the one object list; an empty one still needs the stop format.
  const stopsKey = (key: string, list: unknown, fallback: unknown) =>
    key === "stops" || isStops(list) || isStops(fallback);
</script>

{#if configurable.length === 0}
  <p class="hint">None of the cards have options yet.</p>
{:else}
  <Field label="Card">
    {#snippet children(id)}
      <select {id} bind:value={selectedId}>
        {#each configurable as card (card.id)}
          <option value={card.id}>{card.name}</option>
        {/each}
      </select>
    {/snippet}
  </Field>

  {#if selected}
    {#if selected.status === "blocked" && selected.reason}
      <p class="blocked">Not showing yet: {selected.reason}</p>
    {/if}
    {#each fields as [key, spec] (key)}
      {#if spec.type === "beats"}
        <Field label={spec.title} hint={spec.description || undefined} stacked>
          {#snippet children()}
            <BeatsEditor
              beats={values[key] ?? spec.default}
              sources={spec.enum ?? []}
              labels={spec.labels ?? {}}
              onsave={(beats) => save(key, beats)}
            />
          {/snippet}
        </Field>
      {:else if spec.type === "boolean"}
        <Field label={spec.title} hint={spec.description || undefined}>
          {#snippet children(id)}
            <Switch
              {id}
              checked={Boolean(values[key] ?? spec.default)}
              onchange={(on) => save(key, on)}
            />
          {/snippet}
        </Field>
      {:else if spec.type === "list"}
        {@const stops = stopsKey(key, values[key], spec.default)}
        <Field label={spec.title} hint={spec.description || undefined} stacked>
          {#snippet children(id)}
            <textarea
              {id}
              rows="4"
              placeholder={stops ? "Work | 1 Main St, Houston" : "One per line"}
              value={listToText(values[key] ?? spec.default, stops)}
              onchange={(e) =>
                save(key, textToList(e.currentTarget.value, stops))}
            ></textarea>
          {/snippet}
        </Field>
      {:else}
        <Field label={spec.title} hint={spec.description || undefined}>
          {#snippet children(id)}
            {#if spec.type === "integer" || spec.type === "number"}
              <input
                {id}
                type="number"
                class="number"
                min={spec.min ?? undefined}
                max={spec.max ?? undefined}
                value={Number(values[key] ?? spec.default ?? 0)}
                onchange={(e) => save(key, Number(e.currentTarget.value))}
              />
            {:else if spec.type === "enum"}
              <select
                {id}
                value={String(values[key] ?? spec.default ?? "")}
                onchange={(e) => save(key, e.currentTarget.value)}
              >
                {#each spec.enum ?? [] as option (option)}
                  <option value={option}
                    >{spec.labels?.[option] ??
                      option[0]?.toUpperCase() + option.slice(1)}</option
                  >
                {/each}
              </select>
            {:else if spec.type === "timerange"}
              {@const parts = String(values[key] ?? spec.default ?? "").split(
                "-",
              )}
              <span class="times">
                <input
                  {id}
                  type="time"
                  aria-label="{spec.title}: from"
                  value={parts[0] ?? ""}
                  onchange={(e) =>
                    save(key, `${e.currentTarget.value}-${parts[1] ?? ""}`)}
                />
                <span>to</span>
                <input
                  type="time"
                  aria-label="{spec.title}: until"
                  value={parts[1] ?? ""}
                  onchange={(e) =>
                    save(key, `${parts[0] ?? ""}-${e.currentTarget.value}`)}
                />
              </span>
            {:else}
              <input
                {id}
                value={String(values[key] ?? spec.default ?? "")}
                onchange={(e) => save(key, e.currentTarget.value)}
              />
            {/if}
          {/snippet}
        </Field>
      {/if}
    {/each}
  {/if}
{/if}

<style>
  .blocked {
    margin: 4px 0;
    padding: 6px 10px;
    border-radius: 8px;
    font-size: var(--type-caption);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }
  .number {
    width: 6rem;
  }
</style>
