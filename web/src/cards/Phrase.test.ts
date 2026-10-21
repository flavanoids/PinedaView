// SPDX-License-Identifier: Apache-2.0
import { render } from "@testing-library/svelte";
import type { ViewModel } from "@pinedaview/protocol";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Phrase from "./Phrase.svelte";

function viewWith(word: unknown): ViewModel {
  return {
    version: "v0",
    device_id: "d",
    cards: [],
    stale_stores: [],
    data: { dailyContent: { word } },
  } as unknown as ViewModel;
}

const SPANISH_PHRASE = {
  english: "Do me a solid",
  literal: "make me the stop",
  note: "hacer el paro (MX) = to do someone a favor",
  languages: [
    {
      lang: "Spanish",
      code: "es",
      text: "Hazme el paro",
      pron: "AHS-meh el PAH-roh",
    },
  ],
};

describe("Phrase card", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // jsdom has no ResizeObserver; the phrase's fitText only needs it to exist.
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows only the term and its English", () => {
    const { getAllByText, container } = render(Phrase, {
      view: viewWith(SPANISH_PHRASE),
      stale: false,
      hero: false,
    });
    // Cycler renders two crossfade layers, so each string appears twice.
    expect(getAllByText("Hazme el paro").length).toBeGreaterThan(0);
    expect(container.textContent).toContain("Do me a solid");
    expect(container.textContent).not.toContain("AHS-meh el PAH-roh");
    expect(container.textContent).not.toContain("Spanish");
  });

  it("never flips to the gloss or note", async () => {
    const { container } = render(Phrase, {
      view: viewWith(SPANISH_PHRASE),
      stale: false,
      hero: false,
    });
    await vi.advanceTimersByTimeAsync(20_000);
    expect(container.querySelector(".flip")).toBeNull();
    expect(container.textContent).not.toContain("make me the stop");
    expect(container.textContent).not.toContain("hacer el paro");
  });
});
