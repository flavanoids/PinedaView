# SPDX-License-Identifier: Apache-2.0
"""The phone menu: everything a phone can change about the screen it scanned.

Served at ``/menu`` — what the photo card's QR code points at, with the
kiosk's own device id as ``?screen=`` (older QR codes without it fall back to
the most recently seen screen). A home page — a live miniature of the screen,
quick timer/alarms/clock-only buttons and four ways in — and, picked by the
URL hash, a page each for Alarms (alarms and reminders, kept by Antigua, see
:mod:`pinedaview.alarms`), Themes, Add photos (same public upload as
``/upload``), Settings (cards, night clock, overnight dimming) and Device (health and
restarts behind the ``[control] pin``). Pages slide in and out; Back pops
history so the phone's own back gesture agrees.

The page wears the screen's current theme — stage, ink and card colours come
from ``/api/themes`` — so picking a theme re-dyes the phone too. Headings are
set in Fraunces, the clock's typeface, served from the SPA build at
``/menu/fraunces.woff2``.

Deliberately not part of the SPA, same reasoning as
:mod:`pinedaview.upload_page`: self-contained, no build step, loads at once on
a guest's phone. Interface size and accessibility live in each screen's
``localStorage`` (see ``web/src/lib/display.svelte.ts``), so they'd do nothing
set from here and are left out.
"""

from __future__ import annotations

MENU_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport"
  content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="Display" />
<meta name="theme-color" content="#000000" id="theme-color" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<link rel="manifest" href="/manifest.json" />
<title>Your screen</title>
<script>
  (function() {
    try {
      var m = localStorage.getItem('pineda_menu_dark_mode');
      if (!m) {
        var match = document.cookie.match(/(?:^|; )pineda_menu_dark_mode=([^;]*)/);
        m = match ? decodeURIComponent(match[1]) : 'dark';
      }
      var sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      var isDark = m === 'dark' || (m === 'system' && sysDark);
      document.documentElement.classList.toggle('dark-theme', isDark);
      document.documentElement.classList.toggle('light-theme', !isDark);
      document.documentElement.setAttribute('data-color-mode', m);
    } catch(e) {}
  })();
