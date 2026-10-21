<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- A short list of mutually exclusive choices, as one row of pills. -->
<script lang="ts" generics="T extends string">
  /* eslint-disable no-undef -- T is this component's generic, which the
     linter can't see declared. */
  interface Props {
    id?: string;
    options: readonly { value: T; label: string }[];
    value: T;
    /** Only needed when no Field names it. */
    label?: string;
    disabled?: boolean;
    onchange: (value: T) => void;
  }
  let {
    id,
    options,
    value,
    label,
    disabled = false,
    onchange,
  }: Props = $props();
</script>

<div
  class="segmented"
  role="radiogroup"
  {id}
  aria-label={label}
  aria-labelledby={label || !id ? undefined : `${id}-label`}
>
  {#each options as opt (opt.value)}
    <button
      type="button"
      role="radio"
      aria-checked={value === opt.value}
      class:on={value === opt.value}
      {disabled}
      onclick={() => value !== opt.value && onchange(opt.value)}
      >{opt.label}</button
    >
  {/each}
</div>

<style>
  .segmented {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 2px;
    padding: 2px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--on-stage) 8%, transparent);
  }
  button {
    font: inherit;
    font-size: var(--type-sm);
    min-height: 2.25rem;
    padding: 0 14px;
    border: none;
    border-radius: 10px;
    background: none;
    color: var(--on-stage-soft);
    cursor: pointer;
    white-space: nowrap;
  }
  button.on {
    background: var(--stage);
    color: var(--on-stage);
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
  }
  button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
</style>
