// SPDX-License-Identifier: Apache-2.0
export const LONG_PRESS_MS = 500;
export const SWIPE_MIN_PX = 44;
export const TAP_MAX_PX = 12;

export type Gesture =
  | "tap"
  | "doubletap"
  | "longpress"
  | "swipe-left"
  | "swipe-right"
  | "swipe-up"
  | "swipe-down"
  | "none";

export interface Point {
  x: number;
  y: number;
}

/** Classify a single pointer stroke from its start, end and duration. Pure. */
export function classifyGesture(
  start: Point,
  end: Point,
  elapsedMs: number,
): Gesture {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const distance = Math.hypot(dx, dy);

  if (distance <= TAP_MAX_PX) {
    return elapsedMs >= LONG_PRESS_MS ? "longpress" : "tap";
  }
  if (distance < SWIPE_MIN_PX) return "none";
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx > 0 ? "swipe-right" : "swipe-left";
  }
  return dy > 0 ? "swipe-down" : "swipe-up";
}

export interface GestureHandlers {
  onTap?: () => void;
  onDoubleTap?: () => void;
  onLongPress?: () => void;
  onSwipe?: (gesture: Gesture) => void;
}

const DOUBLE_TAP_MS = 280;

/** Svelte action: `<div use:gesture={{ onTap, onLongPress, onSwipe }}>`. */
export function gesture(node: HTMLElement, handlers: GestureHandlers) {
  let current = handlers;
  let start: Point | null = null;
  let startTime = 0;
  let lastTapTime = 0;
  let longPressTimer: ReturnType<typeof setTimeout> | undefined;
  let firedLongPress = false;

  function clearLongPress(): void {
    if (longPressTimer !== undefined) clearTimeout(longPressTimer);
    longPressTimer = undefined;
  }

  function onPointerDown(event: PointerEvent): void {
    start = { x: event.clientX, y: event.clientY };
    startTime = performance.now();
    firedLongPress = false;
    if (current.onLongPress) {
      longPressTimer = setTimeout(() => {
        firedLongPress = true;
        current.onLongPress?.();
      }, LONG_PRESS_MS);
    }
  }

  function onPointerMove(event: PointerEvent): void {
    if (!start) return;
    if (
      Math.hypot(event.clientX - start.x, event.clientY - start.y) > TAP_MAX_PX
    ) {
      clearLongPress();
    }
  }

  function onPointerUp(event: PointerEvent): void {
    clearLongPress();
    if (!start || firedLongPress) {
      start = null;
      return;
    }
    const end = { x: event.clientX, y: event.clientY };
    const g = classifyGesture(start, end, performance.now() - startTime);
    start = null;

    if (g === "tap") {
      const now = performance.now();
      if (current.onDoubleTap && now - lastTapTime < DOUBLE_TAP_MS) {
        lastTapTime = 0;
        current.onDoubleTap();
      } else {
        lastTapTime = now;
        current.onTap?.();
      }
    } else if (g.startsWith("swipe")) {
      current.onSwipe?.(g);
    }
  }

  node.addEventListener("pointerdown", onPointerDown);
  node.addEventListener("pointermove", onPointerMove);
  node.addEventListener("pointerup", onPointerUp);
  node.addEventListener("pointercancel", () => {
    clearLongPress();
    start = null;
  });

  return {
    update(next: GestureHandlers) {
      current = next;
    },
    destroy() {
      clearLongPress();
      node.removeEventListener("pointerdown", onPointerDown);
      node.removeEventListener("pointermove", onPointerMove);
      node.removeEventListener("pointerup", onPointerUp);
    },
  };
}
