// SPDX-License-Identifier: Apache-2.0
import { afterEach, describe, expect, it, vi } from "vitest";

import { modal } from "./modal";

function setup(): {
  root: HTMLElement;
  sibling: HTMLElement;
  first: HTMLButtonElement;
  last: HTMLButtonElement;
} {
  document.body.innerHTML = "";
  const sibling = document.createElement("div");
  const trigger = document.createElement("button");
  const root = document.createElement("div");
  const dialog = document.createElement("div");
  dialog.setAttribute("role", "dialog");
  dialog.tabIndex = -1;
  const first = document.createElement("button");
  first.textContent = "one";
  const last = document.createElement("button");
  last.textContent = "two";
  dialog.append(first, last);
  root.append(dialog);
  document.body.append(sibling, trigger, root);
  trigger.focus();
  return { root, sibling, first, last };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("modal action", () => {
  it("inerts siblings while open and restores them on destroy", () => {
    const { root, sibling } = setup();
    const handle = modal(root, { onClose: vi.fn() });
    expect(sibling.hasAttribute("inert")).toBe(true);
    handle.destroy();
    expect(sibling.hasAttribute("inert")).toBe(false);
  });

  it("moves focus in on open and back to the trigger on close", () => {
    const { root } = setup();
    const trigger = document.activeElement;
    const handle = modal(root, { onClose: vi.fn() });
    expect(document.activeElement?.getAttribute("role")).toBe("dialog");
    handle.destroy();
    expect(document.activeElement).toBe(trigger);
  });

  it("closes on Escape", () => {
    const { root } = setup();
    const onClose = vi.fn();
    const handle = modal(root, { onClose });
    root.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    expect(onClose).toHaveBeenCalledOnce();
    handle.destroy();
  });

  it("wraps Tab from the last focusable to the first", () => {
    const { root, first, last } = setup();
    const handle = modal(root, { onClose: vi.fn() });
    last.focus();
    const event = new KeyboardEvent("keydown", { key: "Tab", bubbles: true });
    const prevented = vi.spyOn(event, "preventDefault");
    root.dispatchEvent(event);
    expect(prevented).toHaveBeenCalled();
    expect(document.activeElement).toBe(first);
    handle.destroy();
  });
});
