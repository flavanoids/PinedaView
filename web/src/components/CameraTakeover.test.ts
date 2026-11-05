// SPDX-License-Identifier: Apache-2.0
import type { components } from "@pinedaview/protocol";
import { render } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";

import CameraTakeover from "./CameraTakeover.svelte";

type Takeover = components["schemas"]["Takeover"];

describe("CameraTakeover", () => {
  beforeEach(() => {
    window.HTMLMediaElement.prototype.play = () => Promise.resolve();
    window.HTMLMediaElement.prototype.load = () => {};
    if (!Element.prototype.animate) {
      Element.prototype.animate = (() => ({
        cancel: () => {},
        finish: () => {},
        pause: () => {},
        play: () => {},
        reverse: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
      })) as unknown as typeof Element.prototype.animate;
    }
  });
  it("renders single full-screen camera when no pip_camera is configured", () => {
    const takeover: Takeover = {
      card: {
        kind: "camera",
        camera: "front_door",
        title: "Front door",
        caption: "",
        pip_title: "",
      },
      shown_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 30_000).toISOString(),
    };

    const { container } = render(CameraTakeover, { takeover });

    expect(container.querySelector(".camera")).toBeTruthy();
    expect(container.querySelector(".tag")?.textContent).toContain(
      "Front door",
    );
    expect(container.querySelector(".load-bar")).toBeTruthy();
    expect(container.querySelector(".pip")).toBeNull();
  });

  it("renders Picture in Picture secondary camera and loading bars when pip_camera is present", () => {
    const takeover: Takeover = {
      card: {
        kind: "camera",
        camera: "front_door",
        title: "Front door",
        caption: "Identifying…",
        pip_camera: "garage",
        pip_title: "Garage",
      },
      shown_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 30_000).toISOString(),
    };

    const { container } = render(CameraTakeover, { takeover });

    expect(container.querySelector(".camera")).toBeTruthy();
    expect(container.querySelector(".tag")?.textContent).toContain(
      "Front door",
    );

    // PiP container
    const pip = container.querySelector(".pip");
    expect(pip).toBeTruthy();
    expect(pip?.querySelector(".pip-tag")?.textContent).toContain("Garage");
    expect(pip?.querySelector(".pip-load-bar")).toBeTruthy();
    expect(pip?.querySelector(".pip-what")?.textContent).toContain(
      "Connecting to garage",
    );

    // Caption
    expect(container.querySelector(".caption")?.textContent).toBe(
      "Identifying…",
    );
  });
});
