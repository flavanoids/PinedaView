<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { CardView } from "@pinedaview/protocol";

  import { useSettings } from "../lib/settings.svelte";
  import CardSettings from "./CardSettings.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import ResetButton from "./settings/ResetButton.svelte";
  import Segmented from "./settings/Segmented.svelte";
  import Switch from "./settings/Switch.svelte";
  import StackModel from "./StackModel.svelte";

  interface Props {
    cards: CardView[];
    canEditLayout: boolean;
    onEditLayout: () => void;
  }
  let { cards, canEditLayout, onEditLayout }: Props = $props();

  const settings = useSettings();
  const profile = $derived(settings.profile);
  const screen = $derived(settings.screen);

  const PACES = [
    { value: "relaxed", label: "Relaxed" },
    { value: "normal", label: "Normal" },
    { value: "brisk", label: "Brisk" },
  ] as const;

  /** The cards this screen is set up with, in order. */
  const stack = $derived(
    screen?.grid
      ? screen.grid.items.map((i) => i.card)
      : screen?.card_stack?.length
        ? screen.card_stack
        : (profile?.card_stack ?? []),
  );
  const profileStack = $derived(profile?.card_stack ?? []);

  function nameOf(id: string): string {
    return (
      cards.find((c) => c.id === id)?.name ??
      id.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase())
    );
  }

  function setShown(card: string, on: boolean): void {
    const off = new Set(screen?.cards_off ?? []);
    if (on) off.delete(card);
    else off.add(card);
    void settings.saveScreen({ cards_off: [...off] });
  }

  /** The row under the pointer or focus, lit in the miniature. */
  let pointing = $state<string | null>(null);

  let newWord = $state("");
  function addWord(): void {
    const word = newWord.trim();
    if (!word || !profile) return;
    newWord = "";
    void settings.saveProfile({
      hide_words: [...(profile.hide_words ?? []), word],
    });
  }
  async function removeWord(word: string): Promise<void> {
    if (!profile) return;
    await settings.saveProfile({
      hide_words: (profile.hide_words ?? []).filter((w) => w !== word),
    });
    if (settings.profile?.hide_words?.includes(word)) return; // didn't save
    settings.flash(`Showing “${word}” again`, false, {
      label: "Undo",
      run: () =>
        void settings.saveProfile({
          hide_words: [...(settings.profile?.hide_words ?? []), word],
        }),
    });
  }
</script>

