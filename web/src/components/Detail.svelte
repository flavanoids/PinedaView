<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { ViewModel } from "@pinedaview/protocol";

  import { cardComponent } from "../cards";
  import { modal } from "../lib/modal";
  import { motion } from "../lib/tier.svelte";
  import CloseIcon from "./CloseIcon.svelte";

  interface Props {
    view: ViewModel;
    cardId: string;
    onClose: () => void;
  }
  let { view, cardId, onClose }: Props = $props();

  const CardView = $derived(cardComponent(cardId));
  // "moon-climate" → "Moon climate", for the dialog's spoken name.
  const title = $derived(
    cardId.replace(/-/g, " ").replace(/^./, (m) => m.toUpperCase()),
  );

  let panelEl = $state<HTMLElement>();
  let backdropEl = $state<HTMLElement>();
  let closing = $state(false);

  function requestClose(): void {
    if (closing) return;
    if (motion.reduced || motion.tier === "lite" || !panelEl || !backdropEl) {
      onClose();
      return;
    }
    closing = true;
    const sourceEl = document.querySelector<HTMLElement>(
      `[data-cell="${cardId}"]`,
    );
    if (sourceEl) {
      const from = panelEl.getBoundingClientRect();
      const to = sourceEl.getBoundingClientRect();
      const dx = to.left - from.left;
      const dy = to.top - from.top;
      const sx = to.width / Math.max(1, from.width);
      const sy = to.height / Math.max(1, from.height);

      backdropEl.animate([{ opacity: 1 }, { opacity: 0 }], {
        duration: 200,
        easing: "ease-in",
        fill: "forwards",
      });
      const anim = panelEl.animate(
        [
          { transformOrigin: "0 0", transform: "none", opacity: 1 },
          {
            transformOrigin: "0 0",
            transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
            opacity: 0.1,
          },
        ],
        {
          duration: 220,
          easing: "cubic-bezier(0.4, 0, 1, 1)",
          fill: "forwards",
        },
      );
      anim.onfinish = () => onClose();
    } else {
      const anim = panelEl.animate(
        [
          { transform: "none", opacity: 1 },
          { transform: "scale(0.96)", opacity: 0 },
        ],
        { duration: 180, easing: "ease-in", fill: "forwards" },
      );
      backdropEl.animate([{ opacity: 1 }, { opacity: 0 }], {
        duration: 180,
        fill: "forwards",
      });
      anim.onfinish = () => onClose();
    }
  }

  $effect(() => {
    if (closing || !panelEl || !backdropEl) return;
    if (motion.reduced || motion.tier === "lite") {
      backdropEl.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150 });
      panelEl.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150 });
      return;
    }
    const sourceEl = document.querySelector<HTMLElement>(
      `[data-cell="${cardId}"]`,
    );
    backdropEl.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 260,
      easing: "ease-out",
    });
    if (sourceEl) {
      const to = panelEl.getBoundingClientRect();
      const from = sourceEl.getBoundingClientRect();
      const dx = from.left - to.left;
      const dy = from.top - to.top;
      const sx = from.width / Math.max(1, to.width);
      const sy = from.height / Math.max(1, to.height);

      panelEl.animate(
        [
          {
            transformOrigin: "0 0",
            transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
            opacity: 0.8,
          },
          { transformOrigin: "0 0", transform: "none", opacity: 1 },
        ],
        {
          duration: 340,
          easing: "cubic-bezier(0.16, 1, 0.3, 1)",
        },
      );
    } else {
      panelEl.animate(
        [
          { transform: "scale(0.92) translateY(20px)", opacity: 0 },
          { transform: "none", opacity: 1 },
        ],
        {
          duration: 300,
          easing: "cubic-bezier(0.16, 1, 0.3, 1)",
        },
      );
    }
  });
</script>

<div class="scrim" use:modal={{ onClose: requestClose }}>
  <button
    type="button"
    class="backdrop"
    bind:this={backdropEl}
    tabindex="-1"
    aria-label="Close {title}"
    onclick={requestClose}
  ></button>

  <div
    class="panel"
    bind:this={panelEl}
    role="dialog"
    aria-modal="true"
    aria-label="{title} details"
    tabindex="-1"
  >
    <button class="close" onclick={requestClose} aria-label="Close"
      ><CloseIcon /></button
    >
    <CardView {view} stale={false} hero={true} id={cardId} />
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: clamp(var(--space-3), 5vw, var(--space-5))
      calc(clamp(var(--space-3), 5vw, var(--space-5)) + var(--frame-x, 0px));
    z-index: 20;
  }
  .backdrop {
    position: absolute;
    inset: 0;
    border: none;
    padding: 0;
    background: color-mix(in srgb, var(--stage) 78%, black);
    backdrop-filter: blur(var(--card-blur));
    cursor: pointer;
  }
  .panel {
    position: relative;
    width: min(680px, 100%);
    height: min(80dvh, 560px);
    display: flex;
  }
  .panel > :global(*) {
    flex: 1;
  }
  .close {
    position: absolute;
    top: calc(-1 * var(--space-5));
    right: 0;
    width: var(--icon-tap);
    height: var(--icon-tap);
    display: grid;
    place-items: center;
    border: none;
    border-radius: 50%;
    background: color-mix(in srgb, var(--on-stage) 12%, transparent);
    color: var(--on-stage);
    font-size: 1.1rem;
    cursor: pointer;
  }
</style>
