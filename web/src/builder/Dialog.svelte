<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Snippet } from "svelte";

  import { modal } from "../lib/modal";

  interface Props {
    title: string;
    confirm: string;
    /** The button that closes without doing anything. */
    cancel?: string;
    /** Red confirm button, for the things that can't be taken back. */
    danger?: boolean;
    disabled?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    children?: Snippet;
  }
  let {
    title,
    confirm,
    cancel = "Cancel",
    danger = false,
    disabled = false,
    onConfirm,
    onCancel,
    children,
  }: Props = $props();
</script>

<div
  class="backdrop"
  use:modal={{ onClose: onCancel }}
  onclick={(e) => {
    if (e.target === e.currentTarget) onCancel();
  }}
  role="presentation"
>
  <div
    class="panel"
    role="alertdialog"
    aria-modal="true"
    aria-labelledby="dialog-title"
    tabindex="-1"
  >
    <h2 id="dialog-title">{title}</h2>
    <div class="body">{@render children?.()}</div>
    <div class="actions">
      <button type="button" class="ghost" onclick={onCancel}>{cancel}</button>
      <button
        type="button"
        class="primary"
        class:danger
        {disabled}
        onclick={onConfirm}>{confirm}</button
      >
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    display: grid;
    place-items: end center;
    padding: 12px;
    background: rgba(0, 0, 0, 0.55);
    animation: fade 160ms ease;
  }
  @media (min-width: 640px) {
    .backdrop {
      place-items: center;
    }
  }
  .panel {
    width: min(100%, 26rem);
    max-height: 85dvh;
    overflow-y: auto;
    padding: 20px 18px max(16px, env(safe-area-inset-bottom));
    border-radius: 20px;
    background: #17150f;
    box-shadow:
      0 0 0 1px var(--rule),
      0 24px 60px -20px #000;
    animation: rise 200ms ease;
  }
  .panel:focus {
    outline: none;
  }
  h2 {
    margin: 0 0 8px;
    font: 500 1.3rem/1.25 var(--display);
  }
  .body {
    color: var(--soft);
  }
  .body :global(p) {
    margin: 0 0 10px;
  }
  .body :global(ul) {
    margin: 0 0 10px;
    padding-left: 1.1em;
  }
  .actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 16px;
  }
  .actions button {
    min-height: 44px;
    padding: 0 18px;
    border-radius: 999px;
    border: none;
    font-weight: 600;
  }
  .ghost {
    background: var(--wash);
  }
  .primary {
    background: var(--accent);
    color: #1a1206;
  }
  .primary.danger {
    background: #e2594a;
    color: #fff;
  }
  .primary:disabled {
    opacity: 0.4;
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
  }
  @keyframes rise {
    from {
      transform: translateY(16px);
      opacity: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .backdrop,
    .panel {
      animation: none;
    }
  }
</style>
