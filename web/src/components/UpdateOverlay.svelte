<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { UpdateStatus } from "@pinedaview/protocol";
  import { fade, scale } from "svelte/transition";

  interface Props {
    status: UpdateStatus;
    onDismiss?: () => void;
  }

  let { status, onDismiss }: Props = $props();

  // Auto-dismiss confirmation after 6 seconds
  $effect(() => {
    if (status.state === "success") {
      const timer = setTimeout(() => {
        onDismiss?.();
      }, 6000);
      return () => clearTimeout(timer);
    }
    if (status.state === "failed") {
      const timer = setTimeout(() => {
        onDismiss?.();
      }, 25000);
      return () => clearTimeout(timer);
    }
  });

  const friendlyError = $derived.by(() => {
    if (status.error_message) return status.error_message;
    switch (status.error_code) {
      case "ERR_AUTH_REJECTED":
        return "Unable to access the private GitHub repository. Check deploy key permissions.";
      case "ERR_NETWORK_UNREACHABLE":
        return "Could not connect to GitHub. Check internet connection.";
      case "ERR_DISK_SPACE":
        return "Device storage is low. At least 500 MB free space is required to update.";
      case "ERR_DIRTY_TREE":
        return "Update paused because local uncommitted changes exist in the workspace.";
      case "ERR_BUILD_FAILED":
        return "Display assets could not be compiled. The previous stable version was kept.";
      case "ERR_HEALTHCHECK_TIMEOUT":
        return "The new version failed startup verification. Automatically rolled back to previous version.";
      default:
        return "An unexpected error occurred during update. The previous version was kept.";
    }
  });
</script>

