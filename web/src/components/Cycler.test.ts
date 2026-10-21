// SPDX-License-Identifier: Apache-2.0
import { render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import CyclerHarness from "./Cycler.harness.svelte";

describe("Cycler", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("stacks two crossfade layers and one dot per item", () => {
    const { container } = render(CyclerHarness, {
      items: ["a", "b", "c", "d"],
    });
    expect(container.querySelectorAll(".layer")).toHaveLength(2);
    expect(container.querySelectorAll(".dot")).toHaveLength(4);
    // Both layers start on item 0; exactly one is on top.
    expect(container.querySelectorAll(".layer.show")).toHaveLength(1);
    expect(container.querySelector(".dot.on")?.getAttribute("data-i")).toBe(
      "0",
    );
  });

  it("advances the shown item and active dot on each interval", async () => {
    const { container } = render(CyclerHarness, {
      items: ["a", "b", "c"],
    });
    const shownItem = (): string | null | undefined =>
      container.querySelector(".layer.show .item")?.getAttribute("data-i");

    expect(shownItem()).toBe("0");
    await vi.advanceTimersByTimeAsync(1000);
    expect(shownItem()).toBe("1");
    expect(container.querySelector(".dot.on")?.getAttribute("data-i")).toBe(
      "1",
    );
    await vi.advanceTimersByTimeAsync(1000);
    expect(shownItem()).toBe("2");
    await vi.advanceTimersByTimeAsync(1000);
    expect(shownItem()).toBe("0"); // wraps
  });

  it("does not rotate or draw dots for a single item", async () => {
    const { container } = render(CyclerHarness, {
      items: ["a"],
    });
    expect(container.querySelectorAll(".dot")).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(5000);
    expect(
      container.querySelector(".layer.show .item")?.getAttribute("data-i"),
    ).toBe("0");
  });

  it("keeps rotating when a view refresh recomputes the same count", async () => {
    // The feed pushes a fresh view model every few seconds; each push
    // re-evaluates the parent's `facts.length` with a new array identity.
    // The rotation must ride those out — not restart at item 0, or no item
    // ever outlives the push interval.
    const { container, rerender } = render(CyclerHarness, {
      items: ["a", "b", "c"],
    });
    const shownItem = (): string | null | undefined =>
      container.querySelector(".layer.show .item")?.getAttribute("data-i");

    await vi.advanceTimersByTimeAsync(1000);
    expect(shownItem()).toBe("1");

    // A push arrives: same three items, brand-new array object.
    await rerender({ items: ["a", "b", "c"] });
    expect(shownItem()).toBe("1"); // still showing item 1, not reset

    await vi.advanceTimersByTimeAsync(1000);
    expect(shownItem()).toBe("2"); // continued, not restarted
  });
});
