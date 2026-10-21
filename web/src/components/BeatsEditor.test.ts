// SPDX-License-Identifier: Apache-2.0
import { fireEvent, render } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";

import BeatsEditor from "./BeatsEditor.svelte";

const US = {
  name: "US",
  enabled: true,
  weight: 1,
  maxAgeHours: 24,
  sources: ["npr-politics"],
  keywords: ["AOC", "ICE"],
  exclude: [],
};
const PROPS = {
  beats: [US],
  sources: ["npr-politics", "bbc-us"],
  labels: { "npr-politics": "NPR · Politics", "bbc-us": "BBC · US & Canada" },
};

describe("Beats editor", () => {
  it("adds a feed to a beat by its label", async () => {
    const onsave = vi.fn();
    const { getByLabelText } = render(BeatsEditor, { ...PROPS, onsave });
    await fireEvent.click(getByLabelText("BBC · US & Canada"));
    expect(onsave).toHaveBeenCalledWith([
      { ...US, sources: ["npr-politics", "bbc-us"] },
    ]);
  });

  it("saves topics as a list, split on commas and new lines", async () => {
    const onsave = vi.fn();
    const { getByLabelText } = render(BeatsEditor, { ...PROPS, onsave });
    const topics = getByLabelText("Topics") as HTMLTextAreaElement;
    topics.value = "AOC, midterm*\n ICE ,";
    await fireEvent.change(topics);
    expect(onsave).toHaveBeenCalledWith([
      { ...US, keywords: ["AOC", "midterm*", "ICE"] },
    ]);
  });

  it("keeps other feed addresses alongside the chosen outlets", async () => {
    const onsave = vi.fn();
    const { getByLabelText } = render(BeatsEditor, { ...PROPS, onsave });
    const feeds = getByLabelText(/Other RSS feeds/) as HTMLTextAreaElement;
    feeds.value = "https://my.town/feed\nnot-a-feed";
    await fireEvent.change(feeds);
    expect(onsave).toHaveBeenCalledWith([
      { ...US, sources: ["npr-politics", "https://my.town/feed"] },
    ]);
  });

  it("adds and removes beats", async () => {
    const onsave = vi.fn();
    const { getByText } = render(BeatsEditor, { ...PROPS, onsave });
    await fireEvent.click(getByText("Add a beat"));
    expect(onsave.mock.calls[0]?.[0]).toHaveLength(2);
    await fireEvent.click(getByText("Remove US"));
    expect(onsave).toHaveBeenLastCalledWith([]);
  });
});