{#if profile && screen}
  <StackModel
    {screen}
    {profile}
    {stack}
    here={settings.editingHere}
    name={nameOf}
    {pointing}
  />

  {#if canEditLayout}
    <button type="button" class="btn primary wide" onclick={onEditLayout}
      >Rearrange cards on this screen</button
    >
  {/if}

  <Group
    title="On {settings.screenName}"
    description={screen.grid
      ? "This screen uses a hand-placed layout. Add or remove cards in the layout editor."
      : "Turn a card off to hide it here. It keeps its place for when you turn it back on."}
  >
    {#if !screen.grid}
      {#each stack as card (card)}
        <div
          role="presentation"
          class="card-row"
          class:off={(screen.cards_off ?? []).includes(card)}
          onpointerenter={() => (pointing = card)}
          onpointerleave={() => (pointing = null)}
          onfocusin={() => (pointing = card)}
          onfocusout={() => (pointing = null)}
        >
          <Field label={nameOf(card)}>
            {#snippet children(id)}
              <Switch
                {id}
                checked={!(screen.cards_off ?? []).includes(card)}
                onchange={(on) => setShown(card, on)}
              />
            {/snippet}
          </Field>
        </div>
      {/each}
    {/if}
    <Field
      label="Dynamic Shuffle"
      hint="Take turns expanding each card into the large hero spotlight so everything can be read from across the room."
    >
      {#snippet children(id)}
        <Switch
          {id}
          checked={screen.dynamic_shuffle ?? profile.dynamic_shuffle}
          onchange={(on) => settings.saveScreen({ dynamic_shuffle: on })}
        />
      {/snippet}
    </Field>
    {#if screen.dynamic_shuffle ?? profile.dynamic_shuffle}
      <Field
        label="Hero card time"
        hint="How long each card stays large before returning to its spot."
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={[
              { value: "10", label: "10 s" },
              { value: "15", label: "15 s" },
              { value: "30", label: "30 s" },
              { value: "60", label: "60 s" },
            ]}
            value={String(
              screen.shuffle_hold_s ?? profile.shuffle_hold_s ?? 15,
            )}
            onchange={(v) => settings.saveScreen({ shuffle_hold_s: Number(v) })}
          />
        {/snippet}
      </Field>
      <Field
        label="Show cards every"
        hint="Hands-free rotation from the photo clock to the cards."
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={[
              { value: "2", label: "2 min" },
              { value: "5", label: "5 min" },
              { value: "10", label: "10 min" },
              { value: "15", label: "15 min" },
            ]}
            value={String(
              screen.ambient_cycle_m ?? profile.ambient_cycle_m ?? 5,
            )}
            onchange={(v) =>
              settings.saveScreen({ ambient_cycle_m: Number(v) })}
          />
        {/snippet}
      </Field>
    {/if}
    <Field
      label="Large card"
      hint="The card that gets the big space. Automatic picks photos, then the clock."
    >
      {#snippet children(id)}
        <select
          {id}
          value={screen.hero_card ?? ""}
          onchange={(e) =>
            settings.saveScreen({ hero_card: e.currentTarget.value })}
        >
          <option value=""
            >{profile.hero_card
              ? `Profile's choice (${nameOf(profile.hero_card)})`
              : "Automatic"}</option
          >
          {#each stack as card (card)}
            <option value={card}>{nameOf(card)}</option>
          {/each}
        </select>
      {/snippet}
    </Field>
  </Group>

  <Group title="For every screen on “{profile.name}”">
    <Field
      label="Dynamic Shuffle"
      hint="Take turns expanding each card into the large hero spotlight so everything can be read from across the room."
    >
      {#snippet children(id)}
        <Switch
          {id}
          checked={profile.dynamic_shuffle}
          onchange={(on) => settings.saveProfile({ dynamic_shuffle: on })}
        />
      {/snippet}
    </Field>
    {#if profile.dynamic_shuffle}
      <Field
        label="Hero card time"
        hint="Default dwell time for screens on this profile."
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={[
              { value: "10", label: "10 s" },
              { value: "15", label: "15 s" },
              { value: "30", label: "30 s" },
              { value: "60", label: "60 s" },
            ]}
            value={String(profile.shuffle_hold_s ?? 15)}
            onchange={(v) =>
              settings.saveProfile({ shuffle_hold_s: Number(v) })}
          />
        {/snippet}
      </Field>
      <Field
        label="Show cards every"
        hint="Default hands-free rotation interval."
      >
        {#snippet children(id)}
          <Segmented
            {id}
            options={[
              { value: "2", label: "2 min" },
              { value: "5", label: "5 min" },
              { value: "10", label: "10 min" },
              { value: "15", label: "15 min" },
            ]}
            value={String(profile.ambient_cycle_m ?? 5)}
            onchange={(v) =>
              settings.saveProfile({ ambient_cycle_m: Number(v) })}
          />
        {/snippet}
      </Field>
    {/if}
    <Field
      label="Large card"
      hint="Used by screens that don't pick their own above."
    >
      {#snippet children(id)}
        <select
          {id}
          value={profile.hero_card ?? ""}
          onchange={(e) =>
            settings.saveProfile({ hero_card: e.currentTarget.value })}
        >
          <option value="">Automatic</option>
          {#each profileStack as card (card)}
            <option value={card}>{nameOf(card)}</option>
          {/each}
        </select>
      {/snippet}
    </Field>
    <Field
      label="Rotation speed"
      hint="How long quotes, headlines and camera views stay up before the next one."
    >
      {#snippet children(id)}
        <Segmented
          {id}
          options={PACES}
          value={profile.pace}
          onchange={(pace) => settings.saveProfile({ pace })}
        />
      {/snippet}
    </Field>
    <Field
      label="Hide topics"
      hint="Skip headlines and quotes that mention any of these words."
      stacked
    >
      {#snippet children(id)}
        {#if profile.hide_words?.length}
          <ul class="chips">
            {#each profile.hide_words ?? [] as word (word)}
              <li>
                {word}
                <button
                  type="button"
                  aria-label="Stop hiding “{word}”"
                  onclick={() => removeWord(word)}>×</button
                >
              </li>
            {/each}
          </ul>
        {/if}
        <form
          class="add"
          onsubmit={(e) => {
            e.preventDefault();
            addWord();
          }}
        >
          <input
            {id}
            placeholder="A word or phrase"
            maxlength="60"
            bind:value={newWord}
          />
          <button type="submit" class="btn" disabled={!newWord.trim()}
            >Hide</button
          >
        </form>
      {/snippet}
    </Field>
  </Group>

  <Group
    title="Card options"
    description="Settings that belong to one card, like commute stops or news topics."
  >
    <CardSettings {cards} />
  </Group>

  <ResetButton
    what="which cards show here, the large card, rotation speed and hidden topics. Card options and the layout stay as they are"
    onreset={async () => {
      const done = await settings.save(
        () =>
          settings.client.resetSection({
            section: "cards",
            profile_id: profile.id,
            device_id: screen.id,
          }),
        "Cards reset",
      );
      if (done) await settings.load();
    }}
  />
{/if}

<style>
  /* A card that's off reads as set aside, not gone: it keeps its row. */
  .card-row :global(.label) {
    transition: color var(--dur-fast) linear;
  }
  .card-row.off :global(.label) {
    color: var(--on-stage-soft);
  }
  .wide {
    width: 100%;
    margin-bottom: var(--space-3);
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    list-style: none;
  }
  .chips li {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 4px 4px 12px;
    border-radius: var(--radius-pill);
    background: color-mix(in srgb, var(--on-stage) 9%, transparent);
    font-size: var(--type-sm);
  }
  .chips button {
    width: 1.6rem;
    height: 1.6rem;
    border: none;
    border-radius: 50%;
    background: none;
    color: var(--on-stage-soft);
    font-size: 1.1rem;
    line-height: 1;
    cursor: pointer;
  }
  .add {
    display: flex;
    gap: var(--space-2);
  }
  .add input {
    flex: 1;
  }
</style>
