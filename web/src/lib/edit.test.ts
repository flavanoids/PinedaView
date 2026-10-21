// SPDX-License-Identifier: Apache-2.0
import { beforeEach, describe, expect, it } from "vitest";

import {
  cancelEdit,
  edit,
  enterEdit,
  fullStack,
  moveCard,
} from "./edit.svelte";

beforeEach(() => cancelEdit());

describe("layout edit state", () => {
  it("takes a working copy of the body on enter", () => {
    enterEdit("weather", ["clock", "moon", "phrase"]);
    expect(edit.active).toBe(true);
    expect(edit.stack).toEqual(["clock", "moon", "phrase"]);
    expect(fullStack()).toEqual(["weather", "clock", "moon", "phrase"]);
  });

  it("reorders with moveCard", () => {
    enterEdit(null, ["a", "b", "c", "d"]);
    moveCard(0, 2);
    expect(edit.stack).toEqual(["b", "c", "a", "d"]);
    moveCard(3, 0);
    expect(edit.stack).toEqual(["d", "b", "c", "a"]);
  });

  it("ignores out-of-range moves", () => {
    enterEdit(null, ["a", "b"]);
    moveCard(0, 5);
    moveCard(-1, 0);
    expect(edit.stack).toEqual(["a", "b"]);
  });

  it("clears on cancel", () => {
    enterEdit("x", ["y"]);
    cancelEdit();
    expect(edit.active).toBe(false);
    expect(edit.stack).toEqual([]);
  });
});