</script>
<style>
  @font-face {
    font-family: "Fraunces";
    font-weight: 400 700;
    font-display: swap;
    src: url("/menu/fraunces.woff2") format("woff2");
  }
  :root {
    color-scheme: dark;
    --stage: #000;
    --ink: #f4efe5;
    --ink-rgb: 244, 239, 229;
    --accent: #e7a34a;
    --on-card: #f4efe5;
    --screen-stage: #000;
    --screen-ink: #f4efe5;
    --soft: rgba(var(--ink-rgb), 0.65);
    --faint: rgba(var(--ink-rgb), 0.40);
    --wash: rgba(var(--ink-rgb), 0.08);
    --rule: rgba(var(--ink-rgb), 0.12);
    --nav-bg: rgba(10, 12, 16, 0.85);
    --display: "Fraunces", "Iowan Old Style", Georgia, serif;
    --text: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    --dye: 350ms ease;
  }
  :root.light-theme {
    color-scheme: light;
    --stage: #f7f6f2;
    --ink: #1a1918;
    --ink-rgb: 26, 25, 24;
    --soft: rgba(var(--ink-rgb), 0.65);
    --faint: rgba(var(--ink-rgb), 0.40);
    --wash: rgba(var(--ink-rgb), 0.06);
    --rule: rgba(var(--ink-rgb), 0.10);
    --nav-bg: rgba(247, 246, 242, 0.88);
  }
  :root.dark-theme {
    color-scheme: dark;
    --stage: #000000;
    --ink: #f4efe5;
    --ink-rgb: 244, 239, 229;
    --soft: rgba(var(--ink-rgb), 0.65);
    --faint: rgba(var(--ink-rgb), 0.40);
    --wash: rgba(var(--ink-rgb), 0.08);
    --rule: rgba(var(--ink-rgb), 0.12);
    --nav-bg: rgba(10, 12, 16, 0.85);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  [hidden] { display: none !important; }
  body {
    min-height: 100dvh;
    background: var(--stage);
    color: var(--ink);
    font: 1rem/1.45 var(--text);
    -webkit-font-smoothing: antialiased;
    -webkit-tap-highlight-color: transparent;
    transition: background-color var(--dye), color var(--dye);
  }
  button, input, select, textarea { font: inherit; color: inherit; }
  button { cursor: pointer; }
  :focus-visible { outline: 2px solid var(--ink); outline-offset: 3px; border-radius: 6px; }

  main {
    max-width: 34rem;
    margin: 0 auto;
    padding: 0 max(16px, env(safe-area-inset-right))
      calc(64px + max(16px, env(safe-area-inset-bottom))) max(16px, env(safe-area-inset-left));
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
  }

  /* ── Pinned Stage Header ─────────────────────────────────────────── */
  .stage-header {
    position: sticky;
    top: 0;
    z-index: 25;
    background: var(--stage);
    padding-top: max(12px, env(safe-area-inset-top));
    padding-bottom: 12px;
    margin-bottom: 8px;
    border-bottom: 1px solid var(--rule);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    transition: background-color var(--dye);
  }
  .stage-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 4px 10px;
  }
  .screen-meta {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .screen-name {
    font-size: 1.25rem;
    font-weight: 600;
    letter-spacing: -0.015em;
    margin: 0;
  }
  .status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--soft);
    background: var(--wash);
    padding: 2px 8px;
    border-radius: 999px;
  }
  .pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #34c759;
  }
  .dark-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid var(--rule);
    border-radius: 50%;
    background: var(--wash);
    color: var(--ink);
    cursor: pointer;
    font-size: 1.05rem;
    transition: transform 120ms ease, background-color 160ms ease;
  }
  .dark-toggle:active {
    transform: scale(0.92);
  }
  .stage-modes {
    display: flex;
    gap: 8px;
    margin-top: 10px;
  }
  .stage-modes .q {
    min-width: 0;
    flex: 1;
    min-height: 42px;
    font-size: 0.82rem;
    padding: 0 8px;
    gap: 6px;
  }

  /* ── Bottom Tab Bar ─────────────────────────────────────────────── */
  .bottom-tab-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 30;
    background: var(--nav-bg);
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border-top: 1px solid var(--rule);
    display: flex;
    justify-content: space-around;
    align-items: center;
    height: calc(52px + max(12px, env(safe-area-inset-bottom)));
    padding-bottom: max(12px, env(safe-area-inset-bottom));
    padding-left: max(8px, env(safe-area-inset-left));
    padding-right: max(8px, env(safe-area-inset-right));
    max-width: 34rem;
    margin: 0 auto;
  }
  .tab-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    color: var(--soft);
    text-decoration: none;
    font-size: 0.72rem;
    font-weight: 500;
    padding: 4px 0;
    border-radius: 12px;
    transition: color 140ms ease, transform 140ms cubic-bezier(0.34, 1.56, 0.64, 1);
    position: relative;
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .tab-item:active {
    transform: scale(0.90);
  }
  .tab-item svg {
    width: 22px;
    height: 22px;
    transition: transform 160ms cubic-bezier(0.34, 1.56, 0.64, 1), color 140ms ease;
  }
  .tab-item.active {
    color: var(--ink);
    font-weight: 600;
  }
  .tab-item.active svg {
    color: var(--accent);
    transform: scale(1.08);
  }
  .tab-badge {
    position: absolute;
    top: 2px;
    right: 50%;
    margin-right: -16px;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--stage);
    font-size: 0.65rem;
    font-weight: 700;
    line-height: 16px;
    text-align: center;
  }

  /* ── Standalone (Add to Home Screen) styles ──────────────────────── */
  @media all and (display-mode: standalone) {
    body {
      -webkit-user-select: none;
      user-select: none;
    }
    .back {
      display: none !important;
    }
  }

  @media (min-width: 768px) {
    main {
      max-width: 58rem;
    }
    #app {
      display: grid;
      grid-template-columns: 24rem 1fr;
      gap: 28px;
      align-items: start;
    }
    .stage-header {
      position: sticky;
      top: 20px;
      margin-bottom: 0;
    }
    .bottom-tab-bar {
      max-width: 58rem;
    }
  }

  /* ── The miniature screen ─────────────────────────────────────────── */
  .mini {
    margin: 4px 0 0;
    padding: 7px;
    border-radius: 18px;
    background: #050505;
    box-shadow: 0 0 0 1px var(--rule), 0 18px 40px -22px rgba(0, 0, 0, 0.55);
  }
  .mini-stage {
    aspect-ratio: 16 / 9;
    border-radius: 11px;
    overflow: hidden;
    background: var(--screen-stage, var(--stage));
    transition: background-color var(--dye);
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-auto-flow: row dense;
    gap: 3.2%;
    padding: 3.2%;
    position: relative;
  }
  .mini-stage.dim::after {
    content: "";
    position: absolute;
    inset: 0;
    background: #000;
    opacity: var(--dim, 0);
    pointer-events: none;
    transition: opacity 300ms ease;
  }
  .tile {
    border-radius: 7%/11%;
    min-width: 0;
    min-height: 0;
    background: var(--tile, var(--wash));
    background-size: cover;
    background-position: center;
    color: var(--on-card);
    font-size: clamp(6px, 1.9vw, 9px);
    line-height: 1.15;
    padding: 6% 7%;
    overflow: hidden;
    transition: background-color var(--dye), color var(--dye);
    display: flex;
    align-items: flex-end;
  }
  .tile span { opacity: 0.78; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tile.hero { grid-column: span 2; grid-row: span 2; border-radius: 4.5%/8%; }
  .tile.clock { align-items: center; justify-content: center; }
  .tile.clock span {
    opacity: 1;
    font-family: var(--display);
    font-variation-settings: "SOFT" 100, "opsz" 72;
    font-size: clamp(11px, 4.4vw, 21px);
    letter-spacing: -0.02em;
  }
  .tile.hero.clock span { font-size: clamp(22px, 9vw, 44px); }
  .tile.photo span { display: none; }
  .tile.plain { color: var(--screen-ink, var(--ink)); }

  /* The real screen, as a snapshot of the kiosk refreshed every few
     seconds. Fades in over the sketch once the first one arrives. */
  .mini { position: relative; }
  .mini-live {
    position: absolute;
    inset: 7px;
    border-radius: 11px;
    overflow: hidden;
    opacity: 0;
    transition: opacity 500ms ease;
    pointer-events: none;
  }
  .mini-live.on { opacity: 1; }
  .mini-live img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .live {
    position: absolute;
    left: 16px;
    bottom: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 9px 3px 7px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.55);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
  }
  .live::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ff5a4f;
    animation: blink 2s ease-in-out infinite;
  }
  @keyframes blink { 50% { opacity: 0.35; } }

  /* ── Pages: home and the three behind its buttons ─────────────────── */
  .page > h2 { margin: 6px 0 6px; font-size: 2.1rem; }
  .page h2:focus { outline: none; }
  .page h3 { font: 400 1.35rem/1.2 var(--display); margin: 34px 0 6px; }
  .back {
    display: none !important;
  }

  /* Quick access: the things you reach for in passing. */
  .quick { display: flex; gap: 8px; margin-top: 20px; flex-wrap: wrap; }
  .q {
    flex: 1 1 0;
    /* Two to a row (Timer and Alarms), then the three screen modes. */
    min-width: calc(50% - 4px);
    min-height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 0 12px;
    border: 0;
    border-radius: 999px;
    background: var(--wash);
    font-weight: 600;
    font-size: 0.92rem;
    white-space: nowrap;
    touch-action: manipulation;
    transition: background-color 140ms ease, color 140ms ease,
      transform 120ms cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .q:active {
    transform: scale(0.95);
  }
  .q svg { width: 19px; height: 19px; flex: none; }
  .q.mode { min-width: calc(33.33% - 6px); padding: 0 8px; gap: 6px; font-size: 0.86rem; }
  .q[aria-pressed="true"] { background: var(--ink); color: var(--stage); }
  .q .n {
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--stage);
    font-size: 0.75rem;
    line-height: 20px;
    text-align: center;
  }
  .ringing {
    width: 100%;
    min-height: 54px;
    margin-top: 10px;
    border: 0;
    border-radius: 999px;
    background: var(--accent);
    color: var(--stage);
    font-weight: 600;
  }

  /* The four ways in. */
  .hub {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 26px;
  }
  .hub-btn {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: 118px;
    padding: 16px;
    border-radius: 20px;
    background: var(--wash);
    color: var(--ink);
    text-decoration: none;
    transition: transform 120ms ease;
  }
  .hub-btn:active { transform: scale(0.97); }
  .hub-btn svg, .hub-btn .dots { width: 26px; height: 26px; margin-bottom: auto; }
  .hub-btn .t { font: 400 1.3rem/1.15 var(--display); margin-top: 14px; }
  .hub-btn .s { font-size: 0.82rem; color: var(--soft); }
  .hub-btn .dots { display: flex; width: auto; gap: 3px; align-self: flex-start; }
  .hub-btn .dots i { width: 13px; height: 26px; border-radius: 4px; }
  .hub-btn .s.warn { color: var(--ink); font-weight: 600; }

  /* Alarms: everything Antigua has, on or off, then a form sheet. */
  .add-row { display: flex; gap: 8px; margin: 4px 0 18px; }
  .alarms { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rule); }
  .al {
    display: flex;
    align-items: center;
    gap: 14px;
    border-bottom: 1px solid var(--rule);
    animation: pop 240ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  .al .open {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    padding: 12px 0;
    border: 0;
    background: none;
    text-align: left;
  }
  .al .t {
    font: 400 2.1rem/1.1 var(--display);
    font-variation-settings: "SOFT" 100, "opsz" 72;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
  }
  .al .t small { font: 600 0.9rem var(--text); margin-left: 4px; letter-spacing: 0; }
  .al .what { font-weight: 600; font-size: 0.95rem; overflow-wrap: anywhere; }
  .al .d { color: var(--soft); font-size: 0.84rem; }
  .al .t, .al .what, .al .d { transition: opacity 200ms ease; }
  .al.off .t, .al.off .what, .al.off .d { opacity: 0.42; }
  .al-empty { margin: 18px 0 0; color: var(--soft); font-size: 0.9rem; }
  .al-form .field + .field, .al-form .field + input, .al-form input + .field,
  .al-form .days + .field, .al-form .field + .days { margin-top: 18px; }
  .al-form #al-date, .al-form .days { margin-top: 10px; }
  .al-form .al-speak { margin-top: 18px; border-top: 1px solid var(--rule); }
  .days { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
  .day {
    aspect-ratio: 1;
    max-height: 46px;
    border: 0;
    border-radius: 50%;
    background: var(--wash);
    font-weight: 600;
    font-size: 0.85rem;
    transition: background-color 160ms ease, color 160ms ease;
  }
  .day[aria-pressed="true"] { background: var(--ink); color: var(--stage); }

  /* Add photos: one big target, then what's been sent. */
  .drop {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-height: 168px;
    margin-top: 8px;
    padding: 20px;
    border-radius: 20px;
    background: var(--wash);
    box-shadow: inset 0 0 0 1.5px var(--rule);
    text-align: center;
    cursor: pointer;
    transition: transform 120ms ease, opacity 200ms ease;
  }
  .drop:active { transform: scale(0.98); }
  .drop:focus-within { box-shadow: inset 0 0 0 2px var(--ink); }
  .drop svg { width: 34px; height: 34px; margin-bottom: 10px; color: var(--accent); }
  .drop .t { font: 400 1.4rem/1.15 var(--display); }
  .drop .s { font-size: 0.84rem; color: var(--soft); }
  .drop.busy { pointer-events: none; }
  .drop.busy svg { animation: breathe 1.4s ease-in-out infinite; }
  @keyframes breathe { 50% { opacity: 0.35; transform: scale(0.9); } }
  .up-done { min-height: 1.4em; margin: 14px 0 10px; color: var(--soft); font-size: 0.88rem; }
  .up-done:empty { min-height: 0; margin: 0; }
  .photos-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 18px 0 10px;
    gap: 12px;
  }
  .photos-bar h3 {
    margin: 0;
    font: 400 1.25rem/1.2 var(--display);
  }
  .manage-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: 999px;
    border: 1px solid var(--rule);
    background: var(--wash);
    color: var(--ink);
    font: 500 0.85rem/1 system-ui, sans-serif;
    cursor: pointer;
    transition: all 160ms ease;
  }
  .manage-btn:hover {
    background: var(--surface);
    border-color: var(--soft);
  }
  .manage-btn:active {
    transform: scale(0.96);
  }
  .manage-btn.active {
    background: var(--ink);
    color: var(--stage);
    border-color: var(--ink);
  }
  .manage-btn svg {
    width: 14px;
    height: 14px;
  }
  .manage-hint {
    font-size: 0.85rem;
    color: var(--soft);
    margin: -4px 0 12px;
  }
  .up-grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
    gap: 8px;
  }
  .up-grid li {
    position: relative;
    aspect-ratio: 1;
    border-radius: 12px;
    overflow: hidden;
    background: var(--wash);
    animation: pop 260ms cubic-bezier(0.2, 0.8, 0.2, 1);
    transition: transform 160ms ease, box-shadow 160ms ease;
  }
  .up-grid img, .up-grid video { width: 100%; height: 100%; object-fit: cover; display: block; }
  .up-grid .state {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 6px;
    background: rgba(0, 0, 0, 0.5);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 600;
    text-align: center;
    transition: opacity 300ms ease;
  }
  .up-grid li.ok .state { opacity: 0; }
  .up-grid li.err .state { background: rgba(120, 20, 20, 0.72); }
  @keyframes pop { from { transform: scale(0.85); opacity: 0; } }

  .up-grid.manage-mode li {
    cursor: pointer;
  }
  .up-grid.manage-mode li:hover {
    transform: scale(1.02);
    box-shadow: 0 0 0 2px #e53935;
  }
  .up-grid.manage-mode li:active {
    transform: scale(0.97);
  }
  .del-badge {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #e53935;
    color: #fff;
    border: 2px solid rgba(255, 255, 255, 0.95);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    cursor: pointer;
    z-index: 5;
    animation: badge-pop 180ms cubic-bezier(0.18, 0.89, 0.32, 1.28);
    transition: transform 120ms ease, background 120ms ease;
  }
  .del-badge:hover {
    background: #d32f2f;
    transform: scale(1.1);
  }
  .del-badge:active {
    transform: scale(0.9);
  }
  .del-badge svg {
    width: 14px;
    height: 14px;
  }
  @keyframes badge-pop {
    from { transform: scale(0); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }

  .up-grid li.deleting {
    pointer-events: none;
    overflow: visible;
  }
  .up-grid li.deleting img,
  .up-grid li.deleting video {
    animation: photo-crumple 480ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }
  @keyframes photo-crumple {
    0% {
      transform: scale(1);
      opacity: 1;
      filter: none;
    }
    40% {
      transform: scale(0.6) translateY(12px) rotate(8deg);
      opacity: 0.8;
      filter: blur(1px);
    }
    100% {
      transform: scale(0.12) translateY(34px) rotate(16deg);
      opacity: 0;
      filter: blur(4px);
    }
  }

  .trash-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    pointer-events: none;
  }
  .trash-anim {
    position: relative;
    width: 44px;
    height: 48px;
    display: flex;
    flex-direction: column;
    align-items: center;
    animation: trash-bounce 640ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
  }
  .trash-lid {
    width: 36px;
    height: 12px;
    color: #e53935;
    transform-origin: 4px 10px;
    animation: lid-flip 520ms cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  }
  .trash-lid svg {
    width: 100%;
    height: 100%;
    display: block;
  }
  .trash-body {
    width: 34px;
    height: 36px;
    margin-top: -3px;
    color: #e53935;
  }
  .trash-body svg {
    width: 100%;
    height: 100%;
    display: block;
  }

  @keyframes lid-flip {
    0% {
      transform: rotate(0deg) translate(0, 0);
    }
    22% {
      transform: rotate(-44deg) translate(-4px, -6px);
    }
    65% {
      transform: rotate(-44deg) translate(-4px, -6px);
    }
    85% {
      transform: rotate(4deg) translate(0, 1px);
    }
    100% {
      transform: rotate(0deg) translate(0, 0);
    }
  }

  @keyframes trash-bounce {
    0% {
      transform: scale(0.7);
      opacity: 0;
    }
    20% {
      transform: scale(1.15);
      opacity: 1;
    }
    65% {
      transform: scale(1);
    }
    85% {
      transform: scale(1.1) translateY(-2px);
    }
    100% {
      transform: scale(0.9);
      opacity: 0.95;
    }
  }

  .trash-burst {
    position: absolute;
    inset: -10px;
    pointer-events: none;
  }
  .trash-burst span {
    position: absolute;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #e53935;
    opacity: 0;
    top: 50%;
    left: 50%;
  }
  .trash-burst span:nth-child(1) { animation: burst-1 420ms 260ms ease-out forwards; }
  .trash-burst span:nth-child(2) { animation: burst-2 420ms 260ms ease-out forwards; }
  .trash-burst span:nth-child(3) { animation: burst-3 420ms 260ms ease-out forwards; }
  .trash-burst span:nth-child(4) { animation: burst-4 420ms 260ms ease-out forwards; }

  @keyframes burst-1 {
    from { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    to { transform: translate(-28px, -22px) scale(0); opacity: 0; }
  }
  @keyframes burst-2 {
    from { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    to { transform: translate(22px, -24px) scale(0); opacity: 0; }
  }
  @keyframes burst-3 {
    from { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    to { transform: translate(-22px, 18px) scale(0); opacity: 0; }
  }
  @keyframes burst-4 {
    from { transform: translate(-50%, -50%) scale(1); opacity: 1; }
    to { transform: translate(24px, 16px) scale(0); opacity: 0; }
  }

  .up-grid li.deleted-collapse {
    animation: tile-collapse 280ms ease-in forwards;
  }
  @keyframes tile-collapse {
    0% {
      transform: scale(0.9);
      opacity: 0.8;
      max-width: 100%;
    }
    100% {
      transform: scale(0);
      opacity: 0;
      max-width: 0;
      margin: 0;
      padding: 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .up-grid li.deleting img,
    .up-grid li.deleting video,
    .trash-anim,
    .trash-lid,
    .trash-burst span,
    .up-grid li.deleted-collapse {
      animation: none !important;
      transition: opacity 150ms ease !important;
      opacity: 0 !important;
    }
  }

  /* Device health: plain words first, the numbers after. */
  .stats { margin: 0; border-top: 1px solid var(--rule); }
  .stats > div {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 0;
    border-bottom: 1px solid var(--rule);
  }
  .stats dt { color: var(--soft); }
  .stats dd { margin: 0; text-align: right; }
  .stats dd small { display: block; color: var(--soft); font-size: 0.8rem; }
  .stats .warn dd { font-weight: 600; }
  .stats-note { margin: 8px 0 0; color: var(--soft); font-size: 0.82rem; }

  /* ── Type ─────────────────────────────────────────────────────────── */
  h1, h2, .display {
    font-family: var(--display);
    font-weight: 400;
    font-variation-settings: "SOFT" 100, "WONK" 0;
    letter-spacing: -0.015em;
  }
  h1 {
    margin: 26px 0 4px;
    font-size: 2.45rem;
    line-height: 1.05;
    font-variation-settings: "SOFT" 100, "WONK" 1, "opsz" 144;
  }
  .summary { margin: 0; color: var(--soft); max-width: 42ch; }
  h2 {
    margin: 0 0 4px;
    font-size: 1.5rem;
    line-height: 1.15;
    font-variation-settings: "SOFT" 100, "opsz" 48;
  }
  .lede { margin: 0 0 18px; color: var(--soft); font-size: 0.9rem; }
  h3 {
    margin: 22px 0 10px;
    font-size: 0.95rem;
    font-weight: 600;
  }
  section { padding-top: 44px; }


  /* ── Theme swatches: each one a tiny screen ───────────────────────── */
  .swatches {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
    gap: 18px 12px;
    padding: 0;
    margin: 0;
    list-style: none;
  }
  .swatch {
    width: 100%;
    padding: 0;
    border: 0;
    background: none;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 7px;
    touch-action: manipulation;
  }
  .swatch .scr {
    aspect-ratio: 16 / 10;
    border-radius: 10px;
    padding: 9%;
    display: grid;
    grid-template-columns: 2fr 1fr;
    grid-template-rows: 1fr 1fr;
    gap: 8%;
    box-shadow: 0 0 0 1px var(--rule);
    transition: box-shadow 150ms ease,
      transform 140ms cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .swatch .scr i { border-radius: 3px; display: block; }
  .swatch .scr i:first-child { grid-row: span 2; }
  .swatch .name { font-size: 0.86rem; line-height: 1.2; }
  .swatch[aria-checked="true"] .scr {
    box-shadow: 0 0 0 2px var(--stage), 0 0 0 4px var(--ink);
    transform: scale(1.02);
  }
  .swatch[aria-checked="true"] .name { font-weight: 600; }
  .swatch:active .scr { transform: scale(0.93) !important; }
  /* A swatch you made: Edit sits under its name. */
  .swatches li { display: flex; flex-direction: column; gap: 2px; }
  .swatch-edit {
    align-self: flex-start;
    border: 0;
    background: none;
    padding: 4px 0;
    font-size: 0.8rem;
    color: var(--soft);
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .swatch.make .scr {
    display: grid;
    grid-template: 1fr / 1fr;
    place-items: center;
    background: none;
    box-shadow: inset 0 0 0 1.5px var(--faint);
    border: 0;
  }
  .swatch.make .scr svg { width: 26px; height: 26px; color: var(--soft); }

  /* ── Theme maker ──────────────────────────────────────────────────── */
  .maker-preview {
    position: relative;
    aspect-ratio: 16 / 10;
    border-radius: 16px;
    padding: 5%;
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    grid-template-rows: auto 1fr 1fr;
    gap: 4%;
    margin: 0 0 18px;
    box-shadow: 0 0 0 1px var(--rule);
    transition: background-color 120ms ease;
  }
  .maker-preview .hello {
    grid-column: span 2;
    margin: 0;
    font: 500 1rem/1.1 var(--display);
  }
  .maker-preview .hello i {
    display: inline-block;
    width: 0.5em;
    height: 0.5em;
    margin-left: 0.35em;
    border-radius: 50%;
    vertical-align: 0.1em;
  }
  .maker-preview b {
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 0.78rem;
    font-weight: 600;
    transition: background-color 120ms ease;
  }
  .maker-preview b:first-of-type { grid-row: span 2; }
  .wells { border-top: 1px solid var(--rule); margin: 18px 0 6px; }
  .well {
    display: flex;
    align-items: center;
    gap: 14px;
    min-height: 58px;
    border-bottom: 1px solid var(--rule);
    cursor: pointer;
  }
  .well > span { flex: 1; }
  .well small { display: block; font-size: 0.8rem; color: var(--soft); }
  .well input {
    width: 44px;
    height: 44px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: none;
    cursor: pointer;
    flex: none;
  }
  .well input::-webkit-color-swatch-wrapper { padding: 0; }
  .well input::-webkit-color-swatch {
    border: 0;
    border-radius: 50%;
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.18);
  }
  .well input::-moz-color-swatch { border: 0; border-radius: 50%; }
  .sheet h3 { font: 400 1.2rem/1.2 var(--display); margin: 20px 0 10px; }
  #mk-fonts { margin-bottom: 22px; }
  .maker-note { margin: 12px 0 0; font-size: 0.82rem; color: var(--soft); text-align: center; }
  button.well {
    width: 100%;
    padding: 0;
    border: 0;
    border-bottom: 1px solid var(--rule);
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
  }
  .well .swatch {
    width: 44px;
    height: 44px;
    flex: none;
    border: 0;
    border-radius: 50%;
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.18), 0 0 0 1px var(--rule);
  }
  .well[aria-expanded="true"] .swatch { box-shadow: 0 0 0 2px var(--stage), 0 0 0 4px var(--ink); }
  .well-wheel { padding: 6px 0 14px; border-bottom: 1px solid var(--rule); }

  /* ── Colour wheel ─────────────────────────────────────────────────── */
  .cw-disc {
    position: relative;
    width: min(260px, 100%);
    aspect-ratio: 1;
    margin: 6px auto 16px;
    border-radius: 50%;
    touch-action: none;
    cursor: crosshair;
  }
  .cw-disc canvas { display: block; width: 100%; height: 100%; border-radius: 50%; }
  .cw-dim {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: #000;
    pointer-events: none;
  }
  .cw-knob {
    position: absolute;
    width: 28px;
    height: 28px;
    margin: -14px 0 0 -14px;
    border: 3px solid #fff;
    border-radius: 50%;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35), 0 2px 6px rgba(0, 0, 0, 0.4);
    pointer-events: none;
  }
  .cw-disc:focus-visible { outline: 3px solid var(--ink); outline-offset: 4px; }
  .cw-v {
    appearance: none;
    -webkit-appearance: none;
    display: block;
    width: 100%;
    height: 30px;
    margin: 0 0 14px;
    border-radius: 999px;
    box-shadow: inset 0 0 0 1px var(--rule);
  }
  .cw-v::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 30px;
    height: 30px;
    border: 3px solid #fff;
    border-radius: 50%;
    background: transparent;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35), 0 2px 6px rgba(0, 0, 0, 0.4);
  }
  .cw-v::-moz-range-thumb {
    width: 24px;
    height: 24px;
    border: 3px solid #fff;
    border-radius: 50%;
    background: transparent;
  }
  .cw-row { display: flex; align-items: center; gap: 12px; }
  .cw-row .text-in { flex: 1; font-variant-numeric: tabular-nums; text-transform: uppercase; }
  .cw-out {
    width: 44px;
    height: 44px;
    flex: none;
    border-radius: 12px;
    box-shadow: inset 0 0 0 1px var(--rule);
  }
  .cw-guard { display: flex; align-items: center; gap: 14px; min-height: 58px; margin-top: 8px; }
  .cw-guard > span { flex: 1; }
  .cw-guard small { display: block; font-size: 0.8rem; color: var(--soft); }
  .cw-guard small.low { color: #e0705a; }

  /* ── Photo Clock & Clock Customizer ────────────────────────────────── */
  .clock-preview {
    display: grid;
    place-items: center;
    aspect-ratio: 16 / 10;
    margin: 0 0 6px;
    border-radius: 16px;
    background: #000;
    font-size: 4.6rem;
    font-weight: 300;
    line-height: 1;
    font-variant-numeric: lining-nums proportional-nums;
    box-shadow: 0 0 0 1px var(--rule);
  }
  #ck-fonts { margin-bottom: 4px; }

  /* ── Photo Clock Section in Settings ───────────────────────────────── */
  .photo-clock-sec {
    margin: 14px 0 24px;
    padding: 16px 18px;
    border-radius: 18px;
    background: var(--wash);
    border: 1px solid var(--rule);
  }
  .pc-banner {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 8px;
  }
  .pc-banner-text h3 {
    margin: 0 0 4px;
    font: 400 1.35rem/1.2 var(--display);
  }
  .pc-banner-text .lede {
    margin: 0;
    font-size: 0.86rem;
    color: var(--soft);
  }
  .pc-status-badge {
    flex: none;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: var(--rule);
    color: var(--soft);
  }
  .pc-status-badge.on {
    background: var(--accent);
    color: var(--stage);
  }
  .photo-clock-sec .setting {
    padding: 10px 0 0;
    border-bottom: 0;
  }
  .photo-clock-sec .setting:first-of-type {
    border-top: 0;
  }
  .pc-summary-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid var(--rule);
  }
  .pc-summary-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.88rem;
  }
  .pc-summary-label {
    color: var(--soft);
  }
  .pc-summary-val {
    font-weight: 500;
  }
  .pc-customize-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 44px;
    margin-top: 4px;
    border-radius: 12px;
    background: var(--ink);
    color: var(--stage);
    border: 0;
    font-weight: 600;
    font-size: 0.92rem;
    touch-action: manipulation;
    transition: transform 120ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 120ms ease;
  }
  .pc-customize-btn:active {
    transform: scale(0.96);
    opacity: 0.9;
  }

  .blurb { margin: 14px 0 0; color: var(--soft); font-size: 0.88rem; min-height: 2.5em; }

  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .range-head { display: flex; justify-content: space-between; margin-top: 14px; }
  .range-head output { font-variant-numeric: tabular-nums; opacity: 0.78; }
  input.range { width: 100%; accent-color: var(--accent); }
  .chip {
    border: 0;
    border-radius: 999px;
    padding: 9px 15px;
    background: var(--wash);
    font-size: 0.9rem;
    transition: background-color 140ms ease, color 140ms ease,
      transform 120ms cubic-bezier(0.34, 1.56, 0.64, 1);
    touch-action: manipulation;
  }
  .chip:active { transform: scale(0.93); }
  .chip[aria-checked="true"] { background: var(--ink); color: var(--stage); font-weight: 600; }
  .note { margin: 10px 0 0; color: var(--faint); font-size: 0.82rem; }

  .wall { display: flex; gap: 14px; align-items: center; }
  .wall img {
    width: 96px;
    aspect-ratio: 16 / 10;
    object-fit: cover;
    border-radius: 10px;
    box-shadow: 0 0 0 1px var(--rule);
  }
  .wall .btns { display: flex; gap: 8px; flex-wrap: wrap; }
  .pill {
    display: inline-flex;
    align-items: center;
    min-height: 40px;
    padding: 0 16px;
    border-radius: 999px;
    border: 1px solid var(--rule);
    background: none;
    font-size: 0.9rem;
    font-weight: 500;
  }
  .pill.busy { opacity: 0.5; pointer-events: none; }
  input[type="file"] { position: absolute; width: 1px; height: 1px; opacity: 0; }

  /* ── Card settings: this screen's cards as a grid of chips ─────────── */
  .card-grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
    gap: 8px;
  }
  .card-chip {
    width: 100%;
    min-height: 54px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px 8px 10px;
    border: 0;
    border-radius: 14px;
    background: var(--wash);
    text-align: left;
    touch-action: manipulation;
    transition: transform 120ms cubic-bezier(0.34, 1.56, 0.64, 1),
      background-color 140ms ease;
  }
  .card-chip:active { transform: scale(0.96); }
  .card-chip i {
    flex: none;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12);
  }
  .card-chip span { flex: 1; min-width: 0; line-height: 1.2; }
  /* A chevron, so the chip reads as "opens", not as a checkbox. */
  .card-chip::after {
    content: "";
    flex: none;
    width: 7px;
    height: 7px;
    margin-right: 4px;
    border-top: 1.8px solid var(--faint);
    border-right: 1.8px solid var(--faint);
    transform: rotate(45deg);
    transition: transform 120ms ease, border-color 120ms ease;
  }
  .card-chip:active::after {
    border-color: var(--ink);
    transform: translateX(2px) rotate(45deg);
  }
  .others { margin-top: 18px; }
  .others summary {
    min-height: 44px;
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--soft);
    cursor: pointer;
    list-style: none;
  }
  .others summary::-webkit-details-marker { display: none; }
  .others summary::after {
    content: "";
    width: 6px;
    height: 6px;
    margin: 0 0 3px 4px;
    border-right: 1.6px solid currentColor;
    border-bottom: 1.6px solid currentColor;
    transform: rotate(45deg);
    transition: transform 160ms ease;
  }
  .others[open] summary::after { transform: rotate(225deg); margin-bottom: -1px; }
  .others .card-grid { margin-top: 6px; }
  .others .card-chip { background: none; box-shadow: inset 0 0 0 1px var(--rule); }
  .card-fields { display: flex; flex-direction: column; gap: 16px; margin-bottom: 18px; }
  .card-fields:empty { display: none; }
  .arrange {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin: 12px 0 0;
    padding: 16px 18px;
    border-radius: 16px;
    background: var(--accent);
    color: var(--stage);
    text-decoration: none;
    touch-action: manipulation;
    transition: transform 120ms cubic-bezier(0.34, 1.56, 0.64, 1), opacity 120ms ease;
  }
  .arrange:active {
    transform: scale(0.97);
    opacity: 0.92;
  }
  .arrange .t { font: 500 1.2rem/1.2 var(--display); }
  .arrange .s { font-size: 0.85rem; opacity: 0.8; }
  .field { display: flex; flex-direction: column; gap: 6px; font-size: 0.88rem; }
  textarea.text-in { resize: vertical; line-height: 1.35; }
  /* The news card's beats: one fold-out per beat, its fields inside. */
  .beats { display: flex; flex-direction: column; gap: 10px; }
  .beat { border-radius: 14px; background: var(--wash); padding: 0 14px; }
  .beat[open] { padding-bottom: 14px; }
  .beat summary {
    min-height: 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    cursor: pointer;
    list-style: none;
    font-weight: 600;
  }
  .beat summary::-webkit-details-marker { display: none; }
  .beat summary small { font-weight: normal; color: var(--soft); }
  .beat summary.off span { opacity: 0.5; text-decoration: line-through; }
  .beat-body { display: flex; flex-direction: column; gap: 14px; }
  .beat-body .text-in { background: var(--stage); }
  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .feeds { display: flex; flex-direction: column; gap: 2px; font-size: 0.88rem; }
  .feeds label { display: flex; align-items: center; gap: 10px; min-height: 36px; }
  .feeds input { width: 20px; height: 20px; flex: none; accent-color: var(--ink); }
  .field.inline {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .text-in, select.text-in {
    width: 100%;
    min-height: 44px;
    padding: 10px 12px;
    border-radius: 10px;
    border: 1px solid var(--rule);
    background: var(--wash);
  }
  select.text-in { appearance: none; }
  input[type="time"].text-in { width: auto; }
  .span { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; color: var(--soft); }

  /* A checkbox drawn as a switch. */
  .switch {
    appearance: none;
    flex: none;
    width: 50px;
    height: 30px;
    margin: 0;
    border-radius: 999px;
    background: var(--rule);
    position: relative;
    cursor: pointer;
    touch-action: manipulation;
    transition: background-color 180ms ease;
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 3px;
    left: 3px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--stage);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transition: transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1),
      width 120ms ease;
  }
  .switch:active::after { width: 28px; }
  .switch:checked { background: var(--ink); }
  .switch:checked::after { transform: translateX(20px); }
  .switch:checked:active::after { transform: translateX(16px); }

  /* ── Screen ───────────────────────────────────────────────────────── */
  .setting {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px 0;
    border-bottom: 1px solid var(--rule);
  }
  .setting:first-of-type { border-top: 1px solid var(--rule); }
  .setting .head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  .setting .hint { margin: 0; color: var(--soft); font-size: 0.84rem; max-width: 34em; }
  .setting .sub .range-head { margin-top: 6px; }
  /* A switch that only matters while the one above it is on. */
  .setting .sub {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: 4px 0 2px;
    padding: 4px 0 2px 14px;
    border-left: 2px solid var(--rule);
  }

  /* ── Restart ──────────────────────────────────────────────────────── */
  .restarts { display: flex; flex-direction: column; border-top: 1px solid var(--rule); }
  .restart {
    display: flex;
    align-items: center;
    gap: 14px;
    border: 0;
    border-bottom: 1px solid var(--rule);
    background: none;
    padding: 14px 0;
    text-align: left;
  }
  .restart .t { display: block; }
  .restart .s { display: block; font-size: 0.8rem; color: var(--soft); }
  .restart > span:nth-child(2) { flex: 1; }
  .restart svg { width: 18px; height: 18px; color: var(--faint); flex: none; }

  /* ── Sheets (PIN pad, timer) ──────────────────────────────────────── */
  .scrim {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: flex-end;
    justify-content: center;
    z-index: 100;
    animation: fade 180ms ease;
  }
  .sheet {
    width: 100%;
    max-width: 26rem;
    max-height: 92dvh;
    overflow: auto;
    background: var(--stage);
    color: var(--ink);
    border-radius: 24px 24px 0 0;
    padding: 26px 22px max(24px, env(safe-area-inset-bottom));
    box-shadow: 0 -1px 0 var(--rule);
    animation: rise 240ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  @media (min-width: 560px) {
    .scrim { align-items: center; }
    .sheet { border-radius: 24px; }
  }
  .sheet h2 { margin-bottom: 6px; }
  .sheet .lede { margin-bottom: 22px; }
  .dots { display: flex; justify-content: center; gap: 14px; margin: 6px 0 8px; }
  .dots i {
    width: 13px;
    height: 13px;
    border-radius: 50%;
    box-shadow: inset 0 0 0 1.6px var(--ink);
    transition: background-color 100ms ease;
  }
  .dots i.on { background: var(--ink); }
  .dots.wrong { animation: shake 360ms ease; }
  .pin-msg {
    text-align: center;
    min-height: 1.4em;
    margin: 0 0 14px;
    font-size: 0.88rem;
    color: var(--soft);
  }
  .pad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .key {
    min-height: 62px;
    border: 0;
    border-radius: 16px;
    background: var(--wash);
    font-family: var(--display);
    font-size: 1.7rem;
    font-variation-settings: "SOFT" 100, "opsz" 72;
  }
  .key:active { background: var(--rule); }
  .key.plain { background: none; font-family: var(--text); font-size: 0.9rem; color: var(--soft); }
  .wide-btn {
    width: 100%;
    min-height: 52px;
    margin-top: 18px;
    border: 0;
    border-radius: 999px;
    background: var(--ink);
    color: var(--stage);
    font-weight: 600;
  }
  .wide-btn.quiet { background: var(--wash); color: var(--ink); }
  .wide-btn.danger {
    background: #e53935;
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: background 150ms ease, transform 100ms ease;
  }
  .wide-btn.danger:hover { background: #d32f2f; }
  .wide-btn.danger:active { background: #c62828; transform: scale(0.98); }
  .del-preview-wrap {
    width: 100%;
    display: flex;
    justify-content: center;
    margin-bottom: 16px;
  }
  .del-photo-img {
    width: 128px;
    height: 128px;
    object-fit: cover;
    border-radius: 16px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
    border: 2px solid var(--rule);
  }
  .presets { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 18px; }
  .presets .key { font-size: 1.35rem; }
  .presets .key small {
    font-family: var(--text);
    font-size: 0.75rem;
    color: var(--soft);
    margin-left: 3px;
  }
  .running { list-style: none; margin: 18px 0 0; padding: 0; border-top: 1px solid var(--rule); }
  .running li {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--rule);
  }
  .running .left { flex: 1; font-variant-numeric: tabular-nums; }
  .running .left b {
    font-family: var(--display);
    font-weight: 400;
    font-size: 1.3rem;
    margin-right: 8px;
  }

  .toast {
    position: fixed;
    left: 50%;
    bottom: calc(58px + max(16px, env(safe-area-inset-bottom)));
    transform: translateX(-50%);
    background: var(--ink);
    color: var(--stage);
    padding: 10px 18px;
    border-radius: 999px;
    font-size: 0.88rem;
    font-weight: 500;
    max-width: calc(100% - 36px);
    z-index: 50;
    animation: fade 160ms ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  }
  .alarm-time { font: 400 2.4rem/1.1 var(--display); padding: 8px 14px; }
  .loading { padding: 40vh 0 0; text-align: center; color: var(--soft); }

  /* Moving between pages: isolated to deck-pages so stage header & tab bar stay anchored */
  main { view-transition-name: none; }
  .deck-pages {
    view-transition-name: deck-content;
    overflow-x: hidden;
  }
  .stage-header { view-transition-name: stage-header; }
  .bottom-tab-bar { view-transition-name: bottom-bar; }

  ::view-transition-old(stage-header),
  ::view-transition-new(stage-header),
  ::view-transition-old(bottom-bar),
  ::view-transition-new(bottom-bar) {
    animation: none;
  }

  ::view-transition-old(deck-content) {
    animation: 160ms cubic-bezier(0.4, 0, 1, 1) both out-fwd;
  }
  ::view-transition-new(deck-content) {
    animation: 240ms cubic-bezier(0.16, 1, 0.3, 1) both in-fwd;
  }
  [data-nav="back"]::view-transition-old(deck-content) { animation-name: out-back; }
  [data-nav="back"]::view-transition-new(deck-content) { animation-name: in-back; }
  .page.in-fwd { animation: in-fwd 240ms cubic-bezier(0.16, 1, 0.3, 1); }
  .page.in-back { animation: in-back 240ms cubic-bezier(0.16, 1, 0.3, 1); }
  @keyframes in-fwd { from { opacity: 0; transform: translateX(24px); } }
  @keyframes in-back { from { opacity: 0; transform: translateX(-24px); } }
  @keyframes out-fwd { to { opacity: 0; transform: translateX(-24px); } }
  @keyframes out-back { to { opacity: 0; transform: translateX(24px); } }
  .scrim.closing { animation: fade 160ms ease reverse forwards; }
  .scrim.closing .sheet { animation: sink 180ms cubic-bezier(0.4, 0, 1, 1) forwards; }
  @keyframes sink { to { transform: translateY(40px); opacity: 0; } }

  @keyframes fade { from { opacity: 0; } }
  @keyframes rise { from { transform: translateY(40px); opacity: 0; } }
  @keyframes shake {
    20%, 60% { transform: translateX(-9px); }
    40%, 80% { transform: translateX(9px); }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
    ::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) {
      animation: none !important;
    }
  }

  /* ── Screens: every display in the house, and setting up a new one ── */
  .changing {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 -4px 10px;
    padding: 9px 14px;
    border-radius: 14px;
    background: var(--sc, var(--wash));
    color: #fff;
    font-weight: 600;
    font-size: 0.92rem;
    text-decoration: none;
  }
  .changing .to { margin-left: auto; font-weight: 500; opacity: 0.9; }
  .changing .dot { width: 9px; height: 9px; border-radius: 50%; background: #fff; flex: none; }
  .find-btn {
    border: 1px solid var(--rule);
    background: var(--wash);
    border-radius: 999px;
    padding: 0 14px;
    height: 36px;
    font-size: 0.85rem;
    font-weight: 600;
  }
  #screens { padding-top: max(16px, env(safe-area-inset-top)); padding-bottom: 40px; }
  .sc-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
  .sc-tile {
    display: flex;
    flex-direction: column;
    gap: 9px;
    padding: 10px;
    border: 1px solid var(--rule);
    border-radius: 18px;
    background: var(--wash);
    text-align: left;
    text-decoration: none;
    color: inherit;
  }
  .sc-tile.wide { grid-column: 1 / -1; }
  .sc-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .sc-head h2 { font-size: 2.1rem; margin: 6px 0 4px; }
  .sc-tile .rm {
    border: 0;
    border-radius: 999px;
    padding: 9px 14px;
    background: #e53935;
    color: #fff;
    font-weight: 600;
  }
  .sc-tile .home-note { color: var(--faint); font-size: 0.8rem; padding: 0 2px; }
  .sc-same { display: flex; flex-direction: column; gap: 10px; }
  .sc-tile .nm { display: flex; align-items: center; gap: 8px; font-weight: 600; padding: 0 2px; }
  .sc-tile .what { color: var(--soft); font-size: 0.84rem; margin-top: -6px; padding: 0 2px; }
  .sc-sw { width: 12px; height: 12px; border-radius: 4px; flex: none; background: var(--sc); }
  .sc-on { margin-left: auto; font-size: 0.74rem; font-weight: 600; color: #34c759;
    display: inline-flex; align-items: center; gap: 5px; }
  .sc-on::before {
    content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor;
  }
  .sc-on.off { color: var(--faint); }
  .sk {
    position: relative;
    width: 100%;
    max-width: 100%;
    border-radius: 9px;
    overflow: hidden;
    background: #16181c;
    color: #fff;
    container-type: inline-size;
  }
  .sk img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .sk .time {
    position: absolute;
    left: 7%;
    bottom: 9%;
    font: 400 17cqw/1 var(--display);
    text-shadow: 0 2px 12px rgba(0, 0, 0, 0.35);
  }
  .sk .photo-bg {
    position: absolute;
    inset: 0;
    background: linear-gradient(160deg, #e07a5f, #3d405b);
    background-size: cover;
    background-position: center;
  }
  .sk .cells { position: absolute; inset: 0; display: grid; gap: 3cqw; padding: 3cqw; }
  .sk .cell {
    border-radius: 2.4cqw;
    background: rgba(255, 255, 255, 0.12);
    padding: 3cqw;
    font-size: 5.6cqw;
    line-height: 1.1;
    overflow: hidden;
    min-width: 0;
  }
  .sk .cell.cam { background: linear-gradient(180deg, #3b4148, #20252a); }
  .sk .new {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    text-align: center;
    background: #f6f3ee;
    color: #1f1d1a;
    font: 600 9cqw/1.15 var(--display);
    padding: 6cqw;
  }
  .join {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 16px;
    padding: 14px 16px;
    border-radius: 18px;
    border: 2px solid #e57f93;
    background: rgba(229, 127, 147, 0.1);
  }
  .join .txt { flex: 1; min-width: 0; }
  .join b { display: block; }
  .join span { color: var(--soft); font-size: 0.88rem; }
  .join button, .pill-btn {
    border: 0;
    border-radius: 999px;
    padding: 10px 16px;
    background: var(--ink);
    color: var(--stage);
    font-weight: 600;
    flex: none;
  }
  .sc-add {
    margin-top: 12px;
    width: 100%;
    min-height: 60px;
    border: 1.5px dashed var(--rule);
    border-radius: 18px;
    background: transparent;
    color: var(--soft);
    font-weight: 600;
  }
  .sc-help { margin-top: 12px; padding: 16px; border-radius: 18px; background: var(--wash); }
  .sc-help ol { margin: 0; padding-left: 1.2em; display: flex; flex-direction: column; gap: 8px; }
  .sc-addr {
    display: block;
    margin: 4px 0;
    padding: 10px 12px;
    border-radius: 12px;
    background: var(--stage);
    font-weight: 700;
    font-size: 1.05rem;
    user-select: all;
    -webkit-user-select: all;
  }
  .sc-name {
    width: 100%;
    padding: 12px 14px;
    border: 1px solid var(--rule);
    border-radius: 12px;
    background: var(--wash);
    font-size: 1.05rem;
  }
  .sc-colours { display: flex; gap: 12px; flex-wrap: wrap; }
  .sc-colours button {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    border: 3px solid transparent;
    background: var(--sc);
  }
  .sc-colours button[aria-checked="true"] {
    border-color: var(--stage);
    outline: 3px solid var(--ink);
  }
  .sc-choices { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .sc-choice {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px;
    border: 2px solid var(--rule);
    border-radius: 16px;
    background: transparent;
    text-align: left;
  }
  .sc-choice[aria-checked="true"] { border-color: var(--ink); }
  .sc-choice b { font-size: 0.92rem; }
  .sc-choice span { font-size: 0.78rem; color: var(--soft); line-height: 1.3; }
  .sc-choice .sk { max-height: 120px; }
  .this-screen { display: flex; flex-direction: column; gap: 10px; }
  .page .this-screen { padding-top: 8px; }
  .page .this-screen h3 { margin-top: 8px; }
  .stage-actions { display: flex; align-items: center; gap: 8px; }
  .this-screen .row2 { display: flex; gap: 8px; }
  .this-screen .row2 .sc-name { flex: 1; min-width: 0; }
</style>
</head>
<body>
<main>
  <p class="loading" id="loading">Finding the screen…</p>

  <div id="screens" hidden>
    <div class="sc-head">
      <h2 class="display" tabindex="-1">Screens</h2>
      <button type="button" class="find-btn" id="sc-edit" aria-pressed="false">Edit</button>
    </div>
    <p class="lede">Every display in the house. Tap one to change it.</p>
    <div id="sc-join"></div>
    <div class="sc-list" id="sc-list"></div>
    <button type="button" class="sc-add" id="sc-add">+ Add a screen</button>
    <div class="sc-help" id="sc-help" hidden>
      <ol>
        <li>On the tablet, open the web browser and go to:
          <span class="sc-addr" id="sc-addr"></span></li>
        <li>The tablet says &ldquo;New screen!&rdquo;</li>
        <li>It shows up at the top of this page, ready to set up.</li>
      </ol>
      <p class="note">On an iPad, choose Share, then Add to Home Screen, so it opens
        full screen.</p>
    </div>
  </div>

  <div id="app" hidden>
    <header class="stage-header" id="stage-header">
      <a class="changing" id="changing" href="/menu" hidden>
        <span class="dot" aria-hidden="true"></span>
        <span id="changing-t"></span>
        <span class="to">All screens &rsaquo;</span>
      </a>
      <div class="stage-topbar">
        <div class="screen-meta">
          <h1 class="screen-name display" id="stage-screen-name">Your screen</h1>
          <span class="status-indicator" id="stage-status-indicator" title="Connected">
            <span class="pulse-dot"></span><span id="stage-status-text">Live</span>
          </span>
        </div>
        <div class="stage-actions">
          <button type="button" class="find-btn" id="find-it" hidden>Find it</button>
          <button type="button" class="dark-toggle" id="dark-toggle"
            aria-label="Toggle dark mode" title="Dark mode">
            <span class="dark-icon" aria-hidden="true">🌙</span>
          </button>
        </div>
      </div>

      <figure class="mini" id="mini-frame">
        <div class="mini-stage dim" id="mini" aria-hidden="true"></div>
        <figcaption class="live" id="mini-live" hidden>Live</figcaption>
      </figure>

      <div class="stage-modes" role="radiogroup" aria-label="Display mode">
        <button class="q mode" type="button" id="q-clock" aria-pressed="false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="9"/>
              <polyline points="12 7 12 12 15 14"/>
          </svg>
          <span id="q-clock-label">Photo Clock</span>
        </button>
        <button class="q mode" type="button" id="q-alt" aria-pressed="false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M4 9a8 8 0 0 1 14.5-3.5M20 4v4h-4M20 15a8 8 0 0 1-14.5 3.5M4 20v-4h4"/></svg>
          Alternate
        </button>
        <button class="q mode" type="button" id="timer-open">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2.5M9.5 2.5h5"/></svg>
          Timer<span class="n" id="q-timers" hidden></span>
        </button>
      </div>
      <button class="ringing" type="button" id="q-dismiss" hidden>
        Turn off the alarm</button>
    </header>

    <div class="deck-pages" id="deck-pages">
      <div class="page" id="page-home" hidden>
        <nav class="hub" aria-label="Menu">
          <a class="hub-btn" href="#themes">
            <span class="dots" id="hub-dots" aria-hidden="true"></span>
            <span class="t">Themes</span><span class="s" id="hub-theme"></span>
          </a>
          <a class="hub-btn" href="#photos">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="9" cy="11" r="2"/>
                <path d="M21 16.5l-4.6-4.6a2 2 0 0 0-2.8 0L7 18"/></svg>
            <span class="t">Add photos</span><span class="s" id="hub-photos"></span>
          </a>
          <a class="hub-btn" href="#settings">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/>
                <circle cx="10" cy="17" r="2"/></svg>
            <span class="t">Settings</span>
            <span class="s" id="hub-settings">Layout, cards and night</span>
          </a>
          <a class="hub-btn" href="#device">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>
            <span class="t">Device</span><span class="s warn" id="hub-device"></span>
          </a>
        </nav>
      </div>

    <div class="page" id="page-themes" hidden>
      <a class="back" href="#">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 6l-6 6 6 6"/></svg>
        Your screen</a>
      <h2 id="look-h" tabindex="-1">Themes</h2>
      <p class="lede">Colours and type for the whole screen.</p>
      <ul class="swatches" id="swatches" role="radiogroup" aria-label="Theme"></ul>
      <p class="blurb" id="blurb"></p>

      <h3 id="clock-h">Clock</h3>
      <div class="chips" id="clocks" role="radiogroup" aria-labelledby="clock-h"></div>
      <p class="note">Small clock tiles stay stacked, except Word grid and Bulge.</p>

      <h3 id="font-h">Font</h3>
      <div class="chips" id="fonts" role="radiogroup" aria-labelledby="font-h"></div>
      <p class="note">Used for everything but the clock, and kept when the theme changes.
        A theme you made can bring its own font; pick Theme's own to see it.</p>

      <h3>Background</h3>
      <div class="setting">
        <div class="head">
          <label for="anim-bg">Animated background</label>
          <input type="checkbox" class="switch" role="switch" id="anim-bg"
            aria-describedby="anim-bg-s" />
        </div>
        <p class="hint" id="anim-bg-s">A slow diagonal drift of the theme's own colours
          behind the cards. Liquid Glass keeps its own background instead.</p>
      </div>

      <div id="wall-box" hidden>
        <h3>Background picture</h3>
        <div class="wall">
          <img id="wall-img" alt="Current background" hidden />
          <div class="btns">
            <label class="pill" id="wall-pick">Choose a picture
              <input type="file" id="wall-file" accept="image/jpeg,image/png,image/webp" /></label>
            <button class="pill" type="button" id="wall-remove" hidden>Remove</button>
          </div>
        </div>
      </div>
    </div>

    <div class="page" id="page-alarms" hidden>
      <button type="button" id="alarm-open" style="display:none"></button>
      <a class="back" href="#">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 6l-6 6 6 6"/></svg>
        Your screen</a>
      <h2 tabindex="-1">Alarms</h2>
      <p class="lede">Set here or by asking Antigua. Once one has gone off, it's gone.</p>
      <div class="add-row">
        <button class="q" type="button" id="al-add-alarm">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 5v14M5 12h14"/></svg>
          Alarm</button>
        <button class="q" type="button" id="al-add-reminder">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 5v14M5 12h14"/></svg>
          Reminder</button>
      </div>
      <ul class="alarms" id="al-list" aria-label="Alarms and reminders"></ul>
      <p class="al-empty" id="al-empty" hidden></p>
    </div>

    <div class="page" id="page-photos" hidden>
      <a class="back" href="#">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 6l-6 6 6 6"/></svg>
        Your screen</a>
      <h2 tabindex="-1">Add photos</h2>
      <p class="lede">They join the slideshow within a few seconds. For a Live
        Photo that moves, use Photos → Save as Video, then pick the video.</p>
      <label class="drop" id="up-pick">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="9" cy="11" r="2"/>
            <path d="M21 16.5l-4.6-4.6a2 2 0 0 0-2.8 0L7 18"/></svg>
        <span class="t" id="up-t">Choose photos</span>
        <span class="s" id="up-s">From this phone, as many as you like</span>
        <input type="file" id="up-file" multiple
          accept="image/jpeg,image/png,image/webp,video/quicktime,video/mp4" />
      </label>
      <p class="up-done" id="up-done" role="status"></p>
      <div class="photos-bar" id="photos-bar">
        <h3 id="recent-h" hidden>Recently added</h3>
        <button type="button" class="manage-btn" id="manage-photos-btn" hidden
          aria-pressed="false">
          <svg class="manage-icon" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path
              d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2">
            </path>
          </svg>
          <span id="manage-btn-text">Manage photos</span>
        </button>
      </div>
      <p class="manage-hint" id="manage-hint" hidden>
        Tap any photo to delete it from the slideshow.
      </p>
      <ul class="up-grid" id="up-grid" aria-labelledby="recent-h"></ul>
    </div>

    <div class="page" id="page-settings" hidden>
      <h2 tabindex="-1">Settings</h2>
      <section class="photo-clock-sec" id="photo-clock-sec" aria-labelledby="pc-sec-h">
        <div class="pc-banner">
          <div class="pc-banner-text">
            <h3 id="pc-sec-h">Photo Clock</h3>
            <p class="lede">Full-screen photos with a live clock overlay.</p>
          </div>
          <span class="pc-status-badge" id="pc-status-badge">Off</span>
        </div>
        <div class="setting">
          <div class="head">
            <label for="nc-hold">Show Photo Clock now</label>
            <input type="checkbox" class="switch" role="switch" id="nc-hold"
              aria-describedby="nc-hold-s" />
          </div>
          <p class="hint" id="nc-hold-s">Keeps your photos and clock on screen day and night instead of cards.</p>
        </div>
        <div class="pc-summary-card" id="pc-summary-card">
          <div class="pc-summary-row">
            <span class="pc-summary-label">Current look</span>
            <span class="pc-summary-val" id="pc-summary-val">Liquid glass · Row</span>
          </div>
          <button type="button" class="wide-btn pc-customize-btn" id="settings-open-pc">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="width:18px;height:18px">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            Customize Photo Clock
          </button>
        </div>
      </section>
      <section class="this-screen" id="this-screen" aria-labelledby="this-h">
        <h3 id="this-h">This screen</h3>
        <span class="label" id="shows-l">Shows</span>
        <div class="chips" id="shows" role="radiogroup" aria-labelledby="shows-l"></div>
        <span class="label" id="popups-l">Pop-ups</span>
        <div class="chips" id="popups" role="radiogroup" aria-labelledby="popups-l"
          aria-describedby="popups-s"></div>
        <p class="note" id="popups-s">Recipes, alarms, and the cameras when someone's at
          the door.</p>
        <label class="label" for="sc-rename">Name</label>
        <div class="row2">
          <input class="sc-name" id="sc-rename" type="text" maxlength="40" autocomplete="off" />
          <button type="button" class="pill-btn" id="sc-rename-go">Save</button>
        </div>
        <button type="button" class="wide-btn quiet" id="sc-remove" hidden>
          Remove this screen</button>
      </section>
      <a class="arrange" id="arrange" href="/layout">
        <span class="t">Arrange this screen</span>
        <span class="s">Pick card sizes, add cards or remove them</span>
      </a>
      <section id="cards-sec" aria-labelledby="cards-h">
        <h3 id="cards-h">Card settings</h3>
      <p class="lede">Tap a card to change what it shows.</p>
      <ul class="card-grid" id="card-list" aria-labelledby="cards-h"></ul>
      <details class="others" id="others" hidden>
        <summary>Not on this screen <span id="others-n"></span></summary>
        <ul class="card-grid" id="other-list"></ul>
      </details>
      </section>
      <section aria-labelledby="pace-h">
        <h3 id="pace-h">Timing</h3>
        <p class="lede">How long things stay up before the next one.</p>
      <div class="setting">
        <span class="label" id="pace-l">Rotation speed</span>
        <div class="chips" id="paces" role="radiogroup" aria-labelledby="pace-l"
          aria-describedby="pace-s"></div>
        <p class="hint" id="pace-s">Quotes, headlines and camera views.</p>
      </div>
      <div class="setting">
        <span class="label" id="hold-l">Each photo</span>
        <div class="chips" id="holds" role="radiogroup" aria-labelledby="hold-l"></div>
      </div>
      </section>
      <section aria-labelledby="screen-h">
        <h3 id="screen-h">Night &amp; Dimming</h3>
        <p class="lede">What the screen does while everyone's asleep.</p>
      <div class="setting">
        <div class="head">
          <label for="nc-on">Night clock</label>
          <input type="checkbox" class="switch" role="switch" id="nc-on"
            aria-describedby="nc-on-s" />
        </div>
        <p class="hint" id="nc-on-s">Late at night the screen shows just a big, dim clock.
          In the morning it goes back to your cards on its own.</p>
        <div class="sub" id="peek-box">
          <span class="label" id="peek-l">A tap shows your cards for</span>
          <div class="chips" id="peeks" role="radiogroup" aria-labelledby="peek-l"></div>
        </div>
      </div>
      <div class="setting">
        <div class="head">
          <label for="dim-on">Dim in the evening</label>
          <input type="checkbox" class="switch" role="switch" id="dim-on"
            aria-describedby="dim-on-s" />
        </div>
        <p class="hint" id="dim-on-s">Turns the brightness down between these hours,
          and back up after.</p>
        <div class="sub" id="dim-box" hidden>
          <div class="span">
            <span>From</span>
            <input type="time" class="text-in" id="dim-from" aria-label="Dim from" />
            <span>to</span><input type="time" class="text-in" id="dim-to" aria-label="Dim until" />
          </div>
          <label class="range-head" for="dim-level">
            <span>Brightness while dimmed</span>
            <output id="dim-level-v" for="dim-level"></output></label>
          <input class="range" type="range" id="dim-level" min="0.1" max="1" step="0.05" />
        </div>
      </div>
      <div class="setting">
        <div class="head">
          <label for="night-on">Go dark overnight</label>
          <input type="checkbox" class="switch" role="switch" id="night-on"
            aria-describedby="night-on-s" />
        </div>
        <p class="hint" id="night-on-s">The screen goes black between these hours,
          night clock included.</p>
        <div class="span" id="night-span" hidden>
          <span>From</span>
          <input type="time" class="text-in" id="night-from" aria-label="Go dark at" />
          <span>to</span><input type="time" class="text-in" id="night-to" aria-label="Wake up at" />
        </div>
      </div>
      </section>
    </div>

    <div class="page" id="page-device" hidden>
      <a class="back" href="#">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 6l-6 6 6 6"/></svg>
        Your screen</a>
      <h2 tabindex="-1">Device</h2>
      <p class="lede">How the screen and the server are doing. Checked every few
        seconds while this page is open.</p>
      <section class="health" aria-labelledby="pi-h">
        <h3 id="pi-h">The screen's Raspberry Pi</h3>
        <dl class="stats" id="st-screen"></dl>
      </section>
      <section class="health" aria-labelledby="srv-h">
        <h3 id="srv-h">The server</h3>
        <dl class="stats" id="st-server"></dl>
      </section>
      <section aria-labelledby="restart-h">
        <h3 id="restart-h">Restart</h3>
      <p class="lede" id="restart-lede">
        Both ask for the PIN, so nobody restarts the screen by accident.</p>
      <div class="restarts">
        <button class="restart" type="button" data-restart="display">
          <span aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 1 1 3 6.7"/><path d="M3 21v-5h5"/></svg></span>
          <span><span class="t">Restart the display</span>
            <span class="s">Reloads the screen. Back in about 20 seconds.</span></span>
          <span aria-hidden="true" class="lock"><svg viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="5" y="11" width="14" height="10" rx="2"/>
            <path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></span>
        </button>
        <button class="restart" type="button" data-restart="system">
          <span aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 3v7"/><path d="M6.3 6.3a9 9 0 1 0 11.4 0"/></svg></span>
          <span><span class="t">Restart the Raspberry Pi</span>
            <span class="s">A full reboot. Offline for a minute or two.</span></span>
          <span aria-hidden="true" class="lock"><svg viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="5" y="11" width="14" height="10" rx="2"/>
            <path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></span>
        </button>
      </div>
      </section>

      <section aria-labelledby="shape-h">
        <h3 id="shape-h">Screen shape</h3>
        <p class="lede">Choose round for circular smart displays, or standard for rectangular.</p>
        <button class="q mode" type="button" id="q-round" aria-pressed="false"
          style="min-height:46px;width:100%;border-radius:14px;background:var(--wash);margin-bottom:8px">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>
          Round display mode
        </button>
      <div class="setting">
        <label class="range-head" for="frame-inset">
          <span>Picture frame</span>
          <output id="frame-inset-v" for="frame-inset"></output></label>
        <input class="range" type="range" id="frame-inset" min="0" max="20" step="1"
          aria-describedby="frame-inset-hint" />
        <p class="hint" id="frame-inset-hint">If a frame covers the screen's sides, slide until
          nothing you read is hidden. Photos still fill the screen; the rest moves in at full
          size.</p>
      </div>
      </section>
    </div>
  </div>

  <nav class="bottom-tab-bar" id="bottom-tab-bar" aria-label="Main Navigation">
    <a class="tab-item" href="#themes" id="tab-themes">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="8.5"/><circle cx="8.5" cy="10" r="1.2"/>
        <circle cx="12" cy="7.5" r="1.2"/><circle cx="15.5" cy="10" r="1.2"/>
        <path d="M12 20.5c1.4 0 1.7-1.6 1-2.6-.6-.9 0-2.4 1.4-2.4h2.1"/>
      </svg>
      <span>Look</span>
    </a>
    <a class="tab-item" href="#settings" id="tab-settings">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/>
        <circle cx="10" cy="17" r="2"/>
      </svg>
      <span>Settings</span>
    </a>
    <a class="tab-item" href="#photos" id="tab-photos">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.6"/>
        <path d="m4 17 5-4.5 3.5 3 2.5-2 5 4"/>
      </svg>
      <span>Photos</span>
    </a>
    <a class="tab-item" href="#alarms" id="tab-alarms">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="13" r="7.5"/>
        <path d="M12 9.5V13l2 1.5M4.5 4.5l3 -2M19.5 4.5l-3-2"/>
      </svg>
      <span>Alarms</span>
      <span class="tab-badge" id="tab-alarms-badge" hidden></span>
    </a>
    <a class="tab-item" href="#device" id="tab-device">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>
      </svg>
      <span>Device</span>
    </a>
  </nav>
</div>
</main>

<template id="keep-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="keep-h">
      <h2 id="keep-h">New screen</h2>
      <p class="lede" id="keep-lede"></p>
      <div class="sc-same" id="keep-same" hidden>
        <h3>Set up before?</h3>
        <p class="note">If this is one of these again (opened from a home-screen icon, or its
          browser was cleared), pick it to carry over its name and settings.</p>
        <div class="chips" id="keep-same-list"></div>
      </div>
      <h3><label for="keep-name">Name it</label></h3>
      <input class="sc-name" id="keep-name" type="text" maxlength="40" autocomplete="off"
        placeholder="Living Room, Office…" />
      <div class="chips" id="keep-names" style="margin-top:10px"></div>
      <h3 id="keep-col-h">Its colour</h3>
      <div class="sc-colours" id="keep-colours" role="radiogroup"
        aria-labelledby="keep-col-h"></div>
      <h3 id="keep-shows-h">What should it show?</h3>
      <div class="sc-choices" id="keep-shows" role="radiogroup"
        aria-labelledby="keep-shows-h"></div>
      <button class="wide-btn" type="button" id="keep-go"></button>
      <button class="wide-btn quiet" type="button" id="keep-cancel">Not now</button>
    </div>
  </div>
</template>

<template id="forget-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="forget-h">
      <h2 id="forget-h"></h2>
      <p class="lede">It goes back to the &ldquo;New screen!&rdquo; message. You can set it up
        again any time.</p>
      <button class="wide-btn danger" type="button" id="forget-go">Remove</button>
      <button class="wide-btn quiet" type="button" id="forget-cancel">Keep it</button>
    </div>
  </div>
</template>

<template id="pin-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="pin-h">
      <h2 id="pin-h"></h2>
      <p class="lede" id="pin-lede"></p>
      <div class="dots" id="pin-dots" aria-hidden="true">
        <i></i><i></i><i></i><i></i><i></i><i></i>
      </div>
      <p class="pin-msg" id="pin-msg" role="status"></p>
      <div class="pad" id="pin-pad"></div>
      <button class="wide-btn" type="button" id="pin-go" hidden></button>
      <button class="wide-btn quiet" type="button" id="pin-cancel">Cancel</button>
    </div>
  </div>
</template>

<template id="theme-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="theme-h">
      <h2 id="theme-h">Make a theme</h2>
      <p class="lede">Pick your colours. The writing on top picks itself so it stays
        easy to read.</p>
      <div class="maker-preview" id="mk-preview" aria-hidden="true">
        <p class="hello">Good morning<i></i></p>
        <b data-slot="weather">Weather</b><b data-slot="clock">9:41</b>
        <b data-slot="affirmation">Quote</b>
      </div>
      <label class="field">Name
        <input class="text-in" id="mk-name" maxlength="40" autocomplete="off" /></label>
      <div class="wells" id="mk-wells"></div>
      <h3 id="mk-font-h">Font</h3>
      <div class="chips" id="mk-fonts" role="radiogroup" aria-labelledby="mk-font-h"></div>
      <button class="wide-btn" type="button" id="mk-save">Save theme</button>
      <button class="wide-btn quiet" type="button" id="mk-cancel">Cancel</button>
      <button class="wide-btn quiet" type="button" id="mk-delete" hidden>Delete theme</button>
      <p class="maker-note" id="mk-note" hidden></p>
    </div>
  </div>
</template>

<template id="clock-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="ck-h">
      <h2 id="ck-h">Photo Clock</h2>
      <p class="lede" id="ck-lede">Full-screen photos with the time over them. Changes appear on your display as you make them.</p>
      <h3 id="ck-style-h">Style</h3>
      <div class="chips" id="ck-style" role="radiogroup" aria-labelledby="ck-style-h"></div>
      <p class="lede" id="ck-photo-note" hidden>Your photos fill the screen, a minute each,
        with the time over them, tucked behind the people in them.</p>
      <div class="clock-preview" id="ck-preview" aria-hidden="true"></div>
      <h3 id="ck-font-h">Font</h3>
      <div class="chips" id="ck-fonts" role="radiogroup" aria-labelledby="ck-font-h"></div>
      <div id="ck-plain">
        <h3>Colour</h3>
        <div id="ck-wheel"></div>
      </div>
      <div id="ck-tint-box" hidden>
        <h3 id="ck-tint-h">Tint</h3>
        <div class="chips" id="ck-tints" role="radiogroup" aria-labelledby="ck-tint-h"></div>
        <div id="ck-tint-wheel" hidden></div>
        <h3 id="ck-glass-h">Glass</h3>
        <div class="chips" id="ck-glass" role="radiogroup" aria-labelledby="ck-glass-h"></div>
        <label class="range-head" for="ck-opacity">
          <span>Opacity</span><output id="ck-opacity-out" for="ck-opacity"></output>
        </label>
        <input class="range" type="range" id="ck-opacity" min="0" max="1" step="0.05">

        <h3 id="ck-ink-h" style="margin-top:14px">Photo colours</h3>
        <p class="hint" style="margin:2px 0 8px">
          Numbers in each photo's own colours instead of glass.</p>
        <div class="chips" id="ck-ink" role="radiogroup" aria-labelledby="ck-ink-h"></div>

        <h3 id="ck-layout-h" style="margin-top:14px">Digits layout</h3>
        <p class="hint" id="ck-layout-s" style="margin:2px 0 8px">
          Row keeps time side-by-side; stacked places hours over minutes for portrait framing.
        </p>
        <div class="chips" id="ck-layout" role="radiogroup" aria-labelledby="ck-layout-h"></div>

        <h3 id="ck-trans-h" style="margin-top:14px">Transition</h3>
        <p class="hint" id="ck-trans-s" style="margin:2px 0 8px">
          Swipe slides the next photo from the side; fade dissolves softly between photos.
        </p>
        <div class="chips" id="ck-trans" role="radiogroup" aria-labelledby="ck-trans-h"></div>

        <div class="setting" style="border-top:1px solid var(--rule);margin-top:14px">
          <div class="head">
            <label for="ck-drift">Motion drift</label>
            <input type="checkbox" class="switch" role="switch" id="ck-drift"
              aria-describedby="ck-drift-s">
          </div>
          <p class="hint" id="ck-drift-s">Gentle 3D parallax zoom while each photo is on screen.</p>
        </div>

        <div class="setting">
          <div class="head">
            <label for="ck-whisper">Memory whisper</label>
            <input type="checkbox" class="switch" role="switch" id="ck-whisper"
              aria-describedby="ck-whisper-s">
          </div>
          <p class="hint" id="ck-whisper-s">Briefly reveals the memory date and year of the photo,
            then softly dissolves away.</p>
        </div>

        <div class="setting">
          <div class="head">
            <label for="ck-weather">Weather in date</label>
            <input type="checkbox" class="switch" role="switch" id="ck-weather"
              aria-describedby="ck-weather-s">
          </div>
          <p class="hint" id="ck-weather-s">Subtly shows current temperature and condition glyph in
            the date pill.</p>
        </div>

        <label class="range-head" for="ck-grain" style="margin-top:10px">
          <span>Film grain</span><output id="ck-grain-out" for="ck-grain"></output>
        </label>
        <p class="hint" style="margin:2px 0 6px">Fine-art analog texture to soften digital screen
          glare.</p>
        <input class="range" type="range" id="ck-grain" min="0" max="0.25" step="0.05">
      </div>
      <button class="wide-btn" type="button" id="ck-done">Done</button>
      <button class="wide-btn quiet" type="button" id="ck-off">Bring the cards back</button>
    </div>
  </div>
</template>

<template id="card-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="card-h">
      <h2 id="card-h"></h2>
      <p class="lede" id="card-desc"></p>
      <div class="card-fields" id="card-fields"></div>
      <p class="lede" id="card-where"></p>
      <button class="wide-btn quiet" type="button" id="card-done">Done</button>
    </div>
  </div>
</template>

<template id="alarm-tpl">
  <div class="scrim">
    <div class="sheet al-form" role="dialog" aria-modal="true" aria-labelledby="al-h">
      <h2 id="al-h"></h2>
      <label class="field" id="al-msg-box">Remind me to
        <input class="text-in" id="al-msg" maxlength="120" placeholder="call mom"
          autocomplete="off" enterkeyhint="done" /></label>
      <label class="field">Time
        <input type="time" class="text-in alarm-time" id="al-time" /></label>
      <div class="field">
        <span id="al-when-l">When</span>
        <div class="chips" id="al-when" role="radiogroup" aria-labelledby="al-when-l">
          <button type="button" class="chip" role="radio" data-when="today">Today</button>
          <button type="button" class="chip" role="radio" data-when="tomorrow">Tomorrow</button>
          <button type="button" class="chip" role="radio" data-when="day">Pick a day</button>
          <button type="button" class="chip" role="radio" data-when="repeat">Repeat</button>
        </div>
      </div>
      <input type="date" class="text-in" id="al-date" aria-label="Day" hidden />
      <div class="days" id="al-days" role="group" aria-label="Repeat on" hidden></div>
      <label class="field" id="al-name-box">Name
        <input class="text-in" id="al-name" maxlength="40" placeholder="Optional, like Gym"
          autocomplete="off" /></label>
      <div class="setting al-speak">
        <div class="head">
          <label for="al-speak">Antigua says it out loud</label>
          <input type="checkbox" class="switch" role="switch" id="al-speak" checked
            aria-describedby="al-speak-s" />
        </div>
        <p class="hint" id="al-speak-s"></p>
      </div>
      <button class="wide-btn" type="button" id="al-save"></button>
      <button class="wide-btn quiet" type="button" id="al-delete" hidden>Delete</button>
      <button class="wide-btn quiet" type="button" id="al-cancel">Cancel</button>
    </div>
  </div>
</template>

<template id="timer-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="timer-h">
      <h2 id="timer-h">Set a timer</h2>
      <p class="lede">It counts down on the screen.</p>
      <label class="field" style="margin-bottom:16px">What's it for?
        <input class="text-in" id="timer-label" maxlength="24" placeholder="Timer" /></label>
      <div class="presets" id="presets"></div>
      <ul class="running" id="running" hidden></ul>
      <button class="wide-btn quiet" type="button" id="timer-done">Done</button>
    </div>
  </div>
</template>

<template id="photo-delete-tpl">
  <div class="scrim">
    <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="del-photo-h">
      <div class="del-preview-wrap">
        <img id="del-photo-img" class="del-photo-img" src="" alt="Photo to delete" />
      </div>
      <h2 id="del-photo-h">Delete photo?</h2>
      <p class="lede" id="del-photo-lede">
        This will remove this photo from the slideshow. All versions and modifications of this
        image will be permanently deleted.
      </p>
      <button class="wide-btn danger" type="button" id="del-photo-confirm">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
          stroke-linecap="round" stroke-linejoin="round"
          style="width:18px;height:18px" aria-hidden="true">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2">
          </path>
          <line x1="10" y1="11" x2="10" y2="17"></line>
          <line x1="14" y1="11" x2="14" y2="17"></line>
        </svg>
        Delete photo
      </button>
      <button class="wide-btn quiet" type="button" id="del-photo-cancel">Cancel</button>
    </div>
  </div>
</template>

<script>
(function () {
  'use strict';

  var CLOCKS = [
    ['', 'Screen picks'], ['stack', 'Stacked'], ['words', 'In words'], ['poster', 'Poster'],
    ['flip', 'Flip board'], ['seg', 'Seven-segment'], ['analog', 'Analog'],
    ['contour', 'Contour'], ['bulge', 'Bulge'], ['qlock', 'Word grid'],
  ];
  // Mirrors FONTS in @pinedaview/tokens (and themes.py's FONTS); '' is the theme's own.
  var FONTS = [
    ['', "Theme's own"], ['google_sans_flex', 'Google Sans Flex'],
    ['atkinson_next', 'Atkinson Hyperlegible Next'], ['zalando_sans', 'Zalando Sans'],
    ['geist', 'Geist'], ['mona_sans', 'Mona Sans'], ['inter', 'Inter'],
    ['instrument_sans', 'Instrument Sans'], ['hanken_grotesk', 'Hanken Grotesk'],
    ['schibsted_grotesk', 'Schibsted Grotesk'], ['host_grotesk', 'Host Grotesk'],
    ['parkinsans', 'Parkinsans'], ['funnel_display', 'Funnel Display'],
    ['unbounded', 'Unbounded'], ['bricolage', 'Bricolage Grotesque'], ['fredoka', 'Fredoka'],
    ['instrument_serif', 'Instrument Serif'], ['young_serif', 'Young Serif'],
    ['playfair', 'Playfair'], ['newsreader', 'Newsreader'], ['geist_mono', 'Geist Mono'],
    ['caveat', 'Caveat'], ['pixelify_sans', 'Pixelify Sans'], ['jacquard_24', 'Jacquard 24'],
    ['roboto', 'Roboto'], ['aileron', 'Aileron'],
  ];
  function fontName(id) {
    var f = FONTS.filter(function (x) { return x[0] === id; })[0];
    return f ? f[1] : '';
  }
  function specimen(id) { return '"pf-' + id + '", system-ui, sans-serif'; }
  // A face per font for the picker's specimens; each loads only once drawn.
  var fontFaces = document.createElement('style');
  FONTS.slice(1).forEach(function (f) {
    fontFaces.textContent += '@font-face{font-family:"pf-' + f[0] + '";font-weight:100 900;'
      + 'font-display:swap;src:url("/menu/fonts/' + f[0] + '.woff2")}';
  });
  document.head.appendChild(fontFaces);
  // Which theme colour each card is painted with (mirrors the SPA's <Card accent>).
  var ACCENT = {
    clock: 'clock', weather: 'weather', forecast: 'forecast', affirmation: 'affirmation',
    traffic: 'affirmation', phrase: 'phrase', 'now-playing': 'nowPlaying',
    countdown: 'countdown', moon: 'moon', 'moon-climate': 'moon', 'home-cams': 'moon',
  };
  var HIDDEN_CARDS = { 'daily-content': true }; // feeds other cards, no face of its own
  var TIMER_MIN = [1, 3, 5, 10, 15, 20, 30, 45, 60];
  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');

  var S = {
    screen: null, profile: null, themes: [], cards: {}, view: null,
    pinRequired: true, photo: null, timers: [], alarms: [], alarmsDown: false,
  };

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'html') n.innerHTML = attrs[k];
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] !== null && attrs[k] !== undefined && attrs[k] !== false) {
        n.setAttribute(k, attrs[k]);
      }
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }

  function call(path, method, body, headers) {
    var opts = { method: method || 'GET', headers: headers || {} };
    if (body !== undefined) {
      opts.headers['content-type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) {
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (b) {
          var e = new Error('HTTP ' + r.status);
          e.status = r.status;
          e.detail = typeof b.detail === 'string' ? b.detail : null;
          throw e;
        });
      }
      return r.status === 200 || r.status === 201 ? r.json() : null;
    });
  }

  var toastTimer = null;
  function toast(text) {
    var old = document.querySelector('.toast');
    if (old) old.remove();
    var t = el('div', { class: 'toast', role: 'status', text: text });
    document.body.appendChild(t);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.remove(); }, 2200);
  }
  function failed(what) {
    return function () { toast("Couldn't " + what + '. Check the Wi-Fi and try again.'); };
  }

  // ── Which screen ──────────────────────────────────────────────────
  // Only the screen the URL names: without one the menu opens on Screens,
  // so it never quietly changes whichever display was on last.
  var WANTED = new URLSearchParams(location.search).get('screen');
  function pickScreen(devices) {
    return devices.filter(function (d) { return d.id === WANTED; })[0] || null;
  }

  // ── Screens ───────────────────────────────────────────────────────
  // Mirrors SCREEN_COLOURS in registry.py and web lib/screenColours.ts.
  var COLOURS = {
    amber: '#d98a1f', teal: '#1a958f', violet: '#7a55c7',
    rose: '#c2566b', blue: '#3a6fd1', green: '#3d8f4f',
  };
  var SHOWS = [
    { id: 'photo', name: 'Photo Clock', hint: 'Your photos with the time' },
    { id: 'cameras', name: 'Cameras', hint: 'The latest doorbell and garage photos' },
    { id: 'cards', name: 'All cards', hint: 'Weather, calendar, news and more' },
    { id: 'mix', name: 'Mix', hint: 'The cameras plus a few cards' },
  ];
  var MIX_CARDS = ['weather', 'clock', 'calendar']; // api._shows_grid's
  var POPUPS = [
    { id: 'all', name: 'Everything' },
    { id: 'cameras', name: 'Cameras only' },
    { id: 'none', name: 'None' },
  ];
  var SC = {
    devices: [], profiles: [], snapshot: false, poll: null, helpOpen: false, snapUrl: null,
    editing: false,
  };

  function colourOf(d) { return COLOURS[d.colour] || COLOURS.amber; }
  function isTall(d) { return (d.viewport_h || 0) > (d.viewport_w || 0); }
  function showsOf(d) {
    if (d.night_clock_hold) return d.night_clock_photo ? 'photo' : null;
    if (d.alternate) return null;
    var g = d.grid;
    if (!g) return 'cards';
    var cams = g.items.some(function (i) { return i.card === 'home-cams'; });
    if (cams && g.items.length === 1) return 'cameras';
    return cams ? 'mix' : null;
  }
  function showsText(d) {
    var id = showsOf(d);
    if (id) return SHOWS.filter(function (x) { return x.id === id; })[0].name;
    if (d.night_clock_hold) return d.night_clock_photo !== false ? 'Photo Clock' : 'Clock';
    if (d.alternate) return 'Photo Clock and cards';
    return 'Your own layout';
  }
  function stackOf(d) {
    var p = SC.profiles.filter(function (x) { return x.id === d.profile_id; })[0];
    var stack = d.card_stack || (p && p.card_stack) || [];
    return stack.filter(function (c) {
      return (d.cards_off || []).indexOf(c) < 0 && !HIDDEN_CARDS[c];
    });
  }
  // What a sketch draws: "new", "snap", "photo", or boxes on a grid.
  function planFor(d) {
    if (!d.kept) return { kind: 'new' };
    if (d.home && SC.snapshot) return { kind: 'snap' };
    var shows = showsOf(d);
    if (shows === 'photo' || d.night_clock_hold) return { kind: 'photo' };
    if (d.grid) return { kind: 'cells', cols: d.grid.cols, items: d.grid.items };
    return autoPlan(stackOf(d), isTall(d));
  }
  function planForShows(shows, tall) {
    if (shows === 'photo') return { kind: 'photo' };
    if (shows === 'cameras') {
      return { kind: 'cells', cols: 1, items: [{ card: 'home-cams', x: 0, y: 0, w: 1, h: 1 }] };
    }
    if (shows === 'mix') {
      var items = tall
        ? [{ card: 'home-cams', x: 0, y: 0, w: 3, h: 2 }].concat(MIX_CARDS.map(function (c, i) {
          return { card: c, x: i, y: 2, w: 1, h: 1 };
        }))
        : [{ card: 'home-cams', x: 0, y: 0, w: 2, h: 3 }].concat(MIX_CARDS.map(function (c, i) {
          return { card: c, x: 2, y: i, w: 1, h: 1 };
        }));
      return { kind: 'cells', cols: 3, items: items };
    }
    var p = SC.profiles.filter(function (x) { return x.id === 'default'; })[0];
    var stack = ((p && p.card_stack) || []).filter(function (c) { return !HIDDEN_CARDS[c]; });
    return autoPlan(stack, tall);
  }
  function autoPlan(cards, tall) {
    var cols = tall ? 2 : 4;
    var items = cards.slice(0, tall ? 6 : 8).map(function (c, i) {
      return { card: c, x: i % cols, y: Math.floor(i / cols), w: 1, h: 1 };
    });
    return { kind: 'cells', cols: cols, items: items };
  }
  function sketch(plan, w, h) {
    var box = el('div', { class: 'sk', 'aria-hidden': 'true' });
    box.style.aspectRatio = (w || 16) + ' / ' + (h || 10);
    if (plan.kind === 'new') {
      box.appendChild(el('div', { class: 'new', text: 'New screen!' }));
    } else if (plan.kind === 'snap') {
      box.appendChild(el('div', { class: 'photo-bg' }));
      if (SC.snapUrl) box.appendChild(el('img', { alt: '', src: SC.snapUrl }));
    } else if (plan.kind === 'photo') {
      var ph = el('div', { class: 'photo-bg' });
      if (S.photo) {
        ph.style.backgroundImage = 'url("/api/photos/' + encodeURIComponent(S.photo) + '/thumb")';
      }
      box.appendChild(ph);
      box.appendChild(el('div', { class: 'time', text: clockText() }));
    } else {
      var rows = plan.items.reduce(function (n, i) { return Math.max(n, i.y + i.h); }, 1);
      var cells = el('div', { class: 'cells' });
      cells.style.gridTemplateColumns = 'repeat(' + plan.cols + ', minmax(0, 1fr))';
      cells.style.gridTemplateRows = 'repeat(' + rows + ', minmax(0, 1fr))';
      plan.items.forEach(function (i) {
        var label = i.card === 'clock' ? clockText()
          : i.card === 'home-cams' ? 'Cameras' : cardName(i.card);
        var c = el('div', { class: 'cell' + (i.card === 'home-cams' ? ' cam' : ''), text: label });
        c.style.gridColumn = (i.x + 1) + ' / span ' + i.w;
        c.style.gridRow = (i.y + 1) + ' / span ' + i.h;
        cells.appendChild(c);
      });
      box.appendChild(cells);
    }
    return box;
  }

  function kept() {
    return SC.devices.filter(function (d) { return d.kept; }).sort(function (a, b) {
      return (b.home - a.home) || (a.paired_at < b.paired_at ? -1 : 1);
    });
  }
  function loadScreens() {
    return Promise.all([call('/api/devices'), call('/api/profiles')]).then(function (r) {
      SC.devices = r[0];
      SC.profiles = r[1];
    });
  }
  function renderScreens() {
    var join = $('sc-join');
    join.innerHTML = '';
    // Waiting: on right now, and nobody has set it up.
    SC.devices.filter(function (d) { return !d.kept && d.online; }).forEach(function (d) {
      join.appendChild(el('div', { class: 'join' }, [
        el('div', { class: 'txt' }, [
          el('b', { text: 'A new screen wants to join' }),
          el('span', { text: (d.kind || 'A screen') + ' · on now' }),
        ]),
        el('button', { type: 'button', text: 'Set it up', onclick: function () { openKeep(d); } }),
      ]));
    });
    var list = $('sc-list');
    list.innerHTML = '';
    kept().forEach(function (d) {
      // Editing: each tile offers Remove instead of opening the screen.
      var extra = !SC.editing ? null : d.home
        ? el('div', { class: 'home-note', text: 'The kitchen display stays.' })
        : el('button', {
          type: 'button', class: 'rm', text: 'Remove',
          onclick: function () {
            confirmRemove(d, function () { loadScreens().then(renderScreens); });
          },
        });
      var tile = el(SC.editing ? 'div' : 'a', {
        class: 'sc-tile' + (isTall(d) ? '' : ' wide'),
        href: SC.editing ? null : '/menu?screen=' + encodeURIComponent(d.id),
      }, [
        sketch(planFor(d), d.viewport_w, d.viewport_h),
        el('div', { class: 'nm' }, [
          el('span', { class: 'sc-sw' }),
          el('span', { text: d.name }),
          el('span', { class: 'sc-on' + (d.online ? '' : ' off'), text: d.online ? 'On' : 'Off' }),
        ]),
        el('div', { class: 'what', text: d.online ? showsText(d) : offSince(d) }),
        extra,
      ]);
      tile.style.setProperty('--sc', colourOf(d));
      list.appendChild(tile);
    });
    $('sc-help').hidden = !SC.helpOpen;
  }
  // "Off since 11:56 AM", "Off since Tuesday", "Off since Oct 3".
  function offSince(d) {
    if (!d.last_seen) return 'Off';
    var t = new Date(d.last_seen);
    var now = new Date();
    var days = (now - t) / 86400000;
    var when = t.toDateString() === now.toDateString()
      ? t.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
      : days < 6 ? t.toLocaleDateString([], { weekday: 'long' })
        : t.toLocaleDateString([], { month: 'short', day: 'numeric' });
    return 'Off since ' + when;
  }
  function confirmRemove(d, done) {
    var sheet = openSheet('forget-tpl');
    sheet.root.querySelector('#forget-h').textContent = 'Remove ' + d.name + '?';
    sheet.root.querySelector('#forget-cancel').addEventListener('click', sheet.close);
    sheet.root.querySelector('#forget-go').addEventListener('click', function () {
      call('/api/devices/' + encodeURIComponent(d.id) + '/forget', 'POST')
        .then(function () { sheet.close(); toast(d.name + ' removed'); done(); })
        .catch(failed('remove the screen'));
    });
  }
  function startScreens() {
    $('sc-addr').textContent = location.host;
    $('sc-edit').addEventListener('click', function () {
      SC.editing = !SC.editing;
      this.textContent = SC.editing ? 'Done' : 'Edit';
      this.setAttribute('aria-pressed', SC.editing ? 'true' : 'false');
      renderScreens();
    });
    $('sc-add').addEventListener('click', function () {
      SC.helpOpen = !SC.helpOpen;
      renderScreens();
    });
    $('loading').hidden = true;
    $('screens').hidden = false;
    document.title = 'Screens · Companion';
    renderScreens();
    // A tablet turned on shows up here within a few seconds.
    SC.poll = setInterval(function () {
      if (document.hidden || document.querySelector('.scrim')) return;
      loadScreens().then(renderScreens).catch(function () {});
    }, 4000);
    if (SC.snapshot) {
      grabSnap();
      setInterval(grabSnap, LIVE_MS);
    }
  }
  // The kiosk's real screen, fetched once per LIVE_MS for every tile redraw.
  function grabSnap() {
    if (document.hidden) return;
    fetch('/api/control/snapshot?t=' + Date.now())
      .then(function (r) { if (!r.ok) throw new Error(); return r.blob(); })
      .then(function (b) {
        if (SC.snapUrl) URL.revokeObjectURL(SC.snapUrl);
        SC.snapUrl = URL.createObjectURL(b);
        if (!document.querySelector('.scrim')) renderScreens();
      })
      .catch(function () {});
  }

  function openKeep(d) {
    var used = kept().map(function (k) { return k.colour; });
    var names = kept().map(function (k) { return k.name; });
    var st = {
      name: '',
      colour: Object.keys(COLOURS).filter(function (c) { return used.indexOf(c) < 0; })[0]
        || 'teal',
      shows: '',
      same: null,
    };
    var sheet = openSheet('keep-tpl');
    function q(id) { return sheet.root.querySelector('#' + id); }
    q('keep-lede').textContent =
      'The ' + (d.kind || 'screen') + ' is showing “New screen!” right now.';
    var input = q('keep-name');
    input.addEventListener('input', function () { st.name = input.value; draw(); });
    // Kept screens that are off now: maybe this is one of them again.
    var before = kept().filter(function (k) { return !k.home && !k.online; });
    q('keep-same').hidden = !before.length;
    function draw() {
      var same = q('keep-same-list');
      same.innerHTML = '';
      before.forEach(function (k) {
        same.appendChild(el('button', {
          type: 'button', class: 'chip', role: 'radio', text: k.name,
          'aria-checked': st.same === k ? 'true' : 'false',
          onclick: function () { st.same = st.same === k ? null : k; draw(); },
        }));
      });
      ['keep-name', 'keep-names', 'keep-colours', 'keep-shows'].forEach(function (id) {
        var n = q(id);
        n.style.opacity = st.same ? 0.35 : '';
        n.style.pointerEvents = st.same ? 'none' : '';
      });
      var chips = q('keep-names');
      chips.innerHTML = '';
      [d.kind || 'Tablet', 'Living Room', 'Office', 'Bedroom', 'Kitchen']
        .filter(function (n) { return names.indexOf(n) < 0; })
        .forEach(function (n) {
          chips.appendChild(el('button', {
            type: 'button', class: 'chip', role: 'radio', text: n,
            'aria-checked': st.name === n ? 'true' : 'false',
            onclick: function () { st.name = n; input.value = n; draw(); },
          }));
        });
      var cs = q('keep-colours');
      cs.innerHTML = '';
      Object.keys(COLOURS).forEach(function (c) {
        var b = el('button', {
          type: 'button', role: 'radio', 'aria-label': c,
          'aria-checked': st.colour === c ? 'true' : 'false',
          onclick: function () { st.colour = c; draw(); },
        });
        b.style.setProperty('--sc', COLOURS[c]);
        cs.appendChild(b);
      });
      var ch = q('keep-shows');
      ch.innerHTML = '';
      SHOWS.forEach(function (x) {
        ch.appendChild(el('button', {
          type: 'button', class: 'sc-choice', role: 'radio',
          'aria-checked': st.shows === x.id ? 'true' : 'false',
          onclick: function () { st.shows = x.id; draw(); },
        }, [
          sketch(planForShows(x.id, isTall(d)), d.viewport_w, d.viewport_h),
          el('b', { text: x.name }), el('span', { text: x.hint }),
        ]));
      });
      var name = st.name.trim();
      var go = q('keep-go');
      if (st.same) {
        go.disabled = false;
        go.style.opacity = 1;
        go.textContent = 'This is ' + st.same.name;
        return;
      }
      go.disabled = !name || !st.shows;
      go.style.opacity = go.disabled ? 0.45 : 1;
      go.textContent = !name ? 'Give it a name first'
        : !st.shows ? 'Pick what it shows' : 'Keep ' + name;
    }
    draw();
    q('keep-cancel').addEventListener('click', sheet.close);
    q('keep-go').addEventListener('click', function () {
      if (st.same) {
        var was = st.same.name;
        call('/api/devices/' + encodeURIComponent(d.id) + '/replace', 'POST', { old: st.same.id })
          .then(function () {
            sheet.close();
            toast(was + ' is back');
            return loadScreens().then(renderScreens);
          })
          .catch(failed('set up the screen'));
        return;
      }
      var name = st.name.trim();
      if (!name || !st.shows) return;
      call('/api/devices/' + encodeURIComponent(d.id) + '/keep', 'POST',
        { name: name, colour: st.colour, shows: st.shows })
        .then(function () {
          sheet.close();
          toast(name + ' is set up');
          return loadScreens().then(renderScreens);
        })
        .catch(failed('set up the screen'));
    });
  }

  // On a screen's own pages: the "Changing" bar, Find it, and This screen.
  function renderThisScreen() {
    var d = S.screen;
    var bar = $('changing');
    bar.hidden = false;
    bar.style.setProperty('--sc', colourOf(d));
    $('changing-t').textContent = 'Changing: ' + (d.name || 'this screen');
    $('find-it').hidden = false;
    var shows = showsOf(d);
    var chips = $('shows');
    chips.innerHTML = '';
    SHOWS.forEach(function (x) {
      chips.appendChild(el('button', {
        type: 'button', class: 'chip', role: 'radio', text: x.name,
        'aria-checked': shows === x.id ? 'true' : 'false',
        onclick: function () {
          if (shows === x.id) return;
          call('/api/devices/' + encodeURIComponent(d.id) + '/shows', 'PUT', { shows: x.id })
            .then(function (nd) { S.screen = nd; return refreshView(); })
            .then(function () { renderAll(); toast(d.name + ' now shows ' + x.name); })
            .catch(failed('change what it shows'));
        },
      }));
    });
    // Unset: everything on the kiosk, nothing on the others (api._popup_for).
    var popups = d.popups || (d.home ? 'all' : 'none');
    var pops = $('popups');
    pops.innerHTML = '';
    POPUPS.forEach(function (x) {
      pops.appendChild(el('button', {
        type: 'button', class: 'chip', role: 'radio', text: x.name,
        'aria-checked': popups === x.id ? 'true' : 'false',
        onclick: function () {
          if (popups !== x.id) saveScreen({ popups: x.id }, 'change the pop-ups');
        },
      }));
    });
    if (document.activeElement !== $('sc-rename')) $('sc-rename').value = d.name || '';
    $('sc-remove').hidden = !!d.home;
  }
  $('find-it').addEventListener('click', function () {
    call('/api/devices/' + encodeURIComponent(S.screen.id) + '/identify', 'POST')
      .then(function () { toast(S.screen.name + ' is flashing its name'); })
      .catch(failed('find the screen'));
  });
  $('sc-rename-go').addEventListener('click', function () {
    var name = $('sc-rename').value.trim();
    if (!name || name === S.screen.name) return;
    $('sc-rename').blur();
    saveScreen({ name: name }, 'rename the screen')
      .then(function () { toast('Renamed to ' + name); });
  });
  $('sc-remove').addEventListener('click', function () {
    confirmRemove(S.screen, function () { location.href = '/menu'; });
  });

  function theme(name) {
    return S.themes.filter(function (t) { return t.name === name; })[0] || null;
  }
  // What the screen is showing right now: the profile's theme, or its night
  // twin when the server has already switched to it.
  function shownTheme() {
    var base = theme(S.profile.theme);
    var live = theme(S.view && S.view.theme);
    if (base && live && base.night === live.name) return live;
    return live && live.name === S.profile.theme ? live : base || live;
  }
  // The screen's card order, switched-off cards included: they keep their
  // place, so switching one back on puts it where it was.
  function stack() {
    return (S.screen.card_stack || S.profile.card_stack || []).slice();
  }
  function offCards() {
    return (S.screen.cards_off || []).slice();
  }
  function heroId() {
    return S.view && S.view.hero && S.view.hero.kind === 'card' ? S.view.hero.card : null;
  }
  // The biggest box of a hand-placed layout, first in reading order on a tie.
  function gridHero(grid) {
    var best = null;
    grid.items.slice().sort(function (a, b) { return a.y - b.y || a.x - b.x; })
      .forEach(function (i) { if (!best || i.w * i.h > best.w * best.h) best = i; });
    return best;
  }
  function cardName(id) {
    var c = S.cards[id];
    if (c) return c.name;
    return id.replace(/-/g, ' ').replace(/^./, function (m) { return m.toUpperCase(); });
  }

  function rgb(hex) {
    var h = hex.replace('#', '');
    if (h.length === 3) h = h.replace(/./g, '$&$&');
    var n = parseInt(h.slice(0, 6), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function isDark(hex) {
    var c = rgb(hex);
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] < 128;
  }
  function tileColour(t, id) {
    var key = ACCENT[id] || 'generic';
    return (t.cards && (t.cards[key] || t.cards.generic)) || null;
  }

  // ── Dark mode (phone companion) ────────────────────────────────────
  function getSavedDarkMode() {
    try {
      var m = localStorage.getItem('pineda_menu_dark_mode');
      if (m) return m;
      var match = document.cookie.match(/(?:^|; )pineda_menu_dark_mode=([^;]*)/);
      if (match) return decodeURIComponent(match[1]);
    } catch (e) {}
    return 'dark';
  }

  function setDarkMode(mode, save) {
    if (save !== false) {
      try {
        localStorage.setItem('pineda_menu_dark_mode', mode);
        var exp = new Date(Date.now() + 365 * 24 * 3600 * 1000).toUTCString();
        var cookieVal = 'pineda_menu_dark_mode=' + encodeURIComponent(mode);
        document.cookie = cookieVal + '; expires=' + exp + '; path=/; SameSite=Lax';
      } catch (e) {}
    }
    var sysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var isDark = mode === 'dark' || (mode === 'system' && sysDark);
    document.documentElement.classList.toggle('dark-theme', isDark);
    document.documentElement.classList.toggle('light-theme', !isDark);
    document.documentElement.setAttribute('data-color-mode', mode);
    document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
    var themeColorMeta = $('theme-color');
    if (themeColorMeta) {
      themeColorMeta.setAttribute('content', isDark ? '#000000' : '#f7f6f2');
    }
    var btn = $('dark-toggle');
    if (btn) {
      var icon = btn.querySelector('.dark-icon') || btn;
      icon.textContent = isDark ? '🌙' : '☀️';
      btn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
      btn.title = isDark ? 'Dark mode (tap for light)' : 'Light mode (tap for dark)';
    }
  }

  function cycleDarkMode() {
    var cur = document.documentElement.getAttribute('data-color-mode') || getSavedDarkMode();
    var next = (cur === 'dark') ? 'light' : 'dark';
    setDarkMode(next, true);
  }

  // ── Paint ─────────────────────────────────────────────────────────
  function paint() {
    var t = shownTheme();
    if (!t) return;
    var root = document.documentElement.style;
    root.setProperty('--screen-stage', t.stage);
    root.setProperty('--screen-ink', t.on_stage);
    root.setProperty('--screen-ink-rgb', rgb(t.on_stage).join(', '));
    root.setProperty('--accent', t.accent);
    root.setProperty('--on-card', t.on_card);
  }

  function clockText() {
    var d = new Date();
    var h = d.getHours() % 12 || 12;
    return h + ':' + String(d.getMinutes()).padStart(2, '0');
  }

  function renderMini() {
    var t = shownTheme();
    var mini = $('mini');
    // The screen's own shape; a tall tablet's is kept short enough to leave
    // the page room under the pinned header.
    var vw = S.screen.viewport_w, vh = S.screen.viewport_h;
    if (vw && vh) {
      mini.style.aspectRatio = vw + ' / ' + vh;
      $('mini-frame').style.width =
        vh > vw ? 'calc(26vh * ' + (vw / vh).toFixed(3) + ' + 14px)' : '';
      $('mini-frame').style.marginInline = vh > vw ? 'auto' : '';
    }
    mini.innerHTML = '';
    if (S.screen.grid) return renderMiniGrid(t, mini, S.screen.grid);
    mini.style.gridTemplateColumns = '';
    var hero = heroId();
    var ids = (hero ? [hero] : []).concat(
      ((S.view && S.view.cards) || []).map(function (c) { return c.id; }),
    );
    var rest = Math.max(0, ids.length - (hero ? 5 : 0));
    var rows = (hero ? 2 : 0) + Math.ceil(rest / 4) || 1;
    mini.style.gridTemplateRows = 'repeat(' + rows + ', minmax(0, 1fr))';
    ids.forEach(function (id, i) {
      var tile = el('div', { class: 'tile' + (i === 0 && hero ? ' hero' : '') });
      var colour = t && tileColour(t, id);
      if (colour) tile.style.setProperty('--tile', colour);
      else tile.classList.add('plain');
      if (id === 'clock') {
        tile.classList.add('clock');
        tile.appendChild(el('span', { text: clockText() }));
      } else {
        if (id === 'photo' && S.photo) {
          tile.classList.add('photo');
          tile.style.backgroundImage =
            'url("/api/photos/' + encodeURIComponent(S.photo) + '/thumb")';
        }
        tile.appendChild(el('span', { text: cardName(id) }));
      }
      mini.appendChild(tile);
    });
    mini.style.setProperty('--dim', String(1 - (S.screen.brightness || 1)));
  }

  // A hand-placed layout: every tile in its own box, as on the screen.
  function renderMiniGrid(t, mini, grid) {
    var rows = grid.items.reduce(function (n, i) { return Math.max(n, i.y + i.h); }, 1);
    var big = gridHero(grid);
    mini.style.gridTemplateColumns = 'repeat(' + grid.cols + ', minmax(0, 1fr))';
    mini.style.gridTemplateRows = 'repeat(' + rows + ', minmax(0, 1fr))';
    grid.items.forEach(function (item) {
      var id = item.card;
      var tile = el('div', { class: 'tile placed' + (big && big.card === id ? ' big' : '') });
      tile.style.gridColumn = (item.x + 1) + ' / span ' + item.w;
      tile.style.gridRow = (item.y + 1) + ' / span ' + item.h;
      var colour = t && tileColour(t, id);
      if (colour) tile.style.setProperty('--tile', colour);
      else tile.classList.add('plain');
      if (id === 'photo' && S.photo) {
        tile.classList.add('photo');
        tile.style.backgroundImage =
          'url("/api/photos/' + encodeURIComponent(S.photo) + '/thumb")';
      }
      tile.appendChild(el('span', { text: id === 'clock' ? clockText() : cardName(id) }));
      mini.appendChild(tile);
    });
    mini.style.setProperty('--dim', String(1 - (S.screen.brightness || 1)));
  }

  // ── Look ──────────────────────────────────────────────────────────
  function renderLook() {
    var list = $('swatches');
    list.innerHTML = '';
    S.themes.filter(function (t) { return !/_night$/.test(t.name); }).forEach(function (t) {
      var on = t.name === S.profile.theme;
      var scr = el('span', { class: 'scr', 'aria-hidden': 'true' });
      scr.style.background = t.stage;
      ['weather', 'clock', 'affirmation'].forEach(function (k) {
        var i = el('i');
        i.style.background = (t.cards && t.cards[k]) || t.accent;
        scr.appendChild(i);
      });
      list.appendChild(el('li', {}, [
        el('button', {
          type: 'button', class: 'swatch', role: 'radio', 'aria-checked': on ? 'true' : 'false',
          onclick: function () { if (!on) saveProfile({ theme: t.name }, 'change the theme'); },
        }, [scr, el('span', { class: 'name display', text: t.label })]),
        t.custom ? el('button', {
          type: 'button', class: 'swatch-edit', text: 'Edit',
          'aria-label': 'Edit ' + t.label,
          onclick: function () { openMaker(t); },
        }) : null,
      ]));
    });
    list.appendChild(el('li', {}, [
      el('button', {
        type: 'button', class: 'swatch make', onclick: function () { openMaker(null); },
      }, [
        el('span', {
          class: 'scr', 'aria-hidden': 'true',
          html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"'
            + ' stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
        }),
        el('span', { class: 'name display', text: 'Make your own' }),
      ]),
    ]));
    var cur = theme(S.profile.theme);
    $('blurb').textContent = cur
      ? cur.blurb + (cur.night ? ' Turns to its night colours at sundown.' : '')
      : '';

    var chips = $('clocks');
    chips.innerHTML = '';
    var face = S.profile.clock_face || '';
    CLOCKS.forEach(function (c) {
      chips.appendChild(el('button', {
        type: 'button', class: 'chip', role: 'radio', text: c[1],
        'aria-checked': c[0] === face ? 'true' : 'false',
        onclick: function () { saveProfile({ clock_face: c[0] }, 'change the clock'); },
      }));
    });

    var fonts = $('fonts');
    fonts.innerHTML = '';
    var font = S.profile.font || '';
    FONTS.forEach(function (f) {
      var chip = el('button', {
        type: 'button', class: 'chip', role: 'radio', text: f[1],
        'aria-checked': f[0] === font ? 'true' : 'false',
        onclick: function () { saveProfile({ font: f[0] }, 'change the font'); },
      });
      // Each name in its own face, so the chip is the specimen.
      if (f[0]) chip.style.fontFamily = specimen(f[0]);
      fonts.appendChild(chip);
    });

    $('anim-bg').checked = !!S.profile.animated_background;

    var glass = cur && cur.surface === 'glass';
    $('wall-box').hidden = !glass;
    if (glass) refreshWallpaper();
  }

  function refreshWallpaper() {
    fetch('/api/wallpaper', { method: 'HEAD' }).then(function (r) {
      $('wall-img').hidden = !r.ok;
      $('wall-remove').hidden = !r.ok;
      if (r.ok) $('wall-img').src = '/api/wallpaper?v=' + Date.now();
    });
  }

  // ── Cards ─────────────────────────────────────────────────────────
  function editable(setting) {
    if (setting.type === 'list') {
      return Array.isArray(setting.default) && setting.default.length > 0 &&
        setting.default.every(function (v) { return typeof v === 'string'; });
    }
    var simple = ['integer', 'number', 'boolean', 'enum', 'string', 'timerange', 'beats'];
    return simple.indexOf(setting.type) >= 0;
  }

  function settingsFor(id) {
    var m = S.cards[id];
    if (!m) return [];
    return Object.keys(m.settings || {}).filter(function (k) { return editable(m.settings[k]); });
  }

  // Which cards are on this screen: the hand-placed layout's, else the
  // automatic stack minus the switched-off ones.
  function onScreen() {
    if (S.screen.grid) return S.screen.grid.items.map(function (i) { return i.card; });
    var off = offCards();
    return stack().filter(function (id) { return off.indexOf(id) < 0; });
  }

  // Positions and on/off live in the layout builder (/layout); here each
  // card that has something to set is a chip that opens its settings.
  function renderCards() {
    $('arrange').href = '/layout?screen=' + encodeURIComponent(S.screen.id);
    var shown = onScreen();
    var ids = Object.keys(S.cards).filter(function (id) {
      var c = S.cards[id];
      return !HIDDEN_CARDS[id] && c.status === 'ready' && settingsFor(id).length;
    });
    // This screen's cards in the order it shows them; the rest by name.
    var here = shown.filter(function (id) { return ids.indexOf(id) >= 0; });
    var rest = ids.filter(function (id) { return here.indexOf(id) < 0; })
      .sort(function (a, b) { return cardName(a).localeCompare(cardName(b)); });
    fillChips($('card-list'), here, true);
    fillChips($('other-list'), rest, false);
    $('others').hidden = !rest.length;
    $('others-n').textContent = '(' + rest.length + ')';
  }

  function fillChips(list, ids, here) {
    var t = shownTheme();
    list.innerHTML = '';
    ids.forEach(function (id) {
      var dot = el('i', { 'aria-hidden': 'true' });
      dot.style.background = (t && tileColour(t, id)) || 'var(--faint)';
      list.appendChild(el('li', {}, [
        el('button', {
          type: 'button', class: 'card-chip', 'aria-haspopup': 'dialog',
          onclick: function () { openCard(id, here); },
        }, [dot, el('span', { text: cardName(id) })]),
      ]));
    });
  }

  function openCard(id, here) {
    var m = S.cards[id];
    var sheet = openSheet('card-tpl');
    var q = function (x) { return sheet.root.querySelector('#' + x); };
    q('card-h').textContent = cardName(id);
    q('card-desc').textContent = m.description || '';
    q('card-desc').hidden = !m.description;
    q('card-where').textContent = here ? ''
      : "This card isn't on this screen. Add it with Arrange this screen.";
    q('card-where').hidden = here;
    q('card-done').addEventListener('click', sheet.close);
    var box = q('card-fields');
    call('/api/cards/' + encodeURIComponent(id) + '/settings').then(function (res) {
      var values = res.values || {};
      settingsFor(id).forEach(function (k) {
        var spec = m.settings[k];
        var v = values[k] !== undefined ? values[k] : spec.default;
        box.appendChild(settingField(id, k, spec, v));
      });
    }).catch(failed('load its settings'));
  }

  function saveCardSetting(id, key, value) {
    var values = {};
    values[key] = value;
    return call('/api/cards/' + encodeURIComponent(id) + '/settings', 'PUT', { values: values })
      .then(function () { toast('Saved'); return true; })
      .catch(function () { failed('save that setting')(); return false; });
  }

  function settingField(id, key, spec, value) {
    var label = spec.title || key;
    var input;
    if (spec.type === 'beats') return beatsField(id, key, spec, value);
    if (spec.type === 'boolean') {
      input = el('input', {
        type: 'checkbox', class: 'switch', role: 'switch', checked: value ? 'checked' : null,
        onchange: function (e) {
          var box = e.target;
          saveCardSetting(id, key, box.checked).then(function (ok) {
            if (!ok) box.checked = !box.checked;
          });
        },
      });
      return el('label', { class: 'field inline' }, [el('span', { text: label }), input]);
    }
    if (spec.type === 'enum') {
      input = el('select', {
        class: 'text-in',
        onchange: function (e) { saveCardSetting(id, key, e.target.value); },
      }, (spec.enum || []).map(function (o) {
        return el('option', {
          value: o, text: o.charAt(0).toUpperCase() + o.slice(1),
          selected: o === value ? 'selected' : null,
        });
      }));
    } else if (spec.type === 'timerange') {
      var parts = String(value || '').split('-');
      var from = el('input', {
        type: 'time', class: 'text-in', value: parts[0] || '', 'aria-label': label + ' from',
      });
      var to = el('input', {
        type: 'time', class: 'text-in', value: parts[1] || '', 'aria-label': label + ' to',
      });
      var save = function () {
        if (from.value && to.value) saveCardSetting(id, key, from.value + '-' + to.value);
      };
      from.addEventListener('change', save);
      to.addEventListener('change', save);
      return el('div', { class: 'field' }, [
        el('span', { text: label }),
        el('div', { class: 'span' }, [from, el('span', { text: 'to' }), to]),
      ]);
    } else if (spec.type === 'integer' || spec.type === 'number') {
      input = el('input', {
        type: 'number', class: 'text-in', inputmode: 'numeric', value: value,
        min: spec.min, max: spec.max, step: spec.type === 'integer' ? 1 : 'any',
        onchange: function (e) {
          var n = Number(e.target.value);
          if (e.target.value === '' || isNaN(n)) return;
          if (spec.min !== null && n < spec.min) n = spec.min;
          if (spec.max !== null && n > spec.max) n = spec.max;
          e.target.value = n;
          saveCardSetting(id, key, spec.type === 'integer' ? Math.round(n) : n);
        },
      });
    } else if (spec.type === 'list') {
      input = el('input', {
        type: 'text', class: 'text-in', value: (value || []).join(', '),
        onchange: function (e) {
          saveCardSetting(id, key, e.target.value.split(',').map(function (s) {
            return s.trim();
          }).filter(Boolean));
        },
      });
      label += ' (separate with commas)';
    } else {
      input = el('input', {
        type: 'text', class: 'text-in', value: value || '',
        onchange: function (e) { saveCardSetting(id, key, e.target.value.trim()); },
      });
    }
    return el('label', { class: 'field' }, [el('span', { text: label }), input]);
  }

  // The news card's beats. Every edit saves the whole list; the server
  // re-sorts the stories it already has, so the screen changes in seconds.
  function beatsField(id, key, spec, value) {
    var beats = Array.isArray(value) ? JSON.parse(JSON.stringify(value)) : [];
    var sources = spec.enum || [];
    var labels = spec.labels || {};
    var open = {};
    var box = el('div', { class: 'beats' });
    var save = function () { saveCardSetting(id, key, beats); };
    var words = function (text) {
      return text.split(/[,\\n]/).map(function (w) { return w.trim(); }).filter(Boolean);
    };

    function area(text, value, rows, onsave, hint) {
      return el('label', { class: 'field' }, [
        el('span', { text: text }),
        el('textarea', {
          class: 'text-in', rows: rows, placeholder: hint || null,
          onchange: function (e) { onsave(e.target.value); save(); },
        }, [document.createTextNode(value)]),
      ]);
    }

    function render() {
      box.innerHTML = '';
      beats.forEach(function (b, i) {
        var head = el('summary', { class: b.enabled === false ? 'off' : null }, [
          el('span', { text: b.name }),
          el('small', { text: b.sources.length + ' feeds' }),
        ]);
        var feeds = el('div', { class: 'feeds', role: 'group', 'aria-label': 'Feeds' },
          sources.map(function (s) {
            return el('label', {}, [
              el('input', {
                type: 'checkbox', checked: b.sources.indexOf(s) >= 0 ? 'checked' : null,
                onchange: function (e) {
                  b.sources = e.target.checked ? b.sources.concat([s])
                    : b.sources.filter(function (x) { return x !== s; });
                  head.lastChild.textContent = b.sources.length + ' feeds';
                  save();
                },
              }),
              el('span', { text: labels[s] || s }),
            ]);
          }));
        var number = function (text, field, fallback, max) {
          return el('label', { class: 'field' }, [
            el('span', { text: text }),
            el('input', {
              type: 'number', class: 'text-in', inputmode: 'numeric', min: 1, max: max,
              value: b[field] || fallback,
              onchange: function (e) {
                var n = Math.round(Number(e.target.value));
                if (!n) return;
                b[field] = Math.min(max, Math.max(1, n));
                save();
              },
            }),
          ]);
        };
        var details = el('details', {
          class: 'beat', open: open[i] ? 'open' : null,
          ontoggle: function () { open[i] = details.open; },
        }, [head, el('div', { class: 'beat-body' }, [
          el('label', { class: 'field inline' }, [
            el('span', { text: 'Show this beat' }),
            el('input', {
              type: 'checkbox', class: 'switch', role: 'switch',
              checked: b.enabled !== false ? 'checked' : null,
              onchange: function (e) {
                b.enabled = e.target.checked;
                head.className = b.enabled ? '' : 'off';
                save();
              },
            }),
          ]),
          el('label', { class: 'field' }, [
            el('span', { text: 'Name' }),
            el('input', {
              type: 'text', class: 'text-in', value: b.name,
              onchange: function (e) {
                b.name = e.target.value.trim() || b.name;
                head.firstChild.textContent = b.name;
                save();
              },
            }),
          ]),
          el('div', { class: 'two' }, [
            number('Turns per round', 'weight', 1, 5),
            number('Oldest story (hours)', 'maxAgeHours', 24, 168),
          ]),
          area('Topics', (b.keywords || []).join(', '), 4,
            function (v) { b.keywords = words(v); },
            'Leave empty for every story from these feeds'),
          area('Leave out stories about', (b.exclude || []).join(', '), 2,
            function (v) { b.exclude = words(v); }),
          el('p', { class: 'note', text: 'Separate with commas. End a word with * to ' +
            'match its start (immigra* finds immigrant and immigration). Write it in ' +
            'capitals to match capitals only (ICE, not ice).' }),
          el('div', { class: 'field' }, [el('span', { text: 'Feeds' }), feeds]),
          area('Other RSS feeds (one address per line)',
            b.sources.filter(function (s) { return s.indexOf('https://') === 0; }).join('\\n'), 2,
            function (v) {
              var known = b.sources.filter(function (s) { return sources.indexOf(s) >= 0; });
              b.sources = known.concat(words(v).filter(function (s) {
                return s.indexOf('https://') === 0;
              }));
              head.lastChild.textContent = b.sources.length + ' feeds';
            }, 'https://…'),
          el('div', { class: 'btns' }, [el('button', {
            type: 'button', class: 'pill', text: 'Remove ' + b.name,
            onclick: function () {
              if (!window.confirm('Remove the ' + b.name + ' beat?')) return;
              beats.splice(i, 1);
              open = {};
              render();
              save();
            },
          })]),
        ])]);
        box.appendChild(details);
      });
      box.appendChild(el('div', { class: 'btns' }, [el('button', {
        type: 'button', class: 'pill', text: 'Add a beat',
        onclick: function () {
          beats.push({
            name: 'New beat', enabled: true, weight: 1, maxAgeHours: 24,
            sources: [], keywords: [], exclude: [],
          });
          open[beats.length - 1] = true;
          render();
          save();
        },
      })]));
    }

    render();
    return el('div', { class: 'field' }, [el('span', { text: spec.title || key }), box]);
  }

  function photoClockSummary() {
    var pc = S.screen.photo_clock || {};
    var glassMap = {
      liquid: 'Liquid glass', frosted: 'Frosted glass', crystal: 'Crystal glass', flat: 'Flat glass',
      mesh: 'Blend colours', match: 'Photo colours', opposite: 'Opposite colours',
      chrome: 'Chrome', print: 'Print ink', neon: 'Neon'
    };
    var parts = [];
    var f = S.screen.night_clock_font;
    if (f) {
      var found = FONTS.filter(function (x) { return x[0] === f; })[0];
      if (found) parts.push(found[1]);
    }
    parts.push(glassMap[pc.glass] || 'Liquid glass');
    parts.push(pc.layout === 'stack' ? 'Stacked' : 'Row');
    if (pc.drift) parts.push('Drift');
    if (pc.weather) parts.push('Weather');
    return parts.join(' · ');
  }

  function renderPhotoClockSec() {
    var held = S.screen.night_clock !== false && !!S.screen.night_clock_hold;
    var isPhoto = S.screen.night_clock_photo !== false;
    var badge = $('pc-status-badge');
    if (badge) {
      if (held && isPhoto) {
        badge.textContent = 'Active now';
        badge.className = 'pc-status-badge on';
      } else if (held) {
        badge.textContent = 'Clock active';
        badge.className = 'pc-status-badge on';
      } else {
        badge.textContent = 'Off';
        badge.className = 'pc-status-badge';
      }
    }
    var sum = $('pc-summary-val');
    if (sum) sum.textContent = photoClockSummary();
  }

  // ── Night ─────────────────────────────────────────────────────────
  function renderScreen() {
    renderPhotoClockSec();
    var nc = S.screen.night_clock !== false;
    $('nc-on').checked = nc;
    $('nc-hold').checked = !!S.screen.night_clock_hold;
    if ($('nc-hold-box')) $('nc-hold-box').hidden = !nc;
    var dark = !!(S.screen.blackout_start && S.screen.blackout_end);
    $('night-on').checked = dark;
    $('night-span').hidden = !dark;
    $('night-from').value = S.screen.blackout_start || '22:00';
    $('night-to').value = S.screen.blackout_end || '06:00';
    $('peek-box').hidden = !nc;
    radioChips($('peeks'), PEEKS, S.screen.peek_s || 60, function (v) {
      saveScreen({ peek_s: v }, 'change that', true);
    });
    var dim = !!(S.screen.dim_start && S.screen.dim_end);
    $('dim-on').checked = dim;
    $('dim-box').hidden = !dim;
    $('dim-from').value = S.screen.dim_start || '21:00';
    $('dim-to').value = S.screen.dim_end || '07:00';
    $('dim-level').value = S.screen.dim_level;
    $('dim-level-v').textContent = Math.round(S.screen.dim_level * 100) + '%';
    $('frame-inset').value = S.screen.frame_inset || 0;
    $('frame-inset-v').textContent = frameLabel(S.screen.frame_inset);
  }

  // ── Timing ────────────────────────────────────────────────────────
  var PACES = [['relaxed', 'Relaxed'], ['normal', 'Normal'], ['brisk', 'Brisk']];
  var HOLDS = [[10, '10 s'], [20, '20 s'], [60, '1 min'], [300, '5 min']];
  var PEEKS = [[30, '30 s'], [60, '1 min'], [120, '2 min'], [300, '5 min']];

  /** A row of radio chips; a saved value that isn't one of them gets its own. */
  function radioChips(box, options, value, onpick) {
    if (!options.some(function (o) { return o[0] === value; })) {
      options = options.concat([[value, value + ' s']]);
    }
    box.innerHTML = '';
    options.forEach(function (o) {
      box.appendChild(el('button', {
        type: 'button', class: 'chip', role: 'radio', text: o[1],
        'aria-checked': o[0] === value ? 'true' : 'false',
        onclick: function () { if (o[0] !== value) onpick(o[0]); },
      }));
    });
  }

  function renderTiming() {
    radioChips($('paces'), PACES, S.profile.pace || 'normal', function (v) {
      saveProfile({ pace: v }, 'change the speed', true);
    });
    radioChips($('holds'), HOLDS, S.profile.photo_hold_s || 20, function (v) {
      saveProfile({ photo_hold_s: v }, 'change the photo time', true);
    });
  }

  $('anim-bg').addEventListener('change', function (e) {
    saveProfile({ animated_background: e.currentTarget.checked }, 'change the background');
  });
  $('nc-on').addEventListener('change', function (e) {
    var on = e.target.checked;
    if ($('nc-hold-box')) $('nc-hold-box').hidden = !on;
    // Switching the night clock off lets go of a held clock too.
    var patch = on ? { night_clock: true } : { night_clock: false, night_clock_hold: false };
    saveScreen(patch, 'change the night clock', true);
  });
  $('nc-hold').addEventListener('change', function (e) {
    var on = e.target.checked;
    var patch = on
      ? { night_clock: true, night_clock_hold: true, night_clock_photo: true, alternate: false }
      : { night_clock_hold: false };
    saveScreen(patch, 'change Photo Clock', true);
  });
  var openPcBtn = $('settings-open-pc');
  if (openPcBtn) {
    openPcBtn.addEventListener('click', function () {
      openClockStyle();
    });
  }
  function saveNight() {
    var on = $('night-on').checked;
    $('night-span').hidden = !on;
    var from = $('night-from').value;
    var to = $('night-to').value;
    if (on && (!from || !to)) return;
    var patch = { blackout_start: on ? from : '', blackout_end: on ? to : '' };
    saveScreen(patch, 'save the overnight hours', true);
  }
  $('night-on').addEventListener('change', saveNight);
  $('night-from').addEventListener('change', saveNight);
  $('night-to').addEventListener('change', saveNight);
  function saveDim() {
    var on = $('dim-on').checked;
    $('dim-box').hidden = !on;
    var from = $('dim-from').value;
    var to = $('dim-to').value;
    if (on && (!from || !to)) return;
    saveScreen({ dim_start: on ? from : '', dim_end: on ? to : '' }, 'save the dimming', true);
  }
  $('dim-on').addEventListener('change', saveDim);
  $('dim-from').addEventListener('change', saveDim);
  $('dim-to').addEventListener('change', saveDim);
  $('dim-level').addEventListener('input', function (e) {
    $('dim-level-v').textContent = Math.round(e.target.value * 100) + '%';
  });
  $('dim-level').addEventListener('change', function (e) {
    saveScreen({ dim_level: Number(e.target.value) }, 'change the dimming', true);
  });
  function frameLabel(v) {
    return Number(v) ? v + '% each side' : 'None';
  }
  $('frame-inset').addEventListener('input', function (e) {
    $('frame-inset-v').textContent = frameLabel(e.target.value);
  });
  $('frame-inset').addEventListener('change', function (e) {
    saveScreen({ frame_inset: Number(e.target.value) }, 'change the frame', true);
  });

  // ── Saving ────────────────────────────────────────────────────────
  function refreshView() {
    return call('/api/view/' + encodeURIComponent(S.screen.id) + '?touch=false')
      .then(function (v) { S.view = v; });
  }
  function renderAll() {
    paint();
    renderMini();
    renderHome();
    renderLook();
    renderCards();
    renderScreen();
    renderTiming();
    renderThisScreen();
  }
  // A save that fails redraws from the last saved state, so a switch or
  // chip never shows something the screen isn't doing.
  function undoFailed(what) {
    var say = failed(what);
    return function () { renderAll(); say(); };
  }
  function saveProfile(patch, what, quietly) {
    var prev = Object.assign({}, S.profile);
    Object.assign(S.profile, patch);
    renderAll();
    return call('/api/profiles/' + encodeURIComponent(prev.id), 'PATCH', patch)
      .then(function (p) { S.profile = p; return refreshView(); })
      .then(function () {
        renderAll();
        if (quietly) toast('Saved');
      })
      .catch(function (err) {
        S.profile = prev;
        renderAll();
        undoFailed(what)(err);
      });
  }
  function saveScreen(patch, what, quietly) {
    var prev = Object.assign({}, S.screen);
    Object.assign(S.screen, patch);
    renderAll();
    return call('/api/devices/' + encodeURIComponent(prev.id), 'PATCH', patch)
      .then(function (d) { S.screen = d; return refreshView(); })
      .then(function () {
        renderAll();
        if (quietly) toast('Saved');
      })
      .catch(function (err) {
        S.screen = prev;
        renderAll();
        undoFailed(what)(err);
      });
  }

  $('wall-file').addEventListener('change', function () {
    var file = this.files && this.files[0];
    if (!file) return;
    $('wall-pick').classList.add('busy');
    var fd = new FormData();
    fd.append('file', file);
    fetch('/api/wallpaper', { method: 'PUT', body: fd })
      .then(function (r) {
        if (!r.ok) throw new Error();
        refreshWallpaper();
        toast('Background changed');
      })
      .catch(failed('use that picture'))
      .finally(function () {
        $('wall-pick').classList.remove('busy');
        $('wall-file').value = '';
      });
  });
  $('wall-remove').addEventListener('click', function () {
    fetch('/api/wallpaper', { method: 'DELETE' })
      .then(function (r) { if (r.ok) { refreshWallpaper(); toast('Background removed'); } })
      .catch(failed('remove the background'));
  });

  // ── Sheets ────────────────────────────────────────────────────────
  var lastFocus = null;
  function openSheet(tplId, onClose) {
    lastFocus = document.activeElement;
    var scrim = $(tplId).content.firstElementChild.cloneNode(true);
    document.body.appendChild(scrim);
    document.body.style.overflow = 'hidden';
    var closed = false;
    function close() {
      if (closed) return;
      closed = true;
      if (onClose) onClose();
      document.body.style.overflow = '';
      document.removeEventListener('keydown', onKey);
      if (lastFocus) lastFocus.focus();
      if (REDUCED.matches) return scrim.remove();
      scrim.classList.add('closing');
      setTimeout(function () { scrim.remove(); }, 190);
    }
    function onKey(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);
    scrim.addEventListener('click', function (e) { if (e.target === scrim) close(); });
    return { root: scrim, close: close };
  }

  var RESTARTS = {
    display: {
      title: 'Restart the display?', path: '/api/control/restart-display',
      done: 'Restarting the display',
      after: 'The screen goes dark for a moment, then comes back on its own.',
    },
    system: {
      title: 'Restart the Raspberry Pi?', path: '/api/control/restart-system',
      done: 'Restarting the Raspberry Pi',
      after: 'The screen is off for a minute or two, then comes back on its own.',
    },
  };

  function openPin(kind) {
    var job = RESTARTS[kind];
    var sheet = openSheet('pin-tpl');
    var q = function (id) { return sheet.root.querySelector('#' + id); };
    var entered = '';
    var busy = false;
    q('pin-h').textContent = job.title;
    q('pin-lede').textContent = S.pinRequired
      ? 'Enter the PIN.'
      : 'Nobody has set a PIN, so this just asks first.';
    var dots = q('pin-dots');
    var pad = q('pin-pad');
    var msg = q('pin-msg');
    var go = q('pin-go');

    function show() {
      Array.prototype.forEach.call(dots.children, function (d, i) {
        d.classList.toggle('on', i < entered.length);
      });
    }
    function finished() {
      q('pin-h').textContent = job.done;
      q('pin-lede').textContent = job.after;
      dots.hidden = true;
      pad.hidden = true;
      go.hidden = true;
      msg.textContent = '';
      q('pin-cancel').textContent = 'Done';
      q('pin-cancel').focus();
    }
    function send(pin) {
      busy = true;
      msg.textContent = 'Checking…';
      var headers = pin ? { 'x-control-pin': pin } : {};
      fetch(job.path, { method: 'POST', headers: headers })
        .then(function (r) {
          if (r.ok) return finished();
          entered = '';
          show();
          if (r.status === 403) {
            msg.textContent = "That PIN didn't work. Try again.";
            dots.classList.remove('wrong');
            void dots.offsetWidth;
            dots.classList.add('wrong');
          } else if (r.status === 429) {
            msg.textContent = 'Too many tries. Wait a minute, then try again.';
          } else {
            msg.textContent = "The screen didn't respond to the restart (" + r.status + ').';
          }
        })
        .catch(function () { msg.textContent = 'No connection. Check the Wi-Fi and try again.'; })
        .finally(function () { busy = false; });
    }
    function press(d) {
      if (busy) return;
      if (d === 'back') { entered = entered.slice(0, -1); show(); return; }
      if (entered.length >= 6) return;
      entered += d;
      msg.textContent = '';
      show();
      if (entered.length === 6) send(entered);
    }

    if (S.pinRequired) {
      ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'back'].forEach(function (d) {
        if (!d) { pad.appendChild(el('span')); return; }
        pad.appendChild(el('button', {
          type: 'button', class: 'key' + (d === 'back' ? ' plain' : ''),
          text: d === 'back' ? 'Delete' : d,
          onclick: function () { press(d); },
        }));
      });
      sheet.root.addEventListener('keydown', function (e) {
        if (/^[0-9]$/.test(e.key)) press(e.key);
        else if (e.key === 'Backspace') press('back');
      });
      pad.querySelector('.key').focus();
    } else {
      dots.hidden = true;
      pad.hidden = true;
      go.hidden = false;
      go.textContent = kind === 'display' ? 'Restart the display' : 'Restart the Raspberry Pi';
      go.addEventListener('click', function () { if (!busy) send(''); });
      go.focus();
    }
    q('pin-cancel').addEventListener('click', sheet.close);
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-restart]'), function (b) {
    b.addEventListener('click', function () { openPin(b.getAttribute('data-restart')); });
  });

  // ── Theme maker ───────────────────────────────────────────────────
  var WELLS = [
    ['stage', 'Background', 'Behind everything'],
    ['accent', 'Highlight', 'Timers, progress bars and small details'],
    ['weather', 'Most cards', 'Weather, calendar and the rest'],
    ['clock', 'Clock card', 'Also the forecast and countdowns'],
    ['affirmation', 'Quote card', 'Also the traffic cameras'],
  ];
  // Same rule as the server (themes.ink_for): light or dark writing,
  // whichever stands out more.
  function lum(hex) {
    return rgb(hex).map(function (c) {
      var v = c / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    }).reduce(function (a, v, i) { return a + v * [0.2126, 0.7152, 0.0722][i]; }, 0);
  }
  function inkFor(hexes) {
    var l = hexes.reduce(function (a, h) { return a + lum(h); }, 0) / hexes.length;
    return (l + 0.05) / (lum('#221d1a') + 0.05) > (lum('#f7f2ea') + 0.05) / (l + 0.05)
      ? '#221d1a' : '#f7f2ea';
  }

  function contrast(a, b) {
    var la = lum(a);
    var lb = lum(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  }
  function mix(hex, to, t) {
    var a = rgb(hex);
    var b = rgb(to);
    return '#' + a.map(function (v, i) {
      return ('0' + Math.round(v + (b[i] - v) * t).toString(16)).slice(-2);
    }).join('');
  }
  // The same hue, lightened or darkened (whichever needs less) just enough
  // that ratioOf(hex) clears min.
  function readable(hex, ratioOf, min) {
    if (ratioOf(hex) >= min) return hex;
    for (var i = 1; i <= 100; i++) {
      var up = mix(hex, '#ffffff', i / 100);
      var down = mix(hex, '#000000', i / 100);
      var ru = ratioOf(up);
      var rd = ratioOf(down);
      if (ru >= min || rd >= min) return ru >= rd ? up : down;
    }
    return hex;
  }
  function hsvHex(h, s, v) {
    function f(n) {
      var k = (n + h / 60) % 6;
      return v - v * s * Math.max(0, Math.min(k, 4 - k, 1));
    }
    return '#' + [f(5), f(3), f(1)].map(function (x) {
      return ('0' + Math.round(x * 255).toString(16)).slice(-2);
    }).join('');
  }
  function hexHsv(hex) {
    var c = rgb(hex).map(function (x) { return x / 255; });
    var max = Math.max(c[0], c[1], c[2]);
    var d = max - Math.min(c[0], c[1], c[2]);
    var h = 0;
    if (d) {
      if (max === c[0]) h = ((c[1] - c[2]) / d + 6) % 6;
      else if (max === c[1]) h = (c[2] - c[0]) / d + 2;
      else h = (c[0] - c[1]) / d + 4;
    }
    return { h: h * 60, s: max ? d / max : 0, v: max };
  }

  // ── Colour wheel ──────────────────────────────────────────────────
  // Hue round the disc, saturation out from the middle, brightness on the
  // slider (drawn as a black veil over the disc: in HSV, dimming is just
  // scaling). "Keep it readable" nudges the pick lighter or darker until
  // o.ratioOf(hex) clears o.min; the knob stays where the finger left it.
  // o.free: any colour goes (a tint, say), so no guard.
  function colourWheel(o) {
    var hsv = hexHsv(o.value);
    var guard = !o.free;
    var size = 520; // canvas pixels; drawn once
    var canvas = el('canvas', { width: size, height: size });
    var dim = el('div', { class: 'cw-dim' });
    var knob = el('div', { class: 'cw-knob' });
    var disc = el('div', {
      class: 'cw-disc', tabindex: '0', role: 'application',
      'aria-label': 'Colour wheel. Arrow keys: left and right turn the colour, '
        + 'up and down make it stronger or softer.',
    }, [canvas, dim, knob]);
    var slider = el('input', {
      class: 'cw-v', type: 'range', min: '0', max: '100', 'aria-label': 'Brightness',
    });
    var hexIn = el('input', {
      class: 'text-in', maxlength: '7', autocomplete: 'off', spellcheck: 'false',
      'aria-label': 'Colour code',
    });
    var out = el('div', { class: 'cw-out' });
    var note = el('small');
    var sw = el('input', {
      type: 'checkbox', class: 'switch', role: 'switch', checked: 'checked',
      'aria-label': 'Keep it readable',
    });
    var node = el('div', { class: 'cw' }, [
      disc, slider,
      el('div', { class: 'cw-row' }, [out, hexIn]),
      o.free ? null : el('label', { class: 'cw-guard' }, [
        el('span', {}, [document.createTextNode('Keep it readable'), note]), sw,
      ]),
    ]);

    var ctx = canvas.getContext('2d');
    var img = ctx.createImageData(size, size);
    var r0 = size / 2;
    for (var y = 0; y < size; y++) {
      for (var x = 0; x < size; x++) {
        var dx = x - r0 + 0.5;
        var dy = y - r0 + 0.5;
        var r = Math.sqrt(dx * dx + dy * dy) / r0;
        if (r > 1.01) continue;
        var c = rgb(hsvHex((Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360, Math.min(r, 1), 1));
        var i = (y * size + x) * 4;
        img.data[i] = c[0]; img.data[i + 1] = c[1]; img.data[i + 2] = c[2];
        img.data[i + 3] = r > 1 ? Math.round((1.01 - r) * 100 * 255) : 255;
      }
    }
    ctx.putImageData(img, 0, 0);

    function picked() { return hsvHex(hsv.h, hsv.s, hsv.v); }
    function shown() { return guard ? readable(picked(), o.ratioOf, o.min) : picked(); }
    function draw(fromText) {
      var a = hsv.h * Math.PI / 180;
      knob.style.left = (50 + 50 * hsv.s * Math.cos(a)) + '%';
      knob.style.top = (50 + 50 * hsv.s * Math.sin(a)) + '%';
      knob.style.background = picked();
      dim.style.opacity = String(1 - hsv.v);
      slider.value = String(Math.round(hsv.v * 100));
      slider.style.background = 'linear-gradient(to right, #000, ' + hsvHex(hsv.h, hsv.s, 1) + ')';
      var hex = shown();
      out.style.background = hex;
      if (!fromText) hexIn.value = hex.toUpperCase();
      if (o.free) return hex;
      var ratio = o.ratioOf(hex);
      var text = ratio.toFixed(1) + ':1 ' + o.against;
      if (hex !== picked()) {
        text += lum(hex) > lum(picked()) ? ' · lightened to read' : ' · darkened to read';
      } else if (ratio < o.min) {
        text += ' · hard to read';
      }
      note.textContent = text;
      note.className = ratio < o.min ? 'low' : '';
      return hex;
    }
    function changed(fromText) { o.onInput(draw(fromText)); }

    function pointAt(e) {
      var b = disc.getBoundingClientRect();
      var dx = e.clientX - b.left - b.width / 2;
      var dy = e.clientY - b.top - b.height / 2;
      hsv.h = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
      hsv.s = Math.min(1, Math.sqrt(dx * dx + dy * dy) / (b.width / 2));
      if (hsv.v < 0.15) hsv.v = 1; // a pick in the dark would show nothing
      changed();
    }
    disc.addEventListener('pointerdown', function (e) {
      disc.setPointerCapture(e.pointerId);
      pointAt(e);
    });
    disc.addEventListener('pointermove', function (e) {
      if (disc.hasPointerCapture(e.pointerId)) pointAt(e);
    });
    disc.addEventListener('keydown', function (e) {
      var k = e.key;
      if (k === 'ArrowLeft') hsv.h = (hsv.h + 355) % 360;
      else if (k === 'ArrowRight') hsv.h = (hsv.h + 5) % 360;
      else if (k === 'ArrowUp') hsv.s = Math.min(1, hsv.s + 0.05);
      else if (k === 'ArrowDown') hsv.s = Math.max(0, hsv.s - 0.05);
      else return;
      e.preventDefault();
      changed();
    });
    slider.addEventListener('input', function () {
      hsv.v = Number(slider.value) / 100;
      changed();
    });
    hexIn.addEventListener('input', function () {
      var v = hexIn.value.trim();
      if (v.charAt(0) !== '#') v = '#' + v;
      if (!/^#[0-9a-fA-F]{6}$/.test(v)) return;
      hsv = hexHsv(v);
      changed(true);
    });
    hexIn.addEventListener('blur', function () { draw(); });
    sw.addEventListener('change', function () {
      guard = sw.checked;
      changed();
    });
    draw();
    return { node: node, value: shown, redraw: draw };
  }

  function openMaker(editing) {
    var sheet = openSheet('theme-tpl');
    var q = function (id) { return sheet.root.querySelector('#' + id); };
    var from = editing || shownTheme() || {};
    var c = {
      stage: from.stage || '#1b1713',
      accent: from.accent || '#e7a34a',
      weather: (from.cards && from.cards.weather) || '#3a3732',
      clock: (from.cards && from.cards.clock) || '#282622',
      affirmation: (from.cards && from.cards.affirmation) || '#645e54',
      font: (editing && editing.font) || '',
    };
    var inUse = editing && (editing.name === S.profile.theme);
    q('theme-h').textContent = editing ? 'Edit ' + editing.label : 'Make a theme';
    q('mk-name').value = editing ? editing.label : 'My theme';
    q('mk-save').textContent = editing ? 'Save changes' : 'Save theme';
    if (editing) {
      q('mk-delete').hidden = !!inUse;
      if (inUse) {
        q('mk-note').hidden = false;
        q('mk-note').textContent = 'To delete this theme, pick a different one first.';
      }
    }

    function draw() {
      var p = q('mk-preview');
      p.style.fontFamily = c.font ? specimen(c.font) : '';
      p.querySelector('.hello').style.fontFamily = p.style.fontFamily;
      p.style.background = c.stage;
      p.style.color = inkFor([c.stage]);
      p.querySelector('i').style.background = c.accent;
      var onCard = inkFor([c.weather, c.clock, c.affirmation]);
      Array.prototype.forEach.call(p.querySelectorAll('b'), function (b) {
        b.style.background = c[b.getAttribute('data-slot')];
        b.style.color = onCard;
      });
    }
    // What each colour has to stay readable against: its own writing (the
    // ink is picked from it), or, for the highlight, the background.
    function cardInk(slot, hex) {
      return inkFor(['weather', 'clock', 'affirmation'].map(function (k) {
        return k === slot ? hex : c[k];
      }));
    }
    var open = null; // { well, holder, wheel } of the wheel showing
    var wheels = [];
    WELLS.forEach(function (w) {
      var slot = w[0];
      var swatch = el('span', { class: 'swatch' });
      swatch.style.background = c[slot];
      var well = el('button', {
        type: 'button', class: 'well', 'aria-expanded': 'false',
      }, [el('span', {}, [document.createTextNode(w[1]), el('small', { text: w[2] })]), swatch]);
      var holder = el('div', { class: 'well-wheel', hidden: 'hidden' });
      var wheel = null;
      well.addEventListener('click', function () {
        var was = open && open.well === well;
        if (open) {
          open.holder.hidden = true;
          open.well.setAttribute('aria-expanded', 'false');
          open = null;
        }
        if (was) return;
        if (!wheel) {
          wheel = colourWheel({
            value: c[slot],
            min: slot === 'accent' ? 3 : 4.5,
            against: slot === 'accent' ? 'on the background' : 'with its writing',
            ratioOf: slot === 'accent'
              ? function (h) { return contrast(h, c.stage); }
              : slot === 'stage'
                ? function (h) { return contrast(h, inkFor([h])); }
                : function (h) { return contrast(h, cardInk(slot, h)); },
            onInput: function (hex) {
              c[slot] = hex;
              swatch.style.background = hex;
              draw();
              // The highlight is judged against the background.
              wheels.forEach(function (x) { if (x !== wheel) x.redraw(); });
            },
          });
          wheels.push(wheel);
          holder.appendChild(wheel.node);
        }
        wheel.redraw();
        holder.hidden = false;
        well.setAttribute('aria-expanded', 'true');
        open = { well: well, holder: holder };
      });
      q('mk-wells').appendChild(well);
      q('mk-wells').appendChild(holder);
    });
    FONTS.forEach(function (f) {
      var chip = el('button', {
        type: 'button', class: 'chip', role: 'radio',
        text: f[0] ? f[1] : 'The usual',
        'aria-checked': f[0] === c.font ? 'true' : 'false',
        onclick: function () {
          c.font = f[0];
          Array.prototype.forEach.call(q('mk-fonts').children, function (b) {
            b.setAttribute('aria-checked', b === chip ? 'true' : 'false');
          });
          draw();
        },
      });
      if (f[0]) chip.style.fontFamily = specimen(f[0]);
      q('mk-fonts').appendChild(chip);
    });
    draw();

    q('mk-cancel').addEventListener('click', sheet.close);
    q('mk-save').addEventListener('click', function () {
      var label = q('mk-name').value.trim();
      if (!label) { q('mk-name').focus(); toast('Give your theme a name'); return; }
      var body = Object.assign({ label: label }, c);
      var saving = editing
        ? call('/api/themes/custom/' + encodeURIComponent(editing.name), 'PUT', body)
        : call('/api/themes/custom', 'POST', body);
      saving.then(function (t) {
        sheet.close();
        return call('/api/themes').then(function (list) {
          S.themes = list.themes;
          // A screen-wide font would hide the one this theme comes with;
          // having just picked it here, you'd want to see it.
          var showFont = c.font && S.profile.font;
          if (editing && !(inUse && showFont)) { renderAll(); toast('Saved'); return null; }
          var patch = { theme: t.name };
          if (showFont) patch.font = '';
          toast(editing ? 'Saved, in ' + fontName(c.font) : label + ' is on the screen');
          return saveProfile(patch, 'use your theme');
        });
      }).catch(failed('save your theme'));
    });
    q('mk-delete').addEventListener('click', function () {
      if (!confirm('Delete ' + editing.label + "? This can't be undone.")) return;
      call('/api/themes/custom/' + encodeURIComponent(editing.name), 'DELETE')
        .then(function () { return call('/api/themes'); })
        .then(function (list) {
          S.themes = list.themes;
          sheet.close();
          renderAll();
          toast(editing.label + ' deleted');
        })
        .catch(failed('delete the theme'));
    });
  }

  // ── Pages & Navigation ─────────────────────────────────────────────
  var PAGES = ['home', 'alarms', 'themes', 'photos', 'settings', 'device'];
  var TAB_ORDER = ['themes', 'settings', 'photos', 'alarms', 'device'];
  var current = null;
  var fromHome = false;
  var tabScrolls = {};

  function updateTabs(name) {
    var tabMap = {
      'themes': 'tab-themes',
      'settings': 'tab-settings',
      'photos': 'tab-photos',
      'alarms': 'tab-alarms',
      'device': 'tab-device'
    };
    var activeId = tabMap[name] || 'tab-themes';
    var tabs = document.querySelectorAll('.bottom-tab-bar .tab-item');
    for (var i = 0; i < tabs.length; i++) {
      var tab = tabs[i];
      var isActive = tab.id === activeId;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
    }
  }

  function route() {
    var rawName = location.hash.slice(1);
    var openClock = rawName === 'photo-clock' || rawName === 'clock';
    var name = openClock ? 'settings' : rawName;
    if (!name || name === 'home' || PAGES.indexOf(name) < 0) name = 'themes';
    if (name === current) {
      updateTabs(name);
      if (openClock) setTimeout(openClockStyle, 100);
      return;
    }
    var first = current === null;
    var prevIdx = current ? TAB_ORDER.indexOf(current) : -1;
    var nextIdx = TAB_ORDER.indexOf(name);
    var back = prevIdx >= 0 && nextIdx < prevIdx;
    if (current) tabScrolls[current] = window.scrollY;
    fromHome = current === 'home' && !back;
    current = name;

    function swap() {
      PAGES.forEach(function (p) {
        var page = $('page-' + p);
        if (page) page.hidden = p !== name;
      });
      var targetScroll = tabScrolls[name] || 0;
      window.scrollTo(0, targetScroll);
      if (!back) {
        var h = document.querySelector('#page-' + name + ' h2');
        if (h) h.focus({ preventScroll: true });
      }
      updateTabs(name);
      if (openClock) setTimeout(openClockStyle, 150);
    }
    if (first || REDUCED.matches) swap();
    else if (document.startViewTransition) {
      document.documentElement.dataset.nav = back ? 'back' : 'fwd';
      document.startViewTransition(swap);
    } else {
      swap();
      var page = $('page-' + name);
      if (page) {
        page.classList.remove('in-fwd', 'in-back');
        void page.offsetWidth; // restart the animation
        page.classList.add(back ? 'in-back' : 'in-fwd');
      }
    }
    if (name === 'device') startHealth(); else stopHealth();
    if (name === 'alarms') startAlarms(); else stopAlarms();
  }
  window.addEventListener('hashchange', route);

  var tabElements = document.querySelectorAll('.bottom-tab-bar .tab-item');
  for (var ti = 0; ti < tabElements.length; ti++) {
    tabElements[ti].addEventListener('click', function (e) {
      var href = this.getAttribute('href');
      var tName = href ? href.slice(1) : '';
      if (tName && tName === current) {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  }

  function renderHome() {
    var t = theme(S.profile.theme);
    if ($('stage-screen-name')) $('stage-screen-name').textContent = S.screen.name || 'Your screen';
    document.title = (S.screen.name || 'Your screen') + ' · Companion';
    $('hub-theme').textContent = t ? t.label : '';
    var dots = $('hub-dots');
    dots.innerHTML = '';
    if (t) {
      ['weather', 'clock', 'affirmation'].forEach(function (k) {
        var i = el('i');
        i.style.background = (t.cards && t.cards[k]) || t.accent;
        dots.appendChild(i);
      });
    }
    var held = S.screen.night_clock !== false && !!S.screen.night_clock_hold;
    var isPhoto = S.screen.night_clock_photo !== false;
    var qClock = $('q-clock');
    if (qClock) {
      qClock.setAttribute('aria-pressed', held ? 'true' : 'false');
      var label = $('q-clock-label');
      if (label) label.textContent = isPhoto ? 'Photo Clock' : 'Clock';
    }
    $('q-alt').setAttribute('aria-pressed', S.screen.alternate && !held ? 'true' : 'false');
    if ($('q-round')) {
      $('q-round').setAttribute('aria-pressed', S.screen.shape === 'circle' ? 'true' : 'false');
    }
    $('hub-settings').textContent = settingsSummary();
  }

  // The Settings tile says what's set, the way Themes names the theme.
  function settingsSummary() {
    var s = S.screen;
    var bits = [];
    if (s.night_clock_hold && s.night_clock !== false) {
      bits.push(s.night_clock_photo !== false ? 'Photo Clock on' : 'Clock on');
    } else if (s.alternate) {
      bits.push('Photo Clock & cards');
    } else if (s.night_clock !== false) {
      bits.push('Night clock on');
    }
    if (s.blackout_start && s.blackout_end) {
      bits.push('Dark ' + shortTime(s.blackout_start) + '\u2013' + shortTime(s.blackout_end));
    } else if (s.dim_start && s.dim_end) {
      bits.push('Dims ' + shortTime(s.dim_start));
    }
    return bits.length ? bits.join(' · ') : 'Photo Clock, layout and night';
  }
  function shortTime(hhmm) {
    var p = hhmm.split(':');
    var h = Number(p[0]);
    var m = Number(p[1]);
    return (h % 12 || 12) + (m ? ':' + pad2(m) : '') + (h < 12 ? ' am' : ' pm');
  }

  $('q-clock').addEventListener('click', function () {
    var held = this.getAttribute('aria-pressed') === 'true';
    if (held) {
      openClockStyle();
    } else {
      var patch = { night_clock: true, night_clock_hold: true, night_clock_photo: true, alternate: false };
      saveScreen(patch, 'show Photo Clock')
        .then(function () {
          if (!S.screen.night_clock_hold) return;
          toast('Photo Clock on');
          openClockStyle();
        });
    }
  });

  // Alternate: the Photo Clock for a minute, then the cards for 30 s, with a
  // 2 s handoff between them (web Alternate). Lets go of Clock only.
  $('q-alt').addEventListener('click', function () {
    var on = this.getAttribute('aria-pressed') !== 'true';
    var patch = { alternate: on };
    if (on) patch.night_clock_hold = false;
    saveScreen(patch, 'change the screen')
      .then(function () {
        if (!!S.screen.alternate !== on) return; // didn't save
        toast(on ? 'Clock and cards take turns' : 'Your cards are back');
      });
  });

  // Round or rectangular in one tap: the dashboard's shape (circle mode) and
  // the Photo Clock's face (glass hands in a disc, or glass digits) together,
  // so whichever the screen is showing changes. Settings still sets each
  // on its own.
  $('q-round').addEventListener('click', function () {
    var round = this.getAttribute('aria-pressed') !== 'true';
    var pc = Object.assign({}, S.screen.photo_clock || {}, { face: round ? 'hands' : 'digits' });
    saveScreen({ shape: round ? 'circle' : 'rect', photo_clock: pc }, 'change the shape')
      .then(function () {
        if ((S.screen.shape === 'circle') !== round) return; // didn't save
        toast(round ? 'Round screen' : 'Rectangular screen');
      });
  });

  // The lone clock's face and colour. Saved as you go (a short wait while a
  // finger is still on the wheel), so the screen follows along.
  var CLOCK_PINK = '#f6cfdc';
  var CLOCK_SERIF = '"Cormorant Garamond", "Cormorant", Georgia, serif';
  var CLOCK_PHOTO = 'Roboto, system-ui, sans-serif';
  function openClockStyle() {
    var sheet = openSheet('clock-tpl');
    var q = function (id) { return sheet.root.querySelector('#' + id); };
    var font = S.screen.night_clock_font || '';
    var colour = S.screen.night_clock_color || CLOCK_PINK;
    var timer = null;
    var firstChip = null;
    function save() {
      clearTimeout(timer);
      timer = setTimeout(function () {
        timer = null;
        saveScreen({
          night_clock_font: font,
          night_clock_color: colour.toLowerCase() === CLOCK_PINK ? '' : colour,
        }, 'change the clock');
      }, 350);
    }
    function preview() {
      var p = q('ck-preview');
      var now = new Date();
      var h = now.getHours() % 12 || 12;
      p.textContent = h + ':' + ('0' + now.getMinutes()).slice(-2);
      // Photos: '' is the screen's own photo clock face, in white glass.
      p.style.fontFamily = font ? specimen(font) : photo ? CLOCK_PHOTO : CLOCK_SERIF;
      p.style.color = !photo ? colour : /^#/.test(tint) ? tint : '#fff';
    }
    [['', 'Thin serif']].concat(FONTS.slice(1)).forEach(function (f) {
      var chip = el('button', {
        type: 'button', class: 'chip', role: 'radio', text: f[1],
        'aria-checked': f[0] === font ? 'true' : 'false',
        onclick: function () {
          font = f[0];
          Array.prototype.forEach.call(q('ck-fonts').children, function (b) {
            b.setAttribute('aria-checked', b === chip ? 'true' : 'false');
          });
          preview();
          save();
        },
      });
      chip.style.fontFamily = f[0] ? specimen(f[0]) : CLOCK_SERIF;
      q('ck-fonts').appendChild(chip);
      if (!f[0]) firstChip = chip;
    });
    q('ck-wheel').appendChild(colourWheel({
      value: colour,
      min: 4.5,
      against: 'on black',
      ratioOf: function (hex) { return contrast(hex, '#000000'); },
      onInput: function (hex) { colour = hex; preview(); save(); },
    }).node);
    // The Photo Clock's glass: clear, each photo's own colour (worked out
    // on the server), or one picked here.
    var tint = S.screen.night_clock_tint || '';
    var tintPick = /^#/.test(tint) ? tint : '#7fb4ff';
    var tintTimer = null;
    function saveTint() {
      clearTimeout(tintTimer);
      tintTimer = setTimeout(function () {
        saveScreen({ night_clock_tint: tint }, 'change the tint');
      }, 350);
    }
    function showTint() {
      var mode = /^#/.test(tint) ? 'pick' : tint;
      Array.prototype.forEach.call(q('ck-tints').children, function (b) {
        b.setAttribute('aria-checked', b.dataset.mode === mode ? 'true' : 'false');
      });
      q('ck-tint-wheel').hidden = mode !== 'pick';
      preview();
    }
    [['', 'Clear'], ['auto', 'From the photo'], ['pick', 'Pick a colour']].forEach(function (t) {
      var chip = el('button', {
        type: 'button', class: 'chip', role: 'radio', text: t[1],
        onclick: function () {
          tint = t[0] === 'pick' ? tintPick : t[0];
          showTint();
          saveTint();
        },
      });
      chip.dataset.mode = t[0];
      q('ck-tints').appendChild(chip);
    });
    q('ck-tint-wheel').appendChild(colourWheel({
      value: tintPick,
      free: true,
      onInput: function (hex) { tint = tintPick = hex; preview(); saveTint(); },
    }).node);

    // The Photo Clock's glass and display enhancements. The whole photo_clock is
    // sent each time; fields this page doesn't show keep their values.
    var pc = Object.assign(
      {
        font: 'roboto',
        size: 'l',
        glass: 'liquid',
        opacity: 0.45,
        depth: true,
        date: true,
        layout: 'row',
        drift: false,
        transition: 'swipe',
        whisper: false,
        weather: false,
        grain: 0.0,
      },
      S.screen.photo_clock || {}
    );
    var pcTimer = null;
    function savePhotoClock() {
      clearTimeout(pcTimer);
      pcTimer = setTimeout(function () {
        saveScreen({ photo_clock: pc }, 'change the photo clock');
      }, 350);
    }
    // Glass and the photo-colour looks are one setting in two rows of chips.
    [
      ['ck-glass', [['liquid', 'Liquid'], ['frosted', 'Frosted'], ['crystal', 'Crystal'],
        ['flat', 'Flat']]],
      ['ck-ink', [['mesh', 'Blend'], ['match', 'Photo'], ['opposite', 'Opposite'],
        ['chrome', 'Chrome'], ['print', 'Print'], ['neon', 'Neon']]],
    ].forEach(function (row) {
      row[1].forEach(function (g) {
        var chip = el('button', {
          type: 'button', class: 'chip', role: 'radio', text: g[1],
          'aria-checked': g[0] === pc.glass ? 'true' : 'false',
          'data-glass': g[0],
          onclick: function () {
            pc.glass = g[0];
            ['ck-glass', 'ck-ink'].forEach(function (id) {
              Array.prototype.forEach.call(q(id).children, function (b) {
                b.setAttribute('aria-checked', b === chip ? 'true' : 'false');
              });
            });
            savePhotoClock();
          },
        });
        q(row[0]).appendChild(chip);
      });
    });
    var opacity = q('ck-opacity');
    function showOpacity() {
      q('ck-opacity-out').textContent = Math.round(pc.opacity * 100) + '%';
    }
    opacity.value = String(pc.opacity);
    opacity.addEventListener('input', function () {
      pc.opacity = Number(opacity.value);
      showOpacity();
      savePhotoClock();
    });
    showOpacity();

    [['row', 'Row'], ['stack', 'Stacked']].forEach(function (l) {
      var chip = el('button', {
        type: 'button', class: 'chip', role: 'radio', text: l[1],
        'aria-checked': l[0] === (pc.layout || 'row') ? 'true' : 'false',
        onclick: function () {
          pc.layout = l[0];
          Array.prototype.forEach.call(q('ck-layout').children, function (b) {
            b.setAttribute('aria-checked', b === chip ? 'true' : 'false');
          });
          savePhotoClock();
        },
      });
      q('ck-layout').appendChild(chip);
    });

    [['swipe', 'Swipe'], ['fade', 'Fade']].forEach(function (tr) {
      var chip = el('button', {
        type: 'button', class: 'chip', role: 'radio', text: tr[1],
        'aria-checked': tr[0] === (pc.transition || 'swipe') ? 'true' : 'false',
        onclick: function () {
          pc.transition = tr[0];
          Array.prototype.forEach.call(q('ck-trans').children, function (b) {
            b.setAttribute('aria-checked', b === chip ? 'true' : 'false');
          });
          savePhotoClock();
        },
      });
      q('ck-trans').appendChild(chip);
    });

    var driftEl = q('ck-drift');
    driftEl.checked = !!pc.drift;
    driftEl.addEventListener('change', function () {
      pc.drift = driftEl.checked;
      savePhotoClock();
    });

    var whisperEl = q('ck-whisper');
    whisperEl.checked = !!pc.whisper;
    whisperEl.addEventListener('change', function () {
      pc.whisper = whisperEl.checked;
      savePhotoClock();
    });

    var weatherEl = q('ck-weather');
    weatherEl.checked = !!pc.weather;
    weatherEl.addEventListener('change', function () {
      pc.weather = weatherEl.checked;
      savePhotoClock();
    });

    var grain = q('ck-grain');
    function showGrain() {
      q('ck-grain-out').textContent = Math.round((pc.grain || 0) * 100) + '%';
    }
    grain.value = String(pc.grain || 0);
    grain.addEventListener('input', function () {
      pc.grain = Number(grain.value);
      showGrain();
      savePhotoClock();
    });
    showGrain();

    // Plain: the lone clock on black. Photos: the Photo Clock, full screen.
    var photo = !!S.screen.night_clock_photo;
    function showStyle() {
      q('ck-plain').hidden = photo;
      q('ck-tint-box').hidden = !photo;
      q('ck-photo-note').hidden = !photo;
      var h = q('ck-h');
      if (h) h.textContent = photo ? 'Photo Clock' : 'Clock';
      var lede = q('ck-lede');
      if (lede) {
        lede.textContent = photo
          ? 'Full-screen photos with the time over them. Changes appear on your display as you make them.'
          : 'The screen shows just the clock on black. Changes appear on your display as you make them.';
      }
      firstChip.textContent = photo ? 'Standard' : 'Thin serif';
      firstChip.style.fontFamily = photo ? CLOCK_PHOTO : CLOCK_SERIF;
      preview();
      Array.prototype.forEach.call(q('ck-style').children, function (b, i) {
        b.setAttribute('aria-checked', (i === 1) === photo ? 'true' : 'false');
      });
    }
    ['Plain', 'Photos'].forEach(function (label, i) {
      q('ck-style').appendChild(el('button', {
        type: 'button', class: 'chip', role: 'radio', text: label,
        onclick: function () {
          if ((i === 1) === photo) return;
          photo = i === 1;
          showStyle();
          saveScreen({ night_clock_photo: photo }, 'change the clock');
        },
      }));
    });
    showStyle();
    showTint();
    q('ck-done').addEventListener('click', sheet.close);
    q('ck-off').addEventListener('click', function () {
      sheet.close();
      saveScreen({ night_clock_hold: false }, 'change the clock')
        .then(function () { if (!S.screen.night_clock_hold) toast('Your cards are back'); });
    });
  }

  // ── The live miniature ────────────────────────────────────────────
  // A snapshot of what the kiosk really shows (/api/control/snapshot),
  // refreshed while this page is in view. Not the dashboard itself in an
  // iframe: drawing the whole 2048x1280 screen at a phone's 3x crashed iOS
  // Safari. Without a snapshot (single-host install, kiosk off) the sketch
  // simply stays.
  var LIVE_MS = 10000;
  function startLive() {
    var w = S.screen.viewport_w;
    var h = S.screen.viewport_h;
    if (!w || !h) return;
    $('mini').style.aspectRatio = w + ' / ' + h;
    var box = el('div', { class: 'mini-live', 'aria-hidden': 'true' });
    var img = el('img', { alt: '' });
    box.appendChild(img);
    $('mini-frame').insertBefore(box, $('mini-live'));
    var busy = false;
    function grab() {
      if (busy || document.hidden) return;
      busy = true;
      // Load off-screen and swap in whole, so a refresh never flashes.
      var next = new Image();
      next.onload = function () {
        busy = false;
        img.src = next.src;
        box.classList.add('on');
        $('mini-live').hidden = false;
      };
      next.onerror = function () { busy = false; };
      next.src = '/api/control/snapshot?t=' + Date.now();
    }
    grab();
    setInterval(grab, LIVE_MS);
    document.addEventListener('visibilitychange', grab);
  }

  // ── Timers and alarms ─────────────────────────────────────────────
  function refreshTimers() {
    return call('/api/timers').then(function (ts) {
      S.timers = ts;
      var timers = ts.filter(function (t) { return t.kind === 'timer'; }).length;
      $('q-timers').hidden = !timers;
      $('q-timers').textContent = timers;
    }).catch(function () {});
  }
  function checkAlarm() {
    return call('/api/takeover').then(function (t) {
      $('q-dismiss').hidden = !(t && t.card && t.card.kind === 'alarm');
    }).catch(function () {});
  }
  $('q-dismiss').addEventListener('click', function () {
    call('/api/takeover', 'DELETE')
      .then(function () { $('q-dismiss').hidden = true; toast('Alarm off'); })
      .catch(failed('turn off the alarm'));
  });

  // ── Alarms and reminders (kept by Antigua, see pinedaview.alarms) ──
  var DAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']; // Antigua counts Monday as 0
  var DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  var alarmPoll = null;

  function loadAlarms() {
    return call('/api/alarms').then(function (rows) {
      S.alarms = rows;
      S.alarmsDown = false;
      var on = rows.filter(function (r) { return r.enabled; }).length;
      $('q-alarms').hidden = !on;
      $('q-alarms').textContent = on;
      var tabBadge = $('tab-alarms-badge');
      if (tabBadge) {
        tabBadge.hidden = !on;
        tabBadge.textContent = on;
      }
    }).catch(function () {
      S.alarmsDown = true;
    });
  }
  function startAlarms() {
    loadAlarms().then(renderAlarms);
    clearInterval(alarmPoll);
    // Past ones drop off on their own; so do changes made by voice.
    alarmPoll = setInterval(function () {
      if (!document.hidden) loadAlarms().then(renderAlarms);
    }, 20000);
  }
  function stopAlarms() { clearInterval(alarmPoll); }
  $('alarm-open').addEventListener('click', function () { location.hash = 'alarms'; });

  function pad2(n) { return String(n).padStart(2, '0'); }
  function isoDay(d) {
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }
  function addDays(d, n) { var c = new Date(d); c.setDate(c.getDate() + n); return c; }
  function clockParts(h, m) {
    return { t: (h % 12 || 12) + ':' + pad2(m), ampm: h < 12 ? 'AM' : 'PM' };
  }
  function repeatText(r) {
    if (!r) return '';
    if (r.indexOf('every:') === 0) {
      var sec = Number(r.slice(6));
      if (sec % 3600 === 0) return sec === 3600 ? 'Every hour' : 'Every ' + sec / 3600 + ' hours';
      return 'Every ' + Math.round(sec / 60) + ' minutes';
    }
    if (r === 'daily') return 'Every day';
    if (r === 'weekdays') return 'Weekdays';
    if (r === 'weekends') return 'Weekends';
    return r.split(',').map(function (i) { return DAY_NAMES[Number(i)]; }).join(', ');
  }
  function dayText(d) {
    var today = new Date();
    if (isoDay(d) === isoDay(today)) return 'Today';
    if (isoDay(d) === isoDay(addDays(today, 1))) return 'Tomorrow';
    return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  }
  function repeatDays(r) {
    if (r === 'daily') return [0, 1, 2, 3, 4, 5, 6];
    if (r === 'weekdays') return [0, 1, 2, 3, 4];
    if (r === 'weekends') return [5, 6];
    return (r || '').split(',').filter(Boolean).map(Number);
  }
  function repeatFrom(days) {
    var key = days.slice().sort().join(',');
    return key === '0,1,2,3,4,5,6' ? 'daily' : key === '0,1,2,3,4' ? 'weekdays'
      : key === '5,6' ? 'weekends' : key;
  }
  function cap(t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; }
  function whatOf(r) {
    return r.kind === 'reminder' ? 'Remind me to ' + (r.message || r.label)
      : r.name ? cap(r.name) : 'Alarm';
  }

  function renderAlarms() {
    var list = $('al-list');
    var empty = $('al-empty');
    list.innerHTML = '';
    if (S.alarmsDown) {
      empty.hidden = false;
      empty.textContent = "Antigua isn't answering, so alarms can't be seen or changed "
        + 'right now. Try again in a minute.';
      return;
    }
    var rows = S.alarms || [];
    empty.hidden = rows.length > 0;
    empty.textContent = 'Nothing set. Add one above, or ask Antigua.';
    rows.forEach(function (r) {
      var at = new Date(r.fires_at * 1000);
      var p = r.hour !== null && r.hour !== undefined
        ? clockParts(r.hour, r.minute) : clockParts(at.getHours(), at.getMinutes());
      var when = repeatText(r.repeat) || (r.enabled ? dayText(at) : 'Once');
      if (!r.speak) when += ' · Screen only';
      var sw = el('input', {
        type: 'checkbox', class: 'switch', role: 'switch',
        'aria-label': whatOf(r) + ' at ' + p.t + ' ' + p.ampm,
      });
      sw.checked = r.enabled;
      sw.addEventListener('change', function () { switchAlarm(r, sw.checked); });
      var t = el('span', { class: 't' }, [
        document.createTextNode(p.t), el('small', { text: p.ampm }),
      ]);
      list.appendChild(el('li', { class: 'al' + (r.enabled ? '' : ' off') }, [
        el('button', {
          type: 'button', class: 'open', 'aria-label': 'Change ' + whatOf(r),
          onclick: function () { openAlarm(r.kind, r); },
        }, [
          t, el('span', { class: 'what', text: whatOf(r) }),
          el('span', { class: 'd', text: when }),
        ]),
        sw,
      ]));
    });
  }

  function switchAlarm(r, on) {
    call('/api/alarms/' + encodeURIComponent(r.id), 'PATCH', { enabled: on })
      .then(function (row) {
        if (on) {
          var at = new Date(row.fires_at * 1000);
          var p = clockParts(at.getHours(), at.getMinutes());
          var day = row.repeat ? '' : ', ' + dayText(at).toLowerCase();
          toast('On for ' + p.t + ' ' + p.ampm + day);
        }
      })
      .catch(function (e) {
        if (e.status === 404) toast("That one's time has passed, so it's gone");
        else failed(on ? 'turn it on' : 'turn it off')();
      })
      .then(loadAlarms).then(renderAlarms);
  }

  $('al-add-alarm').addEventListener('click', function () { openAlarm('alarm'); });
  $('al-add-reminder').addEventListener('click', function () { openAlarm('reminder'); });

  // The form, for a new alarm or reminder or for changing one (`row`).
  function openAlarm(kind, row) {
    var sheet = openSheet('alarm-tpl');
    var q = function (id) { return sheet.root.querySelector('#' + id); };
    var reminder = kind === 'reminder';
    var when = 'today';
    var days = [];
    var now = new Date();

    q('al-h').textContent = (row ? 'Change ' : 'New ') + (reminder ? 'reminder' : 'alarm');
    q('al-save').textContent = row ? 'Save' : reminder ? 'Set reminder' : 'Set alarm';
    q('al-msg-box').hidden = !reminder;
    q('al-name-box').hidden = reminder;
    q('al-delete').hidden = !row;
    q('al-date').min = isoDay(now);

    DAY_LETTERS.forEach(function (letter, i) {
      q('al-days').appendChild(el('button', {
        type: 'button', class: 'day', 'aria-pressed': 'false', 'aria-label': DAY_NAMES[i],
        'data-i': String(i), text: letter,
        onclick: function () {
          var at = days.indexOf(i);
          if (at < 0) days.push(i); else days.splice(at, 1);
          drawWhen();
        },
      }));
    });

    if (row) {
      var at = new Date(row.fires_at * 1000);
      var h = row.hour !== null && row.hour !== undefined ? row.hour : at.getHours();
      var m = row.hour !== null && row.hour !== undefined ? row.minute : at.getMinutes();
      q('al-time').value = pad2(h) + ':' + pad2(m);
      q('al-msg').value = row.message || '';
      q('al-name').value = row.name || '';
      q('al-speak').checked = row.speak;
      if (row.repeat && row.repeat.indexOf('every:') !== 0) {
        when = 'repeat';
        days = repeatDays(row.repeat);
      } else if (isoDay(at) === isoDay(addDays(now, 1))) {
        when = 'tomorrow';
      } else if (isoDay(at) !== isoDay(now)) {
        when = 'day';
        q('al-date').value = isoDay(at);
      }
    } else {
      // An alarm starts at 7; a reminder an hour from now, on the hour.
      var start = reminder ? new Date(now.getTime() + 3600e3) : null;
      q('al-time').value = reminder ? pad2(start.getHours()) + ':00' : '07:00';
      if (reminder && start.getDate() !== now.getDate()) when = 'tomorrow';
    }

    function timePassedToday() {
      var hm = (q('al-time').value || '').split(':');
      if (hm.length < 2) return false;
      var t = new Date();
      t.setHours(Number(hm[0]), Number(hm[1]), 0, 0);
      return t <= new Date();
    }
    function drawWhen() {
      var gone = timePassedToday();
      if (gone && when === 'today') when = 'tomorrow';
      sheet.root.querySelectorAll('#al-when .chip').forEach(function (c) {
        c.setAttribute('aria-checked', c.dataset.when === when ? 'true' : 'false');
        c.disabled = c.dataset.when === 'today' && gone;
      });
      q('al-date').hidden = when !== 'day';
      q('al-days').hidden = when !== 'repeat';
      sheet.root.querySelectorAll('.day').forEach(function (b) {
        b.setAttribute('aria-pressed', days.indexOf(Number(b.dataset.i)) >= 0 ? 'true' : 'false');
      });
      var named = (q('al-name').value || '').trim();
      var msg = (q('al-msg').value || '').trim().replace(/^remind me to\\s+/i, '');
      q('al-speak-s').textContent = !q('al-speak').checked
        ? 'Only the screen shows it. Antigua stays quiet.'
        : reminder ? 'Antigua says "Reminder: ' + (msg || 'call mom') + '."'
        : 'Antigua says "Your ' + (named ? named.toLowerCase() + ' ' : '')
          + 'alarm is going off" and keeps ringing until you say stop.';
    }
    sheet.root.querySelectorAll('#al-when .chip').forEach(function (c) {
      c.addEventListener('click', function () {
        when = c.dataset.when;
        if (when === 'repeat' && !days.length) days = [0, 1, 2, 3, 4, 5, 6];
        if (when === 'day' && !q('al-date').value) {
          q('al-date').value = isoDay(addDays(new Date(), 2));
        }
        drawWhen();
        if (when === 'day') q('al-date').focus();
      });
    });
    ['al-time', 'al-name', 'al-msg', 'al-speak'].forEach(function (id) {
      q(id).addEventListener('input', drawWhen);
      q(id).addEventListener('change', drawWhen);
    });
    drawWhen();

    q('al-cancel').addEventListener('click', sheet.close);
    q('al-delete').addEventListener('click', function () {
      call('/api/alarms/' + encodeURIComponent(row.id), 'DELETE')
        .catch(function (e) { if (e.status !== 404) throw e; })
        .then(function () { sheet.close(); toast('Deleted'); })
        .catch(failed('delete it'))
        .then(loadAlarms).then(renderAlarms);
    });
    q('al-save').addEventListener('click', function () {
      var body = { kind: kind, time: q('al-time').value, speak: q('al-speak').checked };
      if (!/^\\d{1,2}:\\d{2}$/.test(body.time)) { q('al-time').focus(); return; }
      if (reminder) {
        body.message = q('al-msg').value.trim().replace(/^remind me to\\s+/i, '');
        if (!body.message) { q('al-msg').focus(); return; }
      } else if (q('al-name').value.trim()) {
        body.name = q('al-name').value.trim();
      }
      if (when === 'today') body.date = isoDay(new Date());
      else if (when === 'tomorrow') body.date = isoDay(addDays(new Date(), 1));
      else if (when === 'day') {
        if (!q('al-date').value) { q('al-date').focus(); return; }
        body.date = q('al-date').value;
      } else {
        if (!days.length) { toast('Pick at least one day'); return; }
        body.repeat = repeatFrom(days);
      }
      var btn = q('al-save');
      btn.disabled = true;
      // A change is a new one, then the old one deleted, so a failure
      // never leaves you with neither.
      call('/api/alarms', 'POST', body)
        .then(function (made) {
          var gone = row ? call('/api/alarms/' + encodeURIComponent(row.id), 'DELETE')
            .catch(function () {}) : null;
          return Promise.resolve(gone).then(function () { return made; });
        })
        .then(function (made) {
          sheet.close();
          var at = new Date(made.fires_at * 1000);
          var p = clockParts(at.getHours(), at.getMinutes());
          var day = made.repeat ? repeatText(made.repeat).toLowerCase() : dayText(at).toLowerCase();
          toast((reminder ? 'Reminder' : 'Alarm') + (row ? ' changed: ' : ' set: ')
            + p.t + ' ' + p.ampm + ', ' + day);
        })
        .catch(function (e) {
          btn.disabled = false;
          if (e.status === 400 && e.detail) toast(cap(e.detail));
          else if (e.status === 503) toast("Antigua isn't answering. Try again in a minute.");
          else failed(row ? 'save it' : 'set it')();
        })
        .then(loadAlarms).then(renderAlarms);
    });
    if (!row) (reminder ? q('al-msg') : q('al-time')).focus();
    else q('al-save').focus({ preventScroll: true });
  }

  // ── Device health ─────────────────────────────────────────────────
  var healthTimer = null;
  function startHealth() {
    refreshHealth();
    if (!healthTimer) healthTimer = setInterval(refreshHealth, 5000);
  }
  function stopHealth() {
    clearInterval(healthTimer);
    healthTimer = null;
  }
  function busyWord(st) {
    var r = st.load1 / st.cores;
    return r < 0.35 ? 'Relaxed' : r < 0.75 ? 'Steady' : r < 1 ? 'Busy' : 'Overloaded';
  }
  function span(seconds) {
    var m = Math.floor(seconds / 60);
    var h = Math.floor(m / 60);
    var d = Math.floor(h / 24);
    if (d) return d === 1 ? '1 day' : d + ' days';
    if (h) return h === 1 ? '1 hour' : h + ' hours';
    return m <= 1 ? 'a minute' : m + ' minutes';
  }
  // What a row says, and whether it needs a look.
  function statRows(st) {
    var rows = [];
    var load = st.load1 / st.cores;
    rows.push(['How busy', busyWord(st),
      'load ' + st.load1.toFixed(2) + ' across ' + st.cores + ' cores', load >= 1]);
    if (st.mem_used_pct != null) {
      rows.push(['Memory', Math.round(st.mem_used_pct) + '% in use', '', st.mem_used_pct >= 90]);
    }
    var low = st.disk_free_gb / st.disk_total_gb < 0.1;
    rows.push(['Storage', st.disk_free_gb.toFixed(0) + ' GB free',
      'of ' + st.disk_total_gb.toFixed(0) + ' GB', low]);
    if (st.temp_c != null) {
      var hot = st.temp_c >= 80;
      rows.push(['Temperature', Math.round(st.temp_c) + ' °C',
        hot ? 'Hot enough to slow itself down' : st.temp_c >= 70 ? 'Warm' : 'Normal', hot]);
    }
    if (st.uptime_s != null) rows.push(['Running for', span(st.uptime_s), '', false]);
    return rows;
  }
  function drawStats(id, st, missing) {
    var dl = $(id);
    dl.innerHTML = '';
    if (!st) {
      dl.appendChild(el('p', { class: 'stats-note', text: missing }));
      return;
    }
    statRows(st).forEach(function (row) {
      dl.appendChild(el('div', { class: row[3] ? 'warn' : null }, [
        el('dt', { text: row[0] }),
        el('dd', {}, [
          document.createTextNode(row[1]), row[2] ? el('small', { text: row[2] }) : null,
        ]),
      ]));
    });
    var age = (Date.now() - new Date(st.at)) / 1000;
    if (age > 180) {
      dl.appendChild(el('p', { class: 'stats-note',
        text: 'Last heard from ' + span(age) + ' ago. If that keeps growing, it may be off.' }));
    }
  }
  function needsLook(st) {
    return statRows(st).some(function (row) { return row[3]; });
  }
  function refreshHealth() {
    return call('/api/system').then(function (sys) {
      drawStats('st-screen', sys.screen,
        "It hasn't checked in yet. It sends an update once a minute.");
      drawStats('st-server', sys.server, '');
      var pi = sys.screen;
      var stale = !pi || (Date.now() - new Date(pi.at)) / 1000 > 180;
      // Quiet when all is well; only a problem earns a line on the button.
      $('hub-device').textContent = stale ? "Can't hear the screen"
        : needsLook(pi) || needsLook(sys.server) ? 'Needs a look' : '';
    }).catch(function () {});
  }

  // ── Timer ─────────────────────────────────────────────────────────
  function remaining(t) {
    var s = Math.max(0, Math.round((new Date(t.fires_at) - Date.now()) / 1000));
    var m = Math.floor(s / 60);
    var h = Math.floor(m / 60);
    return h ? h + ':' + String(m % 60).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0')
      : m + ':' + String(s % 60).padStart(2, '0');
  }

  $('timer-open').addEventListener('click', function () {
    var ticking = null;
    var sheet = openSheet('timer-tpl', function () { clearInterval(ticking); });
    var q = function (id) { return sheet.root.querySelector('#' + id); };
    var list = q('running');

    function drawRunning() {
      var mine = S.timers.filter(function (t) { return t.kind === 'timer'; });
      list.innerHTML = '';
      list.hidden = !mine.length;
      mine.forEach(function (t) {
        list.appendChild(el('li', {}, [
          el('span', { class: 'left' }, [
            el('b', { text: remaining(t) }), document.createTextNode(t.label),
          ]),
          t.source ? null : el('button', {
            type: 'button', class: 'pill', text: 'Cancel',
            onclick: function () {
              call('/api/timers/' + encodeURIComponent(t.id), 'DELETE')
                .then(loadTimers).catch(failed('cancel the timer'));
            },
          }),
        ]));
      });
    }
    function loadTimers() {
      return refreshTimers().then(drawRunning);
    }

    TIMER_MIN.forEach(function (m) {
      var b = el('button', {
        type: 'button', class: 'key',
        onclick: function () {
          var label = q('timer-label').value.trim() || 'Timer';
          call('/api/timers', 'POST', { seconds: m * 60, label: label })
            .then(function () { toast(label + ' started for ' + m + ' min'); return loadTimers(); })
            .catch(failed('start the timer'));
        },
      }, [document.createTextNode(String(m)), el('small', { text: 'min' })]);
      q('presets').appendChild(b);
    });
    q('timer-done').addEventListener('click', sheet.close);
    loadTimers().catch(function () {});
    ticking = setInterval(drawRunning, 1000);
    q('timer-label').focus();
  });

  // ── Add & Manage photos ──────────────────────────────────────────
  var photoCount = null;
  var photoList = [];
  var isManagingPhotos = false;

  function showPhotoCount() {
    if (photoCount === null) return;
    $('hub-photos').textContent = photoCount === 1 ? '1 photo' : photoCount + ' photos';
  }

  function createDeleteBadge() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'del-badge';
    b.setAttribute('aria-label', 'Delete photo');
    b.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2' +
        'h4a2 2 0 0 1 2 2v2"></path>' +
        '<line x1="10" y1="11" x2="10" y2="17"></line>' +
        '<line x1="14" y1="11" x2="14" y2="17"></line>' +
      '</svg>';
    return b;
  }

  function renderPhotoGrid() {
    var grid = $('up-grid');
    grid.innerHTML = '';
    var hasPhotos = photoList.length > 0;
    $('recent-h').hidden = !hasPhotos;
    $('manage-photos-btn').hidden = !hasPhotos;

    if (!hasPhotos) {
      if (isManagingPhotos) setManagingPhotos(false);
      return;
    }

    photoList.sort(function (a, b) { return (b.uploaded_at || 0) - (a.uploaded_at || 0); });
    var items = isManagingPhotos ? photoList : photoList.slice(0, 9);

    items.forEach(function (p) {
      var li = el('li', { class: 'ok', 'data-name': p.name });
      var img = el('img', {
        alt: '', loading: 'lazy', src: '/api/photos/' + encodeURIComponent(p.name) + '/thumb',
      });
      li.appendChild(img);

      if (isManagingPhotos) {
        var badge = createDeleteBadge();
        badge.addEventListener('click', function (e) {
          e.stopPropagation();
          confirmDeletePhoto(p, li);
        });
        li.appendChild(badge);
        li.addEventListener('click', function () {
          confirmDeletePhoto(p, li);
        });
      }

      grid.appendChild(li);
    });
  }

  function setManagingPhotos(on) {
    isManagingPhotos = on;
    var btn = $('manage-photos-btn');
    var txt = $('manage-btn-text');
    var hint = $('manage-hint');
    var grid = $('up-grid');

    if (on) {
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');
      txt.textContent = 'Done';
      hint.hidden = false;
      grid.classList.add('manage-mode');
    } else {
      btn.classList.remove('active');
      btn.setAttribute('aria-pressed', 'false');
      txt.textContent = 'Manage photos';
      hint.hidden = true;
      grid.classList.remove('manage-mode');
    }
    renderPhotoGrid();
  }

  $('manage-photos-btn').addEventListener('click', function () {
    setManagingPhotos(!isManagingPhotos);
  });

  function confirmDeletePhoto(photo, li) {
    var sheet = openSheet('photo-delete-tpl');
    var root = sheet.root;
    var img = root.querySelector('#del-photo-img');
    if (img) {
      img.src = '/api/photos/' + encodeURIComponent(photo.name) + '/thumb';
    }
    var confirmBtn = root.querySelector('#del-photo-confirm');
    var cancelBtn = root.querySelector('#del-photo-cancel');

    cancelBtn.addEventListener('click', sheet.close);
    confirmBtn.addEventListener('click', function () {
      sheet.close();
      executeDeletePhoto(photo, li);
    });
  }

  function executeDeletePhoto(photo, li) {
    if (!li || li.classList.contains('deleting')) return;

    playTrashcanAnimation(li, function () {
      photoList = photoList.filter(function (p) { return p.name !== photo.name; });
      if (photoCount !== null) {
        photoCount = photoList.length;
        showPhotoCount();
      }
      li.remove();
      if (photoList.length === 0) {
        $('recent-h').hidden = true;
        $('manage-photos-btn').hidden = true;
        $('manage-hint').hidden = true;
        if (isManagingPhotos) setManagingPhotos(false);
      }
    });

    call('/api/photos/' + encodeURIComponent(photo.name), 'DELETE')
      .then(function () {
        toast('Photo deleted');
      })
      .catch(function () {
        toast("Couldn't delete photo. Check connection and try again.");
        call('/api/photos').then(function (list) {
          photoList = list || [];
          renderPhotoGrid();
        }).catch(function () {});
      });
  }

  function playTrashcanAnimation(li, onComplete) {
    if (REDUCED.matches) {
      li.style.transition = 'opacity 150ms ease';
      li.style.opacity = '0';
      setTimeout(onComplete, 160);
      return;
    }

    li.classList.add('deleting');
    var overlay = el('div', { class: 'trash-overlay' });
    overlay.innerHTML =
      '<div class="trash-anim">' +
        '<div class="trash-lid">' +
          '<svg viewBox="0 0 32 10" fill="none" stroke="currentColor" stroke-width="2.5" ' +
            'stroke-linecap="round">' +
            '<line x1="2" y1="8" x2="30" y2="8"></line>' +
            '<path d="M12 8V3a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v5" stroke-width="2"></path>' +
          '</svg>' +
        '</div>' +
        '<div class="trash-body">' +
          '<svg viewBox="0 0 32 30" fill="none" stroke="currentColor" stroke-width="2.5" ' +
            'stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M5 2l2 24a3 3 0 0 0 3 3h12a3 3 0 0 0 3-3l2-24"></path>' +
            '<line x1="12" y1="8" x2="12" y2="22"></line>' +
            '<line x1="16" y1="8" x2="16" y2="22"></line>' +
            '<line x1="20" y1="8" x2="20" y2="22"></line>' +
          '</svg>' +
        '</div>' +
        '<div class="trash-burst">' +
          '<span></span><span></span><span></span><span></span>' +
        '</div>' +
      '</div>';

    li.appendChild(overlay);

    setTimeout(function () {
      li.classList.add('deleted-collapse');
    }, 450);

    setTimeout(function () {
      if (onComplete) onComplete();
    }, 720);
  }

  function sendPhoto(file) {
    var state = el('div', { class: 'state', text: 'Sending…' });
    // A Live Photo saved as a video: show its first frame.
    var video = file.type.indexOf('video/') === 0;
    var img = el(video ? 'video' : 'img', video ? {} : { alt: '' });
    img.src = URL.createObjectURL(file) + (video ? '#t=0.1' : '');
    if (video) { img.muted = true; img.playsInline = true; }
    var li = el('li', {}, [img, state]);
    $('up-grid').prepend(li);
    $('recent-h').hidden = false;
    $('manage-photos-btn').hidden = false;
    var form = new FormData();
    form.append('file', file);
    return fetch('/api/photos', { method: 'POST', body: form })
      .then(function (r) {
        if (r.ok) {
          li.className = 'ok';
          return r.json().then(function (photo) {
            photoList.unshift(photo);
            if (photoCount !== null) { photoCount = photoList.length; showPhotoCount(); }
            li.setAttribute('data-name', photo.name);
            if (isManagingPhotos) {
              var badge = createDeleteBadge();
              badge.addEventListener('click', function (e) {
                e.stopPropagation();
                confirmDeletePhoto(photo, li);
              });
              li.appendChild(badge);
              li.addEventListener('click', function () {
                confirmDeletePhoto(photo, li);
              });
            }
            return true;
          });
        }
        li.className = 'err';
        state.textContent = r.status === 409 ? 'Already there'
          : r.status === 413 ? 'Over 10 seconds'
          : r.status === 415 ? 'Not a photo' : "Didn't send";
        return false;
      })
      .catch(function () {
        li.className = 'err';
        state.textContent = 'No connection';
        return false;
      });
  }
  $('up-file').addEventListener('change', function () {
    var input = this;
    var files = Array.prototype.slice.call(input.files || []);
    if (!files.length) return;
    var pick = $('up-pick');
    var added = 0;
    pick.classList.add('busy');
    $('up-done').textContent = '';
    var chain = Promise.resolve();
    files.forEach(function (f, i) {
      chain = chain.then(function () {
        $('up-t').textContent = 'Sending ' + (i + 1) + ' of ' + files.length;
        $('up-s').textContent = 'Keep this page open';
        return sendPhoto(f).then(function (ok) { if (ok) added++; });
      });
    });
    chain.then(function () {
      pick.classList.remove('busy');
      $('up-t').textContent = 'Add more';
      $('up-s').textContent = 'From this phone, as many as you like';
      input.value = '';
      $('up-done').textContent = added
        ? (added === 1 ? '1 photo added' : added + ' photos added') + ' to the slideshow.'
        : 'Nothing new was added.';
      if (photoCount !== null) { photoCount += added; showPhotoCount(); }
    });
  });

  // ── Start ─────────────────────────────────────────────────────────
  Promise.all([
    call('/api/devices'),
    call('/api/profiles'),
    call('/api/themes'),
    call('/api/cards'),
    call('/api/control').catch(function () { return { pin_required: true }; }),
    call('/api/now-showing').catch(function () { return {}; }),
  ]).then(function (r) {
    SC.devices = r[0];
    SC.profiles = r[1];
    SC.snapshot = !!r[4].snapshot;
    r[3].forEach(function (c) { S.cards[c.id] = c; });
    S.photo = r[5] && r[5].photo ? r[5].photo.name : null;
    // The QR on a "New screen!" display: straight to setting that one up.
    var setup = new URLSearchParams(location.search).get('setup');
    if (setup) {
      var fresh = r[0].filter(function (d) { return d.id === setup; })[0];
      if (fresh && fresh.kept) {
        location.replace('/menu?screen=' + encodeURIComponent(fresh.id));
        throw new Error('screens');
      }
      history.replaceState(null, '', '/menu');
      startScreens();
      if (fresh) openKeep(fresh);
      else toast('That screen has gone. Open it again to get a new code.');
      throw new Error('screens');
    }
    S.screen = pickScreen(r[0]);
    if (!S.screen || !S.screen.kept) {
      // No screen named, or one nobody has set up yet: the Screens page.
      if (WANTED && S.screen) history.replaceState(null, '', '/menu');
      startScreens();
      throw new Error('screens');
    }
    S.profile = r[1].filter(function (p) { return p.id === S.screen.profile_id; })[0] || r[1][0];
    S.themes = r[2].themes;
    S.pinRequired = r[4].pin_required;
    if (!S.pinRequired) {
      $('restart-lede').textContent = 'Both come back on their own afterwards.';
    }
    return refreshView();
  }).then(function () {
    renderAll();
    setDarkMode(getSavedDarkMode(), false);
    $('loading').hidden = true;
    $('app').hidden = false;
    route();
    if (S.screen.home && SC.snapshot) startLive();
    refreshTimers();
    checkAlarm();
    loadAlarms();
    refreshHealth();
    var darkToggle = $('dark-toggle');
    if (darkToggle) darkToggle.addEventListener('click', cycleDarkMode);
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
        if (document.documentElement.getAttribute('data-color-mode') === 'system') {
          setDarkMode('system', false);
        }
      });
    }
    if (window.navigator.standalone) {
      document.addEventListener('click', function (e) {
        var a = e.target.closest('a');
        if (a && a.getAttribute('href') && a.getAttribute('href').startsWith('#')) {
          return;
        }
        var sameHost = a && a.href && a.hostname === window.location.hostname;
        if (sameHost && !a.target && !a.hasAttribute('download')) {
          e.preventDefault();
          window.location.href = a.href;
        }
      }, false);
    }
    call('/api/photos').then(function (list) {
      photoList = list || [];
      photoCount = photoList.length;
      showPhotoCount();
      renderPhotoGrid();
    }).catch(function () {});
    setInterval(function () {
      if (document.hidden) return;
      refreshTimers();
      checkAlarm();
      loadAlarms();
    }, 15000);
    setInterval(function () {
      var c = document.querySelector('.tile.clock span');
      if (c) c.textContent = clockText();
    }, 15000);
  }).catch(function (e) {
    if (e.message === 'screens') return;
    $('loading').textContent = e.message === 'no screen'
      ? 'No screen is set up yet. Open the display once, then scan its code again.'
      : "Can't reach the screen. Make sure this phone is on the home Wi-Fi, then reload.";
  });
})();
</script>
</body>
</html>
"""
