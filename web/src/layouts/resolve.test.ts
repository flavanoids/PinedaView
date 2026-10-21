// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { getLayout, resolveTier } from "./resolve";

const layout = getLayout("wide");

describe("getLayout", () => {
  it("maps the server's layout id, with a fallback", () => {
    expect(getLayout("wide_grid").id).toBe("wide");
    expect(getLayout("does-not-exist").id).toBe("wide");
  });
  it("resolves square and material", () => {
    expect(getLayout("square_grid").id).toBe("square");
    expect(getLayout("material").id).toBe("material");
  });
});

describe("resolveTier for other layouts", () => {
  it("square goes 2-up on a phone", () => {
    expect(resolveTier(getLayout("square"), 400).columns).toBe("1fr 1fr");
  });
  it("material is single-column on a phone", () => {
    expect(resolveTier(getLayout("material"), 400).columns).toBe("1fr");
  });
});

describe("resolveTier", () => {
  it("picks the compact tier on a narrow screen", () => {
    expect(resolveTier(layout, 400).id).toBe("compact");
    expect(resolveTier(layout, 640).id).toBe("compact");
  });
  it("picks an intermediate tier on a mid-size tablet", () => {
    expect(resolveTier(layout, 900).id).toBe("mid");
    expect(resolveTier(layout, 900).columns).toBe("repeat(2, minmax(0, 1fr))");
  });
  it("picks the wide tier on a large display", () => {
    expect(resolveTier(layout, 1400).id).toBe("wide");
    expect(resolveTier(layout, 2000).id).toBe("wide");
  });
});
