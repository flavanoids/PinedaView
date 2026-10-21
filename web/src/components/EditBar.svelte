<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  interface Props {
    onSaveDevice: () => void;
    onSaveProfile: () => void;
    onCancel: () => void;
  }
  let { onSaveDevice, onSaveProfile, onCancel }: Props = $props();
</script>

<div class="bar" role="toolbar" aria-label="Layout editor">
  <span class="hint">Drag cards to reorder</span>
  <div class="actions">
    <button class="ghost" onclick={onCancel}>Cancel</button>
    <button class="ghost" onclick={onSaveProfile}>Save to profile</button>
    <button class="primary" onclick={onSaveDevice}>Save to this screen</button>
  </div>
</div>

<style>
  .bar {
    position: fixed;
    left: 50%;
    bottom: max(var(--space-3), env(safe-area-inset-bottom));
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-pill);
    background: var(--on-stage);
    color: var(--stage);
    box-shadow: 0 10px 30px -8px rgba(0, 0, 0, 0.4);
    z-index: 15;
    max-width: calc(100vw - var(--space-4));
    flex-wrap: wrap;
    justify-content: center;
  }
  .hint {
    font-size: var(--type-caption);
    opacity: 0.7;
  }
  .actions {
    display: flex;
    gap: var(--space-2);
  }
  button {
    font: inherit;
    font-size: var(--type-sm);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-pill);
    border: none;
    cursor: pointer;
  }
  .ghost {
    background: transparent;
    color: var(--stage);
    opacity: 0.75;
  }
  .primary {
    background: var(--accent);
    color: var(--stage);
    font-weight: 600;
  }
</style>
