// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { updatedAgo } from "./ago";

describe("updatedAgo", () => {
  const now = Date.parse("2026-10-12T12:00:00Z");
  const at = (min: number) => new Date(now - min * 60_000).toISOString();

  it("says minutes, then hours, then days", () => {
    expect(updatedAgo(at(0), now)).toBe("Updated just now");
    expect(updatedAgo(at(25), now)).toBe("Updated 25 min ago");
    expect(updatedAgo(at(180), now)).toBe("Updated 3 hr ago");
    expect(updatedAgo(at(26 * 60), now)).toBe("Updated yesterday");
    expect(updatedAgo(at(72 * 60), now)).toBe("Updated 3 days ago");
  });

  it("copes with a bad timestamp", () => {
    expect(updatedAgo("nope", now)).toBe("Not updated lately");
  });
});
