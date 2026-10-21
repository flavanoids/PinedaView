// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { remaining } from "./time.svelte";

describe("remaining", () => {
  const from = new Date("2026-08-28T07:00:00Z");

  it("counts down to a future target", () => {
    const left = remaining("2026-08-28T07:03:30Z", from);
    expect(left).toEqual({
      minutes: 3,
      seconds: 30,
      totalSeconds: 210,
      done: false,
    });
  });

  it("is done at or past the target", () => {
    expect(remaining("2026-08-28T06:59:00Z", from).done).toBe(true);
    expect(remaining("2026-08-28T07:00:00Z", from).done).toBe(true);
  });

  it("is done for an unparseable target", () => {
    expect(remaining("nonsense", from).done).toBe(true);
  });
});
