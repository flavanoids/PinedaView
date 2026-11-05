// SPDX-License-Identifier: Apache-2.0
import { render } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";

import UpdateOverlay from "./UpdateOverlay.svelte";

describe("UpdateOverlay", () => {
  it("renders updating spinner with status message", () => {
    const { container } = render(UpdateOverlay, {
      status: {
        state: "updating",
        step: "building_web",
        message: "Compiling display assets…",
        current_version: "1.0.0",
        current_commit: "abc1234",
        target_version: "1.0.1",
        target_commit: "def5678",
      },
    });

    expect(container.querySelector(".spinner")).toBeTruthy();
    expect(container.querySelector(".title")?.textContent).toContain(
      "Updating PinedaDisplay",
    );
    expect(container.querySelector(".subtitle")?.textContent).toContain(
      "Compiling display assets…",
    );
    expect(container.querySelector(".tag-pill")?.textContent).toContain(
      "v1.0.1 • def5678",
    );
  });

  it("renders confirmation badge on success", () => {
    const { container } = render(UpdateOverlay, {
      status: {
        state: "success",
        message: "Updated successfully",
        current_version: "1.0.1",
        current_commit: "def5678",
        target_version: "1.0.1",
        target_commit: "def5678",
      },
    });

    expect(container.querySelector(".icon-bubble.success")).toBeTruthy();
    expect(container.querySelector(".title")?.textContent).toContain(
      "Update Complete",
    );
    expect(container.querySelector(".subtitle")?.textContent).toContain(
      "Updated successfully",
    );
    expect(container.querySelector(".action-btn")?.textContent).toContain(
      "Return to Display",
    );
  });

  it("renders device-grade diagnostic error card on failure", () => {
    const { container } = render(UpdateOverlay, {
      status: {
        state: "failed",
        step: "preflight",
        message: "GitHub authentication failed",
        error_code: "ERR_AUTH_REJECTED",
        current_version: "1.0.0",
        current_commit: "abc1234",
      },
    });

    expect(container.querySelector(".icon-bubble.alert")).toBeTruthy();
    expect(container.querySelector(".title")?.textContent).toContain(
      "Update Incomplete",
    );
    expect(container.querySelector(".error-desc")?.textContent).toContain(
      "Unable to access the private GitHub repository",
    );
    expect(container.querySelector(".diag-code code")?.textContent).toContain(
      "ERR_AUTH_REJECTED",
    );
    expect(container.querySelector(".reassurance")?.textContent).toContain(
      "Display safely restored to previous release.",
    );
    expect(container.querySelector(".action-btn")?.textContent).toContain(
      "Dismiss",
    );
  });
});
