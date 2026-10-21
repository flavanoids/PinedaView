// SPDX-License-Identifier: Apache-2.0
/**
 * `use:modal` — turns an element into an accessible modal container:
 *
 * - moves focus inside on mount (the `[role="dialog"]` panel, else the first
 *   focusable), and restores it to the trigger on unmount
 * - keeps Tab / Shift+Tab inside the modal
 * - closes on Escape
 * - marks every sibling element `inert` so the background can't be reached by
 *   keyboard, pointer, or a screen reader's virtual cursor
 *
 * Apply it to the outermost node of the modal (the backdrop wrapper).
 */
const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export function modal(
  node: HTMLElement,
  options: { onClose: () => void },
): { update: (o: { onClose: () => void }) => void; destroy: () => void } {
  let opts = options;
  const trigger = document.activeElement as HTMLElement | null;

  const siblings = [...(node.parentElement?.children ?? [])].filter(
    (el): el is HTMLElement => el instanceof HTMLElement && el !== node,
  );
  const alreadyInert = siblings.map((el) => el.hasAttribute("inert"));
  siblings.forEach((el) => el.setAttribute("inert", ""));

  const focusable = (): HTMLElement[] =>
    [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
      (el) =>
        !el.closest("[hidden],[inert]") &&
        el.getAttribute("aria-hidden") !== "true",
    );

  (
    node.querySelector<HTMLElement>('[role="dialog"]') ?? focusable()[0]
  )?.focus();

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.stopPropagation();
      opts.onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const els = focusable();
    const first = els[0];
    const last = els[els.length - 1];
    if (!first || !last) {
      event.preventDefault();
      return;
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  node.addEventListener("keydown", onKeydown);

  return {
    update(next: { onClose: () => void }) {
      opts = next;
    },
    destroy() {
      node.removeEventListener("keydown", onKeydown);
      siblings.forEach((el, i) => {
        if (!alreadyInert[i]) el.removeAttribute("inert");
      });
      trigger?.focus?.();
    },
  };
}
