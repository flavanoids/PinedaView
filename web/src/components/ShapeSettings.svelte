<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { CardView } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import Segmented from "./settings/Segmented.svelte";

  // A screen's shape: the usual rectangle of cards, or the round watch face
  // (RoundStage) with up to four cards under clock hands. Per screen — a
  // round face suits a wall display, not a phone — while colours and fonts
  // still come from the profile's theme.

  const settings = useSettings();
  const client = settings.client;
  const screen = $derived(settings.screen);
  const profile = $derived(settings.profile);

  let cards = $state<CardView[]>([]);
  $effect(() => {
    void client.listCards().then((list) => (cards = list));
  });

  const SHAPES = [
    { value: "rect", label: "Rectangle" },
    { value: "circle", label: "Circle" },
  ] as const;
  const COUNTS = [
    { value: "1", label: "1" },
    { value: "2", label: "2" },
    { value: "3", label: "3" },
    { value: "4", label: "4" },
  ] as const;

  /** Each slot's name for a face with `n` cards, listed top to bottom. */
  function slotNames(n: number): { slot: number; name: string }[] {
    if (n <= 1) return [{ slot: 0, name: "Centre" }];
    if (n === 2)
      return [
        { slot: 0, name: "Centre" },
        { slot: 1, name: "Bottom" },
      ];
    if (n === 3)
      return [
        { slot: 1, name: "Top" },
        { slot: 0, name: "Centre" },
        { slot: 2, name: "Bottom" },
      ];
    return [
      { slot: 1, name: "Top" },
      { slot: 0, name: "Centre" },
      { slot: 2, name: "Bottom left" },
      { slot: 3, name: "Bottom right" },
    ];
  }

  const pickable = $derived(cards.filter((c) => c.id !== "clock"));
  const stack = $derived(
    screen?.card_stack?.length
      ? screen.card_stack
      : (profile?.card_stack ?? []),
  );
  /** What the face shows now: its own pick, or the server's default. */
  const current = $derived(
    screen?.circle_stack ??
      stack
        .filter((c) => c !== "clock" && !(screen?.cards_off ?? []).includes(c))
        .slice(0, 4),
  );

  function nameOf(id: string): string {
    return (
      cards.find((c) => c.id === id)?.name ??
      id.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase())
    );
  }

  function setCount(n: number): void {
    const next = current.slice(0, n);
    for (const c of [...stack, ...pickable.map((p) => p.id)]) {
      if (next.length >= n) break;
      if (c !== "clock" && !next.includes(c)) next.push(c);
    }
    void settings.saveScreen({ circle_stack: next });
  }

  /** Put `card` in `slot`; if it's already in another slot, they swap. */
  function setSlot(slot: number, card: string): void {
    const next = [...current];
    const was = next.indexOf(card);
    if (was >= 0) next[was] = next[slot]!;
    next[slot] = card;
    void settings.saveScreen({ circle_stack: next });
  }
</script>

{#if screen}
  <Group
    title="Shape"
    description="Just {settings.screenName}. A circle is a round watch face: up to four cards, with hands that tell the time, on black. Colours and fonts still come from the theme."
  >
    <Field label="Shape">
      {#snippet children(id)}
        <Segmented
          {id}
          options={SHAPES}
          value={screen.shape ?? "rect"}
          onchange={(shape) => settings.saveScreen({ shape })}
        />
      {/snippet}
    </Field>
    {#if screen.shape === "circle"}
      <Field
        label="Cards"
        hint="The hands are the clock, so the clock card isn't offered."
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={COUNTS}
            value={String(Math.max(1, current.length))}
            onchange={(v) => setCount(Number(v))}
          />
        {/snippet}
      </Field>
      {#each slotNames(current.length) as { slot, name } (slot)}
        <Field label={name}>
          {#snippet children(id)}
            <select
              {id}
              value={current[slot] ?? ""}
              onchange={(e) => setSlot(slot, e.currentTarget.value)}
            >
              {#if !current[slot]}<option value="">Choose a card</option>{/if}
              {#each pickable as card (card.id)}
                <option value={card.id}>{nameOf(card.id)}</option>
              {/each}
            </select>
          {/snippet}
        </Field>
      {/each}
      {#if !current.includes("photo")}
        <p class="note">
          The settings code is on the photo card. Without it, open settings from
          your phone's menu or another screen.
        </p>
      {/if}
    {/if}
  </Group>
{/if}

<style>
  .note {
    margin: 0;
    font-size: var(--type-caption);
    opacity: 0.75;
  }
</style>
