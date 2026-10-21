<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { ConnectionStatus } from "../lib/connection.svelte";
  import { timeOfDay } from "../lib/format";

  const LABELS: Record<ConnectionStatus, string> = {
    connecting: "Connecting…",
    live: "Online",
    reconnecting: "Reconnecting…",
    offline: "Offline",
  };

  interface Props {
    status: ConnectionStatus;
    /** When the view on screen was made (ISO 8601) — what "last update"
        means while the connection is down. */
    since?: string;
  }
  let { status, since }: Props = $props();

  const text = $derived(
    since && (status === "offline" || status === "reconnecting")
      ? `${LABELS[status]} · last update ${timeOfDay(new Date(since))}`
      : LABELS[status],
  );
</script>

<!-- Always in the DOM so the live region announces reconnect / offline; the
     pill is hidden visually while the connection is healthy. -->
<div
  class="pill"
  class:hidden={status === "live"}
  data-status={status}
  role="status"
  aria-live="polite"
>
  <span class="visually-hidden">Connection: </span>{text}
</div>

<style>
  .pill {
    position: fixed;
    bottom: max(var(--space-3), env(safe-area-inset-bottom));
    left: 50%;
    transform: translateX(-50%);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-pill);
    background: color-mix(in srgb, var(--on-stage) 12%, transparent);
    color: var(--on-stage-soft);
    font-size: var(--type-caption);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    backdrop-filter: blur(var(--card-blur));
  }
  .pill.hidden {
    opacity: 0;
    pointer-events: none;
  }
  .pill[data-status="offline"] {
    color: var(--accent);
  }
</style>
