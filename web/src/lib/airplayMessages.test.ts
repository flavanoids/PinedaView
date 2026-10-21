// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { AIRPLAY_IDLE_MESSAGES, idleAirplayMessage } from "./airplayMessages";

describe("idleAirplayMessage", () => {
  it("picks a message from the pool", () => {
    expect(AIRPLAY_IDLE_MESSAGES).toContain(
      idleAirplayMessage(new Date("2026-09-17T12:00:00Z")),
    );
  });

  it("is stable within the same calendar day", () => {
    const morning = idleAirplayMessage(new Date("2026-09-17T00:05:00Z"));
    const night = idleAirplayMessage(new Date("2026-09-17T23:55:00Z"));
    expect(morning).toBe(night);
  });

  it("changes on the next day and loops after the pool length", () => {
    const day0 = idleAirplayMessage(new Date("2026-09-17T00:00:00Z"));
    const day1 = idleAirplayMessage(new Date("2026-09-18T00:00:00Z"));
    expect(day1).not.toBe(day0);

    const cycled = idleAirplayMessage(
      new Date(
        new Date("2026-09-17T00:00:00Z").getTime() +
          AIRPLAY_IDLE_MESSAGES.length * 86_400_000,
      ),
    );
    expect(cycled).toBe(day0);
  });
});
