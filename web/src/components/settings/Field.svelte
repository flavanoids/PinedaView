<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  One setting: its name and a one-line explanation on the left, the control
  on the right (or underneath, `stacked`, for wide controls). The control
  snippet gets an id to put on its input so the name labels it.
-->
<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    label: string;
    hint?: string;
    stacked?: boolean;
    children: Snippet<[string]>;
  }
  let { label, hint, stacked = false, children }: Props = $props();
  const id = $props.id();
</script>

<div class="field" class:stacked data-field>
  <div class="text">
    <label class="label" for={id} id="{id}-label">{label}</label>
    {#if hint}<p class="hint">{hint}</p>{/if}
  </div>
  <div class="control">{@render children(id)}</div>
</div>

<style>
  .field {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
    padding: 12px 0;
  }
  /* Where Settings search lands: a brief wash so the eye finds the row. */
  .field:global(.found) {
    animation: found 1.6s ease-out;
    border-radius: 10px;
  }
  @keyframes found {
    0%,
    40% {
      background: color-mix(in srgb, var(--accent) 22%, transparent);
    }
    100% {
      background: transparent;
    }
  }
  .field.stacked {
    flex-direction: column;
    align-items: stretch;
  }
  .text {
    flex: 1 1 12rem;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .label {
    font-size: var(--type-sm);
    font-weight: 500;
    color: var(--on-stage);
  }
  .hint {
    font-size: var(--type-caption);
    line-height: 1.4;
    color: var(--on-stage-soft);
  }
  .control {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .stacked .text {
    flex: none;
  }
  .stacked .control {
    align-items: stretch;
    flex-direction: column;
  }
</style>
