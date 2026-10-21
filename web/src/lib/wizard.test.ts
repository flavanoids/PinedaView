// SPDX-License-Identifier: Apache-2.0
import { beforeEach, describe, expect, it } from "vitest";

import {
  back,
  currentStep,
  isLast,
  next,
  reset,
  STEPS,
  wizard,
} from "./wizard.svelte";

beforeEach(() => {
  try {
    localStorage.clear();
  } catch {
    /* jsdom */
  }
  reset();
});

describe("wizard navigation", () => {
  it("starts at welcome and walks forward to invite", () => {
    expect(currentStep()).toBe("welcome");
    for (let i = 1; i < STEPS.length; i += 1) next();
    expect(currentStep()).toBe("invite");
    expect(isLast()).toBe(true);
  });

  it("clamps at both ends", () => {
    back();
    expect(wizard.index).toBe(0);
    for (let i = 0; i < 20; i += 1) next();
    expect(wizard.index).toBe(STEPS.length - 1);
  });

  it("persists progress and restores it", () => {
    next();
    next();
    expect(wizard.index).toBe(2);
    const raw = localStorage.getItem("pineda.wizard");
    expect(raw).toContain('"index":2');
  });

  it("reset clears the draft and returns to step one", () => {
    next();
    wizard.draft.device_name = "Kitchen";
    reset();
    expect(wizard.index).toBe(0);
    expect(wizard.draft.device_name).toBe("Screen");
    expect(localStorage.getItem("pineda.wizard")).toBeNull();
  });
});
