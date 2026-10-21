<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  interface Props {
    id?: string;
    checked: boolean;
    disabled?: boolean;
    /** Only needed when no <label for> names it. */
    label?: string;
    onchange: (checked: boolean) => void;
  }
  let { id, checked, disabled = false, label, onchange }: Props = $props();
</script>

<button
  type="button"
  role="switch"
  class="switch"
  {id}
  aria-checked={checked}
  aria-label={label}
  {disabled}
  onclick={() => onchange(!checked)}
>
  <span class="thumb" aria-hidden="true"></span>
</button>

<style>
  .switch {
    flex: none;
    position: relative;
    width: 2.9rem;
    height: 1.7rem;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: color-mix(in srgb, var(--on-stage) 22%, transparent);
    cursor: pointer;
  }
  .switch[aria-checked="true"] {
    background: var(--accent);
  }
  .switch:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .switch:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .thumb {
    position: absolute;
    top: 0.2rem;
    left: 0.2rem;
    width: 1.3rem;
    height: 1.3rem;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  }
  [aria-checked="true"] .thumb {
    transform: translateX(1.2rem);
  }
  @media (prefers-reduced-motion: no-preference) {
    .thumb,
    .switch {
      transition:
        transform var(--dur-fast) var(--ease-spring),
        background-color var(--dur-fast) linear;
    }
  }
</style>
