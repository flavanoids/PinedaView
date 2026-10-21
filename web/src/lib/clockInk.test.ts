// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";
import { photoInks } from "./clockInk";

describe("photoInks", () => {
  it("takes the most vivid colour and its opposite", () => {
    const inks = photoInks(null, ["#334455", "#08875b", "#cebfae"]);
    expect(inks.main).toBe("#3ef7b7");
    expect(inks.opposite).toBe("#ff337a");
    expect(inks.mesh).toHaveLength(4);
    expect(inks.mesh[3]).toBe(inks.opposite);
  });

  it("lets a chosen tint win over the photo", () => {
    expect(photoInks("#ff0000", ["#08875b"]).main).toBe("#f73e3e");
  });

  it("keeps black and white photos soft", () => {
    const inks = photoInks(null, ["#111111", "#eeeeee"]);
    expect(inks.main).toBe("#bae1f7");
  });

  it("falls back without colours", () => {
    expect(photoInks(undefined, undefined).main).toMatch(/^#[0-9a-f]{6}$/);
  });
});
