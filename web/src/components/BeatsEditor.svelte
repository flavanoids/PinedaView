<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  The news card's beats: each a name, the outlets it reads, the keywords that
  pull a story in or keep one out, and how many turns it gets per round.
  Every edit saves the whole list — the server re-sorts the stories it
  already has straight away, so a change shows on the screen in seconds.
-->
<script lang="ts">
  interface Beat {
    name: string;
    enabled?: boolean;
    weight?: number;
    maxAgeHours?: number;
    sources: string[];
    keywords: string[];
    exclude: string[];
  }

  interface Props {
    beats: unknown;
    /** Every outlet feed the server knows, by id… */
    sources: string[];
    /** …and what to call each one. */
    labels: Record<string, string>;
    onsave: (beats: Beat[]) => void;
  }
  let { beats, sources, labels, onsave }: Props = $props();

  const list = $derived(Array.isArray(beats) ? (beats as Beat[]) : []);

  function update(index: number, patch: Partial<Beat>): void {
    onsave(list.map((b, i) => (i === index ? { ...b, ...patch } : b)));
  }
  function remove(index: number): void {
    onsave(list.filter((_, i) => i !== index));
  }
  function add(): void {
    onsave([
      ...list,
      {
        name: "New beat",
        enabled: true,
        weight: 1,
        maxAgeHours: 24,
        sources: [],
        keywords: [],
        exclude: [],
      },
    ]);
  }
  function toggleSource(index: number, id: string, on: boolean): void {
    const current = list[index]?.sources ?? [];
    update(index, {
      sources: on ? [...current, id] : current.filter((s) => s !== id),
    });
  }

  const words = (text: string): string[] =>
    text
      .split(/[,\n]/)
      .map((w) => w.trim())
      .filter(Boolean);
  const extraFeeds = (beat: Beat): string[] =>
    beat.sources.filter((s) => s.startsWith("https://"));
  function setExtraFeeds(index: number, text: string): void {
    const known = (list[index]?.sources ?? []).filter((s) =>
      sources.includes(s),
    );
    const urls = words(text).filter((s) => s.startsWith("https://"));
    update(index, { sources: [...known, ...urls] });
  }
</script>

<div class="beats">
  {#each list as beat, i (i)}
    <details class="beat">
      <summary>
        <span class="name" class:off={beat.enabled === false}>{beat.name}</span>
        <span class="count">{beat.sources.length} feeds</span>
      </summary>

      <label class="row">
        <input
          type="checkbox"
          checked={beat.enabled !== false}
          onchange={(e) => update(i, { enabled: e.currentTarget.checked })}
        />
        Show this beat
      </label>
      <label>
        Name
        <input
          value={beat.name}
          onchange={(e) => update(i, { name: e.currentTarget.value.trim() })}
        />
      </label>
      <div class="pair">
        <label>
          Turns per round
          <input
            type="number"
            min="1"
            max="5"
            value={beat.weight ?? 1}
            onchange={(e) =>
              update(i, { weight: Number(e.currentTarget.value) })}
          />
        </label>
        <label>
          Oldest story (hours)
          <input
            type="number"
            min="1"
            max="168"
            value={beat.maxAgeHours ?? 24}
            onchange={(e) =>
              update(i, { maxAgeHours: Number(e.currentTarget.value) })}
          />
        </label>
      </div>
      <label>
        Topics
        <textarea
          rows="3"
          placeholder="Leave empty for every story from these feeds"
          value={beat.keywords.join(", ")}
          onchange={(e) =>
            update(i, { keywords: words(e.currentTarget.value) })}
        ></textarea>
      </label>
      <label>
        Leave out stories about
        <textarea
          rows="2"
          value={beat.exclude.join(", ")}
          onchange={(e) => update(i, { exclude: words(e.currentTarget.value) })}
        ></textarea>
      </label>
      <p class="hint">
        Separate with commas. End a word with * to match its start (immigra*
        finds immigrant and immigration). Write it in capitals to match capitals
        only (ICE, not ice).
      </p>

      <fieldset>
        <legend>Feeds</legend>
        {#each sources as id (id)}
          <label class="row">
            <input
              type="checkbox"
              checked={beat.sources.includes(id)}
              onchange={(e) => toggleSource(i, id, e.currentTarget.checked)}
            />
            {labels[id] ?? id}
          </label>
        {/each}
      </fieldset>
      <label>
        Other RSS feeds (one address per line)
        <textarea
          rows="2"
          placeholder="https://…"
          value={extraFeeds(beat).join("\n")}
          onchange={(e) => setExtraFeeds(i, e.currentTarget.value)}
        ></textarea>
      </label>

      <button type="button" class="remove" onclick={() => remove(i)}>
        Remove {beat.name}
      </button>
    </details>
  {/each}
  <button type="button" onclick={add}>Add a beat</button>
</div>

<style>
  .beats {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .beat {
    display: flex;
    flex-direction: column;
    border: 1px solid color-mix(in srgb, var(--on-stage) 22%, transparent);
    border-radius: 10px;
    padding: var(--space-2) var(--space-3);
  }
  .beat[open] {
    padding-bottom: var(--space-3);
  }
  .beat > :not(summary) {
    margin-top: var(--space-2);
  }
  summary {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    cursor: pointer;
    font-weight: 600;
  }
  .name.off {
    opacity: 0.5;
    text-decoration: line-through;
  }
  .count {
    font-weight: normal;
    color: var(--on-stage-soft);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: var(--type-sm);
  }
  label.row {
    flex-direction: row;
    align-items: center;
    gap: var(--space-2);
  }
  .pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }
  fieldset {
    border: none;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
    gap: 2px var(--space-3);
  }
  legend {
    font-size: var(--type-sm);
    margin-bottom: 4px;
  }
  .hint {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  input,
  textarea,
  button {
    font: inherit;
    background: none;
    border: 1px solid color-mix(in srgb, var(--on-stage) 22%, transparent);
    color: var(--on-stage);
    border-radius: 8px;
    padding: 6px 8px;
  }
  input[type="checkbox"] {
    padding: 0;
  }
  button {
    cursor: pointer;
    align-self: flex-start;
  }
  .remove {
    color: var(--accent);
  }
</style>
