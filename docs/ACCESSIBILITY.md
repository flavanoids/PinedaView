<!-- SPDX-License-Identifier: Apache-2.0 -->
# Accessibility

PinedaView targets **WCAG 2.1 AA** for the interactive surfaces (the
setup wizard, the Settings sheet, card detail views, and the layout editor).
The dashboard itself is a glance-and-go ambient display rather than a document,
so it is kept semantically quiet on purpose — but it is still operable and
readable.

## What's in place

**Keyboard**

- Every control is reachable with Tab, with a visible focus ring (a 2px accent
  outline plus a contrasting halo so it shows on any card colour or the glass).
- The wizard, Settings, Theme Studio, and card detail views are true modals: focus moves in
  on open, is trapped inside, returns to the trigger on close, and Escape
  closes them. Everything behind a modal is `inert`.
- Settings tabs are a real tablist — Arrow keys move between sections.
- Theme selection in Settings → Appearance uses an accessible `role="radiogroup"`
  with `aria-checked` states, keyboard Tab navigation, and Enter/Space selection.
- The layout editor has a keyboard path: Tab on the dashboard first offers a
  "Rearrange cards" button; once in, Arrow keys move the focused card and a
  live region announces each move. (Touch still uses long-press.)
- Cards that do nothing on tap are not focusable; only cards with a detail
  view, or the editor, expose a button role.

**Screen readers**

- The connection status is a polite live region, so "Reconnecting…" /
  "Offline" are announced.
- The word-of-the-day card marks each translation with its language (`lang`),
  and Arabic with `dir="rtl"`, so pronunciation and bidi are correct.
- Decorative glyphs (weather emoji, moon phase, pagination dots, theme
  swatches, QR frame) are `aria-hidden` or given a real label.
- Icon-only buttons (the gear, close buttons) have `aria-label`s.

**Motion & vision**

- **Settings → Accessibility** has explicit controls: Motion (Auto / Standard /
  Lite), Reduce transparency, Larger text, High contrast, Announce updates.
  They persist per device and override auto-detection.
- The OS settings are a floor that applies even with the toggle off:
  `prefers-reduced-motion`, `prefers-reduced-transparency`, `prefers-contrast`.
- `prefers-reduced-motion` / Lite also drop the Liquid Glass backdrop blur to
  zero, make the card fill opaque, and stop all card cycling.
- The Photo Clock's countdown ring (beside the date) is decorative
  (`aria-hidden`) and hidden under `prefers-reduced-motion`; on a Pi or Lite it
  steps twice a second instead of animating every frame.
- Auto-detection floors a Raspberry Pi (from its Chromium user agent) to Lite
  unconditionally, since its GPU can't back what `hardwareConcurrency` /
  `deviceMemory` alone would suggest. Unlike the general Lite tier, a detected
  Pi also drops `backdrop-filter` entirely (the property itself forces a
  compositor layer) rather than just zeroing its blur radius, so pinning
  Standard/Rich in Settings doesn't undo the saving.
- Touch targets for the standalone controls (gear, close) are at least 44px.

## Known gaps

- The dashboard has no heading outline — by design, but it means "navigate by
  heading" doesn't work there.
- Colour contrast of secondary text on the lightest theme cards is close to
  the 4.5:1 line; the default (Quiet Canvas) and Liquid Glass themes are
  comfortably above it, and High contrast lifts the rest.
- No automated axe/regression check yet — a11y is verified by hand and by the
  Svelte compiler's a11y warnings (which fail the lint gate).

## Reporting

File an issue with the assistive tech, browser, and what you expected. Small,
specific reports ("VoiceOver on iOS skips the Save button in the layout
editor") are the most useful.