{#if status.state === "updating" || status.state === "checking" || status.state === "success" || status.state === "failed"}
  <div
    class="scrim"
    transition:fade={{ duration: 240 }}
    role="dialog"
    aria-modal="true"
    aria-label="System Update"
  >
    <div class="card" transition:scale={{ start: 0.94, duration: 260 }}>
      {#if status.state === "updating" || status.state === "checking"}
        <!-- Small Centered Updating Spinner -->
        <div class="spinner-wrap" role="status" aria-live="polite">
          <div class="spinner">
            <span class="spinner-ring"></span>
            <span class="spinner-dot"></span>
          </div>
          <h2 class="title">
            {status.state === "checking"
              ? "Checking for Updates"
              : "Updating PinedaDisplay"}
          </h2>
          <p class="subtitle">
            {status.message ||
              (status.step === "building_web"
                ? "Compiling display assets…"
                : "Installing software update…")}
          </p>
          {#if status.target_commit || status.target_version}
            <div class="tag-pill">
              {status.target_version
                ? `v${status.target_version}`
                : ""}{status.target_commit ? ` • ${status.target_commit}` : ""}
            </div>
          {/if}
        </div>
      {:else if status.state === "success"}
        <!-- Success Confirmation -->
        <div class="status-wrap" role="status" aria-live="polite">
          <div class="icon-bubble success">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M20 6L9 17l-5-5" />
            </svg>
          </div>
          <h2 class="title">Update Complete</h2>
          <p class="subtitle">
            {status.message ||
              "Display is running the latest software version."}
          </p>
          {#if status.target_version || status.target_commit}
            <div class="tag-pill success">
              {status.target_version
                ? `v${status.target_version}`
                : ""}{status.target_commit ? ` • ${status.target_commit}` : ""}
            </div>
          {/if}
          <button type="button" class="action-btn" onclick={onDismiss}
            >Return to Display</button
          >
        </div>
      {:else if status.state === "failed"}
        <!-- Device-grade Diagnostic Error Card -->
        <div class="status-wrap" role="alert">
          <div class="icon-bubble alert">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
              />
            </svg>
          </div>
          <h2 class="title">Update Incomplete</h2>
          <p class="error-desc">{friendlyError}</p>

          {#if status.error_code}
            <div class="diag-code" title="Diagnostic Code">
              <span>CODE:</span> <code>{status.error_code}</code>
            </div>
          {/if}

          <p class="reassurance">
            Display safely restored to previous release.
          </p>
          <button type="button" class="action-btn" onclick={onDismiss}
            >Dismiss</button
          >
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 100;
    display: grid;
    place-items: center;
    background: rgba(6, 8, 14, 0.75);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    padding: var(--space-4);
  }

  .card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    width: 100%;
    max-width: 420px;
    padding: calc(var(--space-4) * 1.25);
    border-radius: var(--radius-card, 24px);
    background: color-mix(
      in srgb,
      var(--on-stage, #ffffff) 6%,
      rgba(20, 24, 36, 0.88)
    );
    border: 1px solid
      color-mix(in srgb, var(--on-stage, #ffffff) 14%, transparent);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
    color: var(--on-stage, #f0f2f8);
  }

  .spinner-wrap,
  .status-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
  }

  /* Small Centered Updating Spinner */
  .spinner {
    position: relative;
    width: 52px;
    height: 52px;
    display: grid;
    place-items: center;
    margin-bottom: var(--space-1);
  }

  .spinner-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 3px solid
      color-mix(in srgb, var(--accent, #689dff) 25%, transparent);
    border-top-color: var(--accent, #689dff);
    animation: spin 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }

  .spinner-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent, #689dff);
    box-shadow: 0 0 12px var(--accent, #689dff);
    animation: breathe 1.8s ease-in-out infinite;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes breathe {
    0%,
    100% {
      transform: scale(0.85);
      opacity: 0.6;
    }
    50% {
      transform: scale(1.15);
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner-ring,
    .spinner-dot {
      animation: none;
    }
  }

  .icon-bubble {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    margin-bottom: var(--space-1);
  }

  .icon-bubble svg {
    width: 24px;
    height: 24px;
  }

  .icon-bubble.success {
    background: rgba(34, 197, 94, 0.16);
    color: #4ade80;
    border: 1px solid rgba(74, 222, 128, 0.3);
  }

  .icon-bubble.alert {
    background: rgba(245, 158, 11, 0.16);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
  }

  .title {
    font-size: calc(1.25rem * var(--ui-scale, 1));
    font-weight: 600;
    margin: 0;
    letter-spacing: -0.01em;
    color: var(--on-stage, #ffffff);
  }

  .subtitle {
    font-size: calc(0.92rem * var(--ui-scale, 1));
    color: var(--on-stage-soft, #94a3b8);
    margin: 0;
    line-height: 1.4;
  }

  .error-desc {
    font-size: calc(0.92rem * var(--ui-scale, 1));
    color: color-mix(in srgb, var(--on-stage) 85%, transparent);
    margin: 0;
    line-height: 1.45;
  }

  .reassurance {
    font-size: calc(0.8rem * var(--ui-scale, 1));
    color: var(--on-stage-soft, #94a3b8);
    margin: var(--space-1) 0 0 0;
  }

  .tag-pill {
    margin-top: var(--space-1);
    font-size: calc(0.75rem * var(--ui-scale, 1));
    padding: 3px 10px;
    border-radius: var(--radius-pill, 9999px);
    background: color-mix(in srgb, var(--on-stage, #ffffff) 10%, transparent);
    color: var(--on-stage-soft, #94a3b8);
    font-family: ui-monospace, monospace;
    letter-spacing: 0.04em;
  }

  .tag-pill.success {
    background: rgba(34, 197, 94, 0.12);
    color: #86efac;
  }

  .diag-code {
    margin-top: var(--space-1);
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid color-mix(in srgb, var(--on-stage) 12%, transparent);
    font-size: calc(0.75rem * var(--ui-scale, 1));
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--on-stage-soft, #94a3b8);
  }

  .diag-code span {
    font-size: 0.7rem;
    opacity: 0.7;
    font-weight: 600;
  }

  .diag-code code {
    font-family: ui-monospace, monospace;
    color: #fbbf24;
    font-weight: 500;
  }

  .action-btn {
    margin-top: var(--space-3);
    padding: 8px 18px;
    border-radius: var(--radius-pill, 9999px);
    border: 1px solid color-mix(in srgb, var(--on-stage) 16%, transparent);
    background: color-mix(in srgb, var(--on-stage) 10%, transparent);
    color: var(--on-stage, #ffffff);
    font-size: calc(0.85rem * var(--ui-scale, 1));
    font-weight: 500;
    cursor: pointer;
    transition: background var(--dur-fast, 150ms) ease;
  }

  .action-btn:hover {
    background: color-mix(in srgb, var(--on-stage) 18%, transparent);
  }
</style>
