// SPDX-License-Identifier: Apache-2.0
import { mount } from "svelte";

import App from "./App.svelte";
import { initPlatform } from "./lib/platform.svelte";
import "./styles/base.css";

initPlatform();

const target = document.getElementById("app");
if (!target) {
  throw new Error("mount target #app is missing from index.html");
}

// /layout is the phone-side layout builder (linked from the QR menu). It must
// not run the dashboard, which would pair the phone as a screen. It loads
// on its own, so a screen never parses the builder.
if (location.pathname === "/layout") {
  void import("./builder/LayoutBuilder.svelte").then(({ default: Builder }) =>
    mount(Builder, { target }),
  );
} else {
  mount(App, { target });
}
