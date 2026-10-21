<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- "Reset to defaults" at the foot of a section, with a confirm step. -->
<script lang="ts">
  interface Props {
    /** What gets reset, finishing "This resets …". */
    what: string;
    onreset: () => Promise<void> | void;
  }
  let { what, onreset }: Props = $props();
  let asking = $state(false);
  let busy = $state(false);

  async function confirm(): Promise<void> {
    busy = true;
    try {
      await onreset();
    } finally {
      busy = false;
      asking = false;
    }
  }
</script>

<div class="reset">
  {#if asking}
    <p>This resets {what}.</p>
    <div class="actions">
      <button type="button" class="btn" onclick={() => (asking = false)}
        >Cancel</button
      >
      <button type="button" class="btn danger" disabled={busy} onclick={confirm}
        >Reset</button
      >
    </div>
  {:else}
    <button type="button" class="link" onclick={() => (asking = true)}
      >Reset to defaults</button
    >
  {/if}
</div>

<style>
  .reset {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-top: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 9%, transparent);
  }
  p {
    font-size: var(--type-caption);
    color: var(--on-stage-soft);
  }
  .actions {
    display: flex;
    gap: var(--space-2);
  }
  .link {
    font: inherit;
    font-size: var(--type-caption);
    padding: 6px 0;
    border: none;
    background: none;
    color: var(--on-stage-soft);
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
  }
</style>
