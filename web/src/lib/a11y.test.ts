// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it } from "vitest";

import { a11y, initA11y, setA11y } from "./a11y.svelte";

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-reduce-transparency");
  document.documentElement.removeAttribute("data-high-contrast");
  document.documentElement.removeAttribute("data-large-text");
});

describe("a11y preferences", () => {
  it("defaults to everything off and no attributes", () => {
    initA11y();
    expect(a11y.reduceTransparency).toBe(false);
    expect(
      document.documentElement.hasAttribute("data-reduce-transparency"),
    ).toBe(false);
  });

  it("stamps an attribute and persists the choice", () => {
    setA11y("highContrast", true);
    expect(document.documentElement.hasAttribute("data-high-contrast")).toBe(
      true,
    );

    a11y.highContrast = false; // simulate a fresh module
    initA11y();
    expect(a11y.highContrast).toBe(true);
    expect(document.documentElement.hasAttribute("data-high-contrast")).toBe(
      true,
    );
  });
});
