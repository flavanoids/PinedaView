# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Streamlined Phone Menu Navigation & Photo Clock Customization (`/menu`):**
  - **Intuitive Display Mode Terminology:** Replaced confusing "Clock only" labels with reactive **"Photo Clock"** (or "Clock" for plain mode), matching the full-screen photo slideshow with clock overlay.
  - **Direct Customization Without Mode Interruption:** Tapping the active mode button in the stage header now opens the customization sheet (`openClockStyle`) directly instead of abruptly turning off the mode.
  - **Dedicated Settings Section for Photo Clock:** Added a first-class Photo Clock customization section in `/menu#settings` featuring a live status badge ("Active now" / "Off"), an activation toggle, current look summary (font, glass look, layout, drift, weather), and a one-tap **"Customize Photo Clock"** button to tweak fonts, tints, glass effects, photo colors, transitions, motion drift, whisper, weather glyphs, and film grain.
  - **Ergonomic Bottom Tab Bar Alignment:** Renamed the second bottom navigation tab from "Cards" to **"Settings"** with a sliders icon, harmonizing the label, icon, and route (`#settings`).
  - **Deep-Linking Support:** Added direct routing for `#photo-clock` and `#clock` to open `/menu#settings` and launch the customizer sheet automatically.
  - **Night & Sleep Schedule Clarity:** Separated daytime Photo Clock activation from automated overnight dimming and sleep hours for clear configuration hierarchy.

- **Dual-Camera Picture-in-Picture (PiP) Takeovers:**
  - **Simultaneous Multi-Camera Livestreaming:** Upgraded `CameraService` and `GET /api/cameras/{name}/stream.mp4` to allow concurrent streaming of a primary camera and a secondary Picture-in-Picture camera without blocking or adding latency to the primary stream.
  - **Mobile-Style Picture-in-Picture Kiosk Layout:** Displays the secondary camera (e.g. garage) as a Picture-in-Picture window in the top-right corner over the full-screen primary camera (e.g. front door). Positioned with `calc(max(var(--space-4), env(safe-area-inset-right)) + var(--frame-x, 0px))` to strictly respect the physical picture frame inset (`frame_inset`).
  - **Dual Independent Loading Bars:** Both primary and PiP cameras feature blurred snapshot backdrops and independent progress indicators (`loadGuess` percentage, circular ring, and horizontal loading bars) while establishing their P2P livestreams, fading smoothly to sharp video once live.
  - **MCP & Takeover Protocol Extension:** Added `pip_camera` and `pip_title` to `CameraTakeover` schema and the `camera_show` tool.

- **Freeway Traffic Map Enhancements & Spatial Camera Pins:**
  - **Camera Spatial Pins:** Projections of configured DOT camera locations (`cam-marker`) directly on the freeway speed map, providing spatial correlation between the map and camera snapshots.
  - **Commute Delay Metrics:** Parses segment delay minutes (`args[13]`) from TranStar speed feeds and formats delay deltas (`(+Xm)`) directly on slowest bottleneck labels.
  - **Multi-Alert Rotating Ticker:** Automatically rotates through multiple bottlenecks, closures, and crashes every 9 seconds during the map slide's 40-second hold.
  - **Configurable Zoom (`mapZoom`):** Added `mapZoom` card setting (zoom 10–14, default 12) for tailoring the map to broad regional commutes or inner-loop neighborhoods.
  - **Visual Polish & Legend:** Distinct stroke hierarchy with soft glow on crawled segments (`<30 mph`), distinctive hazard markers for crashes, closures, and flooding, and a sleek 4-step speed legend.
  - **Touch & Keyboard Detail Mode:** Enabled `detail: true` on the traffic card manifest, allowing tap-to-expand full-screen inspection on touchscreens.

### Fixed

- **Traffic Map Incident Classification:** Broadened incident severity keyword parsing from `"accident"` to detect crashes, collisions, overturned vehicles, fires, closures, and flooding.
- **Traffic Map Resilient Caching:** `TrafficCamsProvider` now retains the last-good map payload across transient TranStar HTTP errors, serving cached data marked `stale: True` instead of dropping the map slide from rotation.

- **Photo Clock countdown ring:** a small ring right after the date pill's text, the height of its capitals, fills clockwise over each photo's hold to show when the next one comes. Hidden with reduced motion; steps twice a second on the Pi/Lite.
- **Alternate Mode Handoff Choreography & GPU Performance Polish:**
  - Upgraded handoff physics with a 3D parabolic curved arc (`midX`, `midY`, `midK` with adaptive apex lift) for glass numerals flying between the full-screen Photo Clock and dashboard clock card.
  - Eliminated font upscaling raster blur during expansion/contraction by docking the high-resolution vector glass stand-in through the flight and crossfading cleanly at near 1:1 scale at the target.
  - Replaced wild cross-screen card crossing with a coordinated, formation-based wave entry (`travelX` with tactile vertical settle and subtle `scale(0.965)`), preventing cards from overtaking and intersecting each other during assembly and disassembly.
  - Added bidirectional easing awareness (`SETTLE` deceleration for incoming views, `DEPART` acceleration for outgoing views) ensuring the background photo and card deck arrive with velvet deceleration rather than harsh stops.
  - Boosted GPU efficiency by batching layout measurements, appending flight stand-ins via `DocumentFragment`, pre-promoting card cells with temporary `willChange` compositor flags, and clearing conflicting Web Animations.
  - Added subtle physical 3D drop-shadow (`filter: drop-shadow`) to in-flight glass figures and synchronized fade for the date capsule.
- **Alternate Mode Kiosk Settings Control:**
  - Added "Alternate with cards" toggle in `Settings → Night & sleep` (`NightSettings.svelte`). Allows kiosk displays to directly activate the alternating rotation between the full-screen Photo Clock (60s) and card dashboard (30s), complete with staggered card assembly, disassembly, and numeral flight/expansion animations.
- **Visual Theme Picker & SPA Theme Studio:**
  - Upgraded theme selection in `Settings → Appearance` from a plain text dropdown to an accessible, responsive visual thumbnail grid (`ThemePreviewCard.svelte`) displaying live mini stage backgrounds, card slot chips, accent indicators, and surface treatments.
  - Added an in-app `ThemeStudio.svelte` modal sheet for desktop, tablet, and kiosk users to create, clone/remix, edit, and delete custom themes directly from the SPA with live preview, real-time WCAG contrast scoring, and font selection.
  - Added 1-click Theme JSON Export and Import directly inside `ThemeStudio` for easy clipboard backup and theme sharing across kiosks.
  - Added color harmony and night-twin generation tools (`lib/themeHelpers.ts`) to instantly generate balanced monochromatic, analogous, complementary, and vibrant palettes from a single seed color, as well as 1-click darkened night variants.
  - Added typed custom theme CRUD client methods (`createCustomTheme`, `updateCustomTheme`, `deleteCustomTheme`) and exported `CustomColours` in `@pinedaview/protocol`.
- **Declarative File-Based Themes (`themes_dir`):**
  - Added declarative theme loader (`load_file_themes`, `parse_theme_dict`) in `pinedaview.themes` and `themes_dir` configuration setting in `config.py`.
  - Supports defining custom themes via `.toml` or `.json` files in `themes/` with automatic luminance and ink calculation, full card slot overrides, glass surface flags, and optional `[night]` tables that automatically link paired night twins.

### Fixed

- **Alternate keeps one photo across the handoff:** the Photo card now starts on (and, while warming out of sight, follows) the Photo Clock's photo, and the clock starts back on the card's — no more cutting to a different photo (`lib/photoShare.svelte.ts`). The clock also holds its photo while the cards warm up, since its 30 s swipe used to land right on the 60 s handover.
- **Traffic cams show again in Alternate mode:** the deck remembers its slide and the time left on it across remounts. The 30 s cards phase was shorter than the map's 40 s hold, so every phase restarted on the map and the cams never came up.
- **Home cams (doorbell/garage) blank:** Antigua's hardened `UMask=0077` left its snapshots root-only, so pineda-web couldn't read them; Antigua now writes them `0644` (fixed in the Antigua repo).

- **Photo Clock Legibility, Subject Depth & Layout Consistency:**
  - **Dark-Photo Contrast & Legibility:** Added reciprocal `gloomOf` contrast boost in `web/src/lib/glass.ts` and `web/src/lib/glassDigits.ts`. When background photo luma is low, the liquid glass increases diffuse milkiness and introduces an ambient inner luminescence, preventing "ghost glass" and ensuring high legibility on dark evening skies or foliage.
  - **Refined Specular & Chamfer Profile:** Raised `specPow` to 80 and `rimPow` to 3.8 in the `liquid` glass look. Eliminates the bloated "inflatable balloon gel" effect and gives the numerals crisp, optical-glass reflections and refined chamfered edges.
  - **Per-Digit Subject Avoidance:** Updated `chooseSpot` in `PhotoClock.svelte` to evaluate per-digit worst coverage (`worst`) in addition to average area coverage. If the center spot would obscure a subject's face, helmet, or forehead (exceeding `MAX_HIDDEN_DIGIT`), the time reliably moves to an unhindered spot rather than forcing the clock layer on top of the subject.
  - **Header Date Capsule Placement:** Constrained date pill placement in `PhotoClock.svelte` to top corners (`tl` or `tr`). Prevents the pill from jumping to the bottom edges (`bl` or `br`), keeping status information consistently and elegantly framed in the top bar.

### Security

- **Never reachable from outside the LAN.** A tunnel hostname had been
  publishing the whole app to the internet. The new `pineda-web-guard`
  (nftables, installed and enabled by the .deb/.rpm) lets `:8090` answer only
  loopback, wg0 and private addresses. It also rejects connections from
  tunnel processes (cloudflared, via a systemd `NFTSet=` drop-in), so tunnel
  ingress can't expose the dashboard. Outbound data fetches are unchanged.
  Google OAuth now uses a static bounce page only. See
  `docs/OPERATIONS.md#keeping-it-on-the-lan` and ADR 0032.
- **Dev toolchain advisories cleared.** `pnpm audit` (high+) had failed CI
  on every push since 10-12. tinypool, via vitest, had two critical
  prototype-pollution-to-RCE advisories (GHSA-5gmw-xhrv-c9v3,
  GHSA-85c8-ppgw-ccpr), and source-map-js, via vite/postcss, a high
  event-loop DoS. Both are test/build-time only and never shipped to
  screens. `pnpm.overrides` now pins tinypool ^2.1.2 (vitest 3 runs on it:
  all 211 web tests pass) and source-map-js ^1.2.2.

### Performance

- **Photo Clock Rendering & Resource Efficiency:**
  - **Single-Decode Photo Pipeline:** Eliminated up to 4 redundant `HTMLImageElement` allocations and JPEG decompressions per photo step in `PhotoClock.svelte`. The decoded image from `photoFor()` is reused directly to generate the 40px glass frost preview and canvas bake.
  - **In-Memory Frost & Mask LRU Caching:** Added bounded `maskCache` and `frostCache` stores. Photos looping in the slideshow resolve masks and frost in 0ms without re-fetching, decoding, or re-running alpha threshold scans.
  - **Sub-Pixel Clock Formatting Memoization:** Memoized `formatClock()` in `format.ts` by minute timestamp and format style. Avoids ~60 redundant `Intl.DateTimeFormat` / `toLocaleDateString` calls and object allocations per minute across all clocks and cards while returning identical references to downstream Svelte derived signals.
  - **Tier-Aware Liquid Glass Canvas Baking:** Capped bake canvas devicePixelRatio to 1.0 on `lite` motion tier (Raspberry Pi, low-power kiosks, battery-saver mode) and 1.5 on high-DPI displays in `glass.ts`, reducing pixel counts and buffer allocations by up to 75%.
  - **Glass Inner-Loop Acceleration:** Replaced `at(x, y)` closure lookups with inline integer coordinate clamping, substituted `Math.hypot` with direct `Math.sqrt` and reciprocal multiplication, reused temporary buffers across multi-pass box blurs, and skipped `Math.pow(spec, 60)` evaluations for sub-threshold highlights.
  - **Mask Digit Coverage & Corner Optimization:** Reduced digit coverage sampling iterations from ~20,000 to ~3,000 by aligning sample steps to scale while maintaining identical statistical coverage accuracy over the 96px mask.
  - **Dynamic Compositor Layer Management:** Restricted `will-change: transform` to active transitions and Ken Burns drift animations, freeing GPU memory and avoiding persistent multi-layer VRAM pressure during idle photo display.
  - **HTTP Cache-Control on Photo Assets:** Added `Cache-Control: public, max-age=86400` headers to `/api/photos/{name}`, `/display`, `/subject`, `/thumb`, and `/motion` static endpoints in FastAPI to eliminate repeated revalidation requests from kiosk displays.
  - **Lazy-Loaded Welcome & QR Code Generator:** Dynamically imported the Welcome onboarding screen and QRCode generator on first connection, keeping the initial client startup bundle lightweight for paired kiosk displays.

### Changed

- **Unconditional Cursor Suppression on Raspberry Pi:** Mouse and touch
  cursors are now unconditionally suppressed (`cursor: none !important`)
  whenever running on a Raspberry Pi (`data-platform="pi"` stamped on
  `<html>`, unless previewing another screen on desktop). An inline script
  in `web/index.html` synchronously stamps `data-platform="pi"` before the
  DOM or CSS parses, eliminating any pointer flicker during cold boots.
  The reference `packaging/pineda-kiosk.service` also appends `?pi=1` to the
  launch URL to guarantee immediate kiosk provisioning.

### Added

- **Picture frame.** A screen hung in a frame that covers its sides can say
  how much (phone menu → Screen shape → Picture frame, 0–20% each side;
  `frame_inset` on the device). Photos, wallpaper and tints still fill the
  whole panel under the frame's lip. The time, date and weather pill, the
  cards, the now-playing slab, takeovers, pop-ups and the gear move in by
  that much at their full size: nothing is scaled down, and the cards
  reflow into the width that's left. The Photo Clock's calm-spot shift and
  date corner, and the clock ⇄ cards handoff, all land inside the frame.
  ADR 0034.

- **Photo Clock time stays readable.** The glass reads how bright the photo
  is behind it: over a pale sky or wall it takes less milk, a little smoke,
  a darker far rim and a deeper shadow, so the figures keep an edge; over
  dark photos it's unchanged. Each photo also picks where the time sits
  across the top (left, middle or right): the middle unless a side is
  clearly calmer (sky rather than branches) or the subject would stand over
  most of the middle. The time fades out and back in at its new spot during
  the swipe, and the date pill keeps clear of it.
- **Photo Clock order and minute turn.** Photos are shuffled instead of
  played in upload order, and none comes round again until about three
  quarters of the library has been shown; the list of recent photos is kept
  across reloads. Near-copies from the same burst aren't shown back to back.
  The pick leans gently towards the time of day: brighter photos by day,
  warmer ones around sunrise and sunset, darker and warmer ones at night,
  and photos taken around this hour. New uploads still come up next. When
  the minute changes, the old figures dissolve over the new ones, so only
  the changing digit crossfades.
- **Music on the clock.** While AirPlay is playing, the Night / Photo Clock
  shows a small Liquid Glass card in the bottom-right corner: mini album art,
  title and artist. Fixed width; a longer title or artist wraps and the card
  glides taller (or shorter) to fit, and a new track's art and text
  crossfade. Paused, loading or stopped, it fades away. On the Photo Clock
  its glass is the figures' own live WebGL glass (lib/glassDigits.ts, same
  look, light, rim and shadow, bending the photos as they swipe): a rounded
  slab baked once at its tallest (lib/glass.ts `bakePanel`) and drawn
  sliced to any shorter height, so the resize never waits on a bake. Flat
  glass, the hands face or no WebGL keep a CSS glass stand-in. The date pill keeps
  out of that corner while it's up, and the view now carries the
  now-playing data whenever music plays, even under a pinned hero card.

- **Photo Clock: live glass that follows the photos.** The time's glass
  used to be a still, baked over the photo as it sat. A swiping or drifting
  photo slid under glass that didn't move, and the next photo's glass
  swapped in halfway through the swipe. Now the figures' shape is baked once
  a minute (the next minute ahead of time), and WebGL bends both photos
  through it every frame they move (`web/src/lib/glassDigits.ts`). The
  glass's seam travels with the photos', and the minute turns with no wait.
  Without WebGL, the CPU bake still draws it.
- **Photo Clock: iOS-style glass, and a Crystal look.** The rim is built
  from a true distance to the outline, so corners stay round instead of
  squaring off. It's shaped after Liquid Glass: clear in the middle, with
  the bending and a thin two-sided rim light at the edge. Looks are presets
  in `web/src/lib/glass.ts`. Glass now offers Liquid, Frosted, Crystal
  (new: a brighter rim, more colour split, almost no fill) and Flat, in the
  phone menu and in Settings.

- **Display UI & Motion Architecture Polish (iOS/Android Fluidity for 15.6" 1600p 60Hz Display):**
  - **Tactile Initial Card Landing Cascade:** Upgraded the display first-boot entrance from a static fade to a 2D Euclidean spatial cascade (`translateY(16px) scale(0.96) -> 1` with `--ease-spring-snappy` deceleration), where cards land like physical widgets settling onto the display surface.
  - **Hardware-Calibrated Ambient Loading Indicator:** Replaced unstyled static text with a glowing dual-ring pulse indicator tuned for high-DPI displays.
  - **Synchronized Theme Crossfade & View Transitions:** Integrated `document.startViewTransition` on theme changes with CSS property fallbacks on `body` and cards, ensuring backgrounds, text, borders, and shadows interpolate synchronously without color flash or contrast tearing.
  - **Organic Clock View Dissolve & Scale:** Eliminated harsh cuts when entering Night Clock / sleep mode and tapping to wake, introducing a smooth 450ms tranquil dissolve and subtle scaling transition tailored for IPS monitor black levels.
  - **Shared Container Transform on Card Details:** Tapping an expandable card fluidly expands the modal dialog outward from the tapped card tile's exact bounding box with FLIP spring physics, and contracts seamlessly back on dismissal.
  - **Standardized Motion Design Tokens:** Added `--dur-normal (320ms)`, `--dur-slow (700ms)`, `--ease-spring-snappy (cubic-bezier(0.16, 1, 0.3, 1))`, and `--ease-spring-gentle (cubic-bezier(0.22, 1, 0.36, 1))` in `tokens.css`, with automatic 0.01ms zeroing for `lite` and reduced-motion tiers.
  - **Elevation Physics & Dynamic Hero Polish:** Added smooth elevation shadow lifting/settling during card rearranging and synchronized opacity handoff during Dynamic Shuffle hero morphs.
  - **Takeover & Alarm Transitions:** Added spring scale-in and fly-in transitions to Alarm and Recipe takeovers.

- **Mobile Companion Navigation & Performance Polish (UI/UX, 120Hz ProMotion Fluidity):**
  - **Isolated Subpage View Transitions:** Scoped CSS view transitions strictly to `.deck-pages` (`deck-content`) while setting `animation: none` on the stage header and bottom tab bar, ensuring top preview and bottom navigation remain rock-solid stationary during tab switches.
  - **Bidirectional Navigation Detection:** Implemented tab order mapping so navigating right-to-left animates backwards and left-to-right animates forwards with 160ms/240ms native deceleration curves.
  - **Tab Scroll Position Retention:** Retains scroll offset per tab across navigation so returning to Settings or Themes never resets the user's scroll position to the top.
  - **Active Tab Tap-to-Top:** Tapping the currently active tab smoothly scrolls the page back to the top, matching standard iOS native tab bar UX.
  - **Zero-Latency Optimistic UI Updates:** Theme swatch selections and screen toggles instantly update the DOM state, tokens, and pinned live preview within a single 120fps frame before network resolution, with automatic rollback on failure.
  - **Haptic Spring Touch Physics:** Added iOS-calibrated cubic-bezier spring physics (`cubic-bezier(0.34, 1.56, 0.64, 1)`) and active transforms to tabs, chips, swatches, quick pills, switch thumbs, and card items with chevron nudges.
  - **Z-Index Hierarchy & Toast Stacking:** Raised modal scrims to `z-index: 100` and toasts to `z-index: 50` with elevated clearance above the 52px bottom navigation bar, preventing clipped dialogs or hidden toasts.
  - **Reclaimed Subpage Real Estate:** Completely removed obsolete top-left back links across all views in favor of direct tab bar navigation, reclaiming 44px of vertical screen real estate.

- **Photo Management & Deletion with Animated Trashcan Feedback:**
  - **Manage photos companion controls (`/menu#photos`):** Added a dedicated "Manage photos" button to the "Add photos" companion hub alongside the uploader and recently uploaded photos. Tapping toggles manage mode with interactive deletion badges on each thumbnail across the library.
  - **Deletion confirmation modal:** Accessible confirmation dialog displays a preview of the photo being deleted, clearly informing the user that all versions, cutouts, and thumbnails will be permanently removed before executing.
  - **Delightful trashcan deletion animation:** Photo tiles undergo a choreographed sequence where an animated trashcan lid opens, the photo tile crumples and gets sucked down into the can, the lid snaps shut with an impact bounce, and burst particles emit as the tile smoothly collapses.
  - **Exhaustive version and derivative cleanup:** Deleting a photo thoroughly purges the original file, cached display copies, thumbnails, AI depth cutouts, and Live Photo motion video clips on disk.


- **Mobile Companion Overhaul & iOS Standalone PWA ("Add to Home Screen").**
  - **Pinned WYSIWYG Stage Header:** Miniature preview of the physical display stays persistently visible at the top while scrolling through settings and themes, allowing immediate visual feedback when tweaking swatches, clocks, and display modes.
  - **Ergonomic Bottom Tab Bar:** Replaced cumbersome top-left back navigation with a fixed 5-tab thumb-friendly navigation bar (`Look`, `Cards`, `Photos`, `Alarms`, `Device`) designed specifically for one-handed operation on modern flagship iPhones (iPhone 17 Pro, 18 Pro Max).
  - **Decoupled Phone Companion Dark Mode:** Decoupled the phone interface's color scheme from the physical display's theme. Phone dark mode persists in `localStorage` and a 1-year cookie (`pineda_menu_dark_mode`) with zero flash of light on boot, even if the living room display is set to a bright daytime theme.
  - **Full Edge-to-Edge Standalone iOS Support:** Added PWA web manifest (`/manifest.json`), touch icons (`/apple-touch-icon.png`, `/apple-touch-icon-precomposed.png`), and `black-translucent` status bar support. Safe-area insets (`env(safe-area-inset-top)` and `env(safe-area-inset-bottom)`) ensure perfect clearance of Dynamic Island and the home indicator pill bar in zero-button standalone mode.
  - **In-App Standalone Navigation Guard:** Internal navigation uses hash routes and intercepts links to keep users seamlessly inside the fullscreen standalone web app without kicking them out to Safari.

- **Minimal Photo Clock Enhancements & Customization.**
  - **Stacked & Row Digits Layout (`layout`):** Choose between clean horizontal `12:45` single-row display or 2-line stacked digits (`12` over `45`, without colon) ideal for portrait framing, vertical displays, and edge-heavy photos. Integrated with multiline liquid glass baking and intelligent 4-digit occlusion depth tucking.
  - **Ken Burns 3D Spatial Parallax Drift (`drift`):** Gentle 1.00× → 1.04× background zoom across 30 seconds paired with a slower, anchored foreground subject cutout (1.00× → 1.015×), creating an authentic stereoscopic depth effect running purely on the GPU compositor at 60fps.
  - **Soft Gallery Crossfade Transition (`transition`):** Added a serene 1.2s cross-dissolve alternative (`transition: "fade"`) to the 0.85s carousel swipe curve (`transition: "swipe"`), with smooth halfway glass frost and cutout handoff.
  - **Memory Whisper Context (`whisper`):** Subtle context capsule softly fades in 3s after photo arrival, displaying authentic camera EXIF capture time (e.g., `October 2021 · 5 yrs ago`), lingers for 5 seconds, and softly dissolves into the photo.
  - **Weather in Corner Date Capsule (`weather`):** Current temperature and condition emoji glyph subtly appended into the existing floating date capsule (`Thu, Oct 15 · 72° ☀️`) with no added visual clutter or widgets.
  - **Analog Fine-Art Film Grain (`grain`):** Adjustable 0% to 25% organic film grain texture overlay softening digital LCD glare with zero per-frame rendering overhead.
  - **Phone Menu & Settings UI Controls:** Added live reactive switches, segmented selectors, and range sliders with concise, clear explainers in the phone menu (`GET /menu` under Clock only) and the dashboard Settings sheet (`Night & sleep` → `Photo clock`).

- **Dynamic Shuffle & Ambient Card Rotation Loop.**
  - **Hero card spotlighting:** Every active dashboard card takes turns expanding into the hero spotlight for a configurable dwell time (10s, 15s, 30s, or 60s; default: 15s).
  - **Compositor-only 60fps FLIP animations:** Expands cards from their source grid tiles into the hero slot and returns them home seamlessly via Web Animations API (`transform: translate3d(...) scale(...)` + `opacity`) without triggering grid reflows or layout shifts.
  - **Photo card exemption:** In Dynamic Shuffle mode, the small photo grid card is omitted (the full-screen Photo Clock handles photography), establishing the clock as the default anchor hero.
  - **Hands-free ambient cycle (Option C):** When running the full-screen Photo Clock, screens automatically wake into the card dashboard every N minutes (2m, 5m, 10m, or 15m; default: 5m) for `peek_s` (default: 60s) before returning to photos.
  - **Unbroken rotation queue:** Remembers card queue progress in `localStorage` across dashboard sessions and wake cycles so screens never repeat the same cards.
  - **Hero view upgrades:** Upgraded 8 built-in cards with dedicated, glanceable Hero layouts: `indoor_climate` (thermostat dial, HVAC pill, humidity grid), `moon` (celestial hero glyph and illumination), `timer` (large countdown digits and active badges), `forecast` (7-day extended forecast grid), `calendar` (agenda layout with week columns), `on_this_day` (full-resolution memory photo), `traffic` (traffic cam feed and status chips), and `phrase` (display typography with pronunciation).

- **MCP server at `/mcp`.** A voice assistant (Antigua) drives the display
  through MCP tools instead of REST: status, themes, now showing, takeovers,
  timers, restart/reboot and the cameras. It speaks the stateless 2026-07-28
  protocol over Streamable HTTP. Every call needs a client's bearer token
  (only its SHA-256 is in the config) with the tool's scope, and each call is
  written to `mcp_audit.db`. `pineda-web mcp-token <client>` makes a token. Spec
  and roadmap (faces, LLM tool calling, events): `docs/MCP.md`.
- **The camera card balloons up full screen.** It inflates out of the
  bottom-right corner in 1.4 s and shrinks back there when it's done. While
  the video connects, the camera's last snapshot sits blurred and dimmed
  behind a progress ring with a guessed percentage; the live picture fades in
  over it. "LIVE" shows only once video is playing.
- **This server runs the camera livestream.** With `[cameras] ha_url`, the
  Eufy livestream starts in Home Assistant when a camera card goes up and
  stops the moment it comes down. The video relay waits for the start and
  retries go2rtc's early errors. A camera put up over a recipe sets the
  recipe aside and brings it back afterwards.
- **Documentation audit & continuous AI coder synchronization rules.**
  Comprehensive audit of all project documentation against active codebase.
  Added workspace root `AGENTS.md` and `.agents/rules/docs-maintenance.md`
  establishing a hard rule and Codebase-to-Documentation Mapping Matrix so any AI
  coder or human contributor updating code in a commit must update the matching
  docs in the same turn. Updated `CONTRIBUTING.md` with standing synchronization rules.

- **A smoother, livelier Photo Clock swipe.** The next photo now comes in
  quick, eases off, meets the edge and bounces back about 20 px before
  settling, in 0.85 s (a CSS `linear()` curve, still a compositor-only
  transform). Each swipe keeps 60 fps in a Pi-speed test (8–12× CPU
  slowdown) where it used to drop to 11–16 fps. The glass was being re-baked
  every second, not every minute (the clock's `parts` is a new object each
  tick); it now bakes once a minute, and the next photo's glass is baked,
  and its pictures decoded, before the swipe starts, so nothing heavy runs
  while photos move. The glass's drop shadow is baked into it instead of
  being a CSS filter redrawn every frame. The date pill fades out during the
  swipe and comes back in the new photo's clearest corner, so its backdrop
  blur isn't redrawn over the moving photos. Bundle budget 109 → 110 kB.
- **Photo Clock glass opacity, live.** Settings → Night & sleep swaps the
  four-step Fill choice for a **Glass opacity** slider (0–100 %, from clear
  glass to milky). The baked glass now uses the whole range, so each step
  shows. **Preview** opens the Photo Clock full screen with the opacity,
  glass and size controls on top, so each change shows as you drag. The
  phone menu's Clock sheet has the same slider and glass choice, and the
  screen follows as you move it. The Photo Clock's settings are now kept on
  the server for each screen (`photo_clock`) instead of in the kiosk's
  browser, so any screen's Settings can change them. Settings the kiosk
  already had are moved to the server the first time it connects.
- **A rebuilt Settings sheet.** Every section now uses the same controls
  (labelled rows with a one-line explanation, switches, segmented choices),
  shows its current state under its title, says who it applies to (the
  house, a profile, one screen, or this device), and ends with **Reset to
  defaults**, which spells out what it will reset first. A toast confirms each
  save or says why it failed. Sections: Appearance, Time & weather, Cards &
  layout, Photos, Night & sleep, Timers, Accessibility, Screens & profiles,
  Backup & server, Help. With more than one screen, **Settings for** at the
  top edits another screen — the way to reach a locked wall kiosk.
    - **Time & weather:** 12- or 24-hour time; the date under the clock full,
      short or hidden; "Find my location".
    - **Appearance:** an accent colour over any theme; **After sunset** (the
      theme's own night colours, no change, or any other theme); the
      background image on every theme, not just Liquid Glass; a clock face
      for every screen on the profile.
    - **Cards & layout:** turn cards off per screen; a large-card pin per
      profile as well as per screen; **Rotation speed** (relaxed / normal /
      brisk) for the quote, phrase, news, traffic and camera cards; **Hide
      topics** skips headlines and quotes mentioning chosen words.
    - **Photos:** hold time (10 s – 5 min), order (yours, newest first,
      shuffle), framing (fill or whole photo), and guest uploads allowed,
      held for approval, or off.
    - **Night & sleep:** night-clock start times for weeknights and weekends
      and an end time (any hour, including before midnight), how long a tap
      shows the dashboard, and dimming on a schedule.
    - **Timers:** one-tap presets, and a chime, bell or beep (per device) when
      a timer ends, on every screen.
    - **Screens & profiles:** copy another screen's settings; the settings
      button, mirror and removal (with a confirm) per screen.
    - **Backup & server:** download every setting as a file and restore it.
    - API: `GET /api/config/backup`, `POST /api/config/restore`,
      `POST /api/config/reset`, `POST /api/devices/{id}/copy-from`,
      `GET /api/photos/pending`, `POST /api/photos/{name}/approve`,
      `POST /api/photos/library` (the owner's upload, past any guest policy).
      `ViewModel.prefs` carries the formatting, timing and night-schedule
      preferences to each screen.

### Fixed

- **Photo Clock: the person no longer shows twice.** With depth on, the
  subject cutout drifted less than its photo (a parallax) — but the subject
  is still in the photo underneath, so the two slipped apart over each
  30 s hold, leaving a ghost outline and a doubled person. The cutout now
  drifts exactly with its photo, on the photo's animation clock.
- **Replaced `BaseHTTPMiddleware` with pure ASGI middleware.** FastAPI's
  `@app.middleware("http")` wraps handlers in Starlette's `BaseHTTPMiddleware`,
  which synthesizes an empty body chunk upon client disconnect. When browsers
  aborted in-flight photo downloads or switched to camera streams, `h11` raised
  `LocalProtocolError: Too little data for declared Content-Length`. The correlation
  ID, authentication, and standby redirection middlewares now use pure ASGI callables,
  completely eliminating these spurious tracebacks.
- **Graceful shutdown on SIGTERM.** Added `timeout_graceful_shutdown=5` to Uvicorn
  and `TimeoutStopSec=15` to `pineda-web.service`. Persistent SSE clients (`/api/stream/{device_id}`)
  previously caused Uvicorn to wait indefinitely for connections to close, resulting
  in a 90s systemd timeout and SIGKILL. The server now cleanly terminates long-lived
  connections and runs lifespan cleanup in < 5 seconds.
- **Quieted expected camera warmup logs.** In `logging_config.py`, the `httpx` logger
  is now set to `WARNING` level unless debug logging is enabled. This silences
  both the expected HTTP 500 retry logs while battery cameras warm up their P2P livestreams
  and high-frequency routine data poll logs.
- **Cleaned up `pineda-web-guard` boot warning.** The `ExecStartPost` and `ExecReload`
  nftables hooks now verify `/sys/fs/cgroup/system.slice/cloudflared.service` exists before
  adding it to `tunnel_units`, preventing `Could not parse cgroupsv2 path` errors when the
  system boots before cloudflared starts.

- **`test_display_tools_are_fast` asserted 5 ms p50; the spec budget is 8.**
  `docs/MCP.md` sets read-only display tools at p50 ≤ 8 ms. Loopback here
  measures 1–2.4 ms, but shared CI runners land around 6.5 ms, so main's CI
  failed on hardware rather than on a regression. The test now enforces the
  documented 8 ms.

- Changing units, location or the countdown in Settings now survives a
  server restart (kept in `<state_dir>/household.json`, which the standby
  sync already copies; `config.toml` is left alone).
- Clearing a screen's blackout times actually clears them.
- Saving the traffic card's camera list no longer empties it.
- The photo card's "Seconds per photo" option, which the slideshow ignored,
  is gone; Photos → Show each photo for replaces it.

- **Fonts, and themes that come with one.** A font picker (kiosk Settings →
  Display, and the menu's Themes page) sets the type for everything but the
  clock and keeps it across theme changes. Twenty-five faces, all SIL OFL,
  Latin subsets with Spanish accents: grotesks (Google Sans Flex, Atkinson
  Hyperlegible Next, Zalando Sans, Geist, Mona Sans, Inter, Instrument Sans,
  Hanken, Schibsted, Host Grotesk), rounded and display faces (Parkinsans,
  Funnel Display, Unbounded, Bricolage, Fredoka), serifs (Instrument Serif,
  Young Serif, Playfair, Newsreader), Geist Mono, Caveat handwriting, and
  pixel faces (Pixelify Sans, Jacquard 24's pixel blackletter), plus Roboto
  and Aileron. **Make your own** now has a Font row too, so "Sunday Morning"
  can be its colours _and_ Young Serif.
    - `Profile.font` (`PATCH /api/profiles/{id}`, `""` clears it) wins; when
      it's unset, a theme's own `Theme.font` applies; otherwise the theme's
      usual type. `POST`/`PUT /api/themes/custom` take an optional `font`.
    - Antigua needs no change: it reads `/api/themes` fresh and sets the
      profile's theme, so "switch to the Sunday Morning theme" brings the font
      along, and switching to a built-in theme drops it. A profile-wide font
      still outranks a theme's, so saving a theme with a font in the menu
      clears the screen-wide one.
    - Instrument Serif, Young Serif and Jacquard 24 come in one weight; bold
      in them is synthesised.
- **The news card**, in place of did-you-know. The server reads public-service
  and independent outlets' RSS feeds (NPR, BBC, PBS NewsHour, Al Jazeera, The
  Guardian; NASA, ScienceDaily, Mongabay, Reasons to be Cheerful and Positive
  News for good news; Houston Public Media, Houston Landing and KHOU for local)
  and sorts the stories into **beats**: US, World, Good news and Houston out of
  the box. Each beat is its outlets, the topics that pull a story in (`AOC`,
  `midterm*`, `ICE` — capitals match only capitals, so not an ice storm), the
  ones that keep a story out, a weight and a maximum age. A beat gets its
  keyword matches first, then the feeds' freshest when matches are thin; no
  outlet takes more than two of its slots, and the same story from two outlets
  shows once. The card takes the beats in turn.
    - Every story sits over **its own picture** — the feed's, or the article
      page's share image (outlets' stand-in logos are skipped) — shrunk and
      blurred on the server, so the Pi shows a ~10 KB finished JPEG with no CSS
      blur. Pictures are held in memory only while their story is on screen
      (`GET /api/news/{id}.jpg`). A scrim in the picture's own colour keeps the
      headline readable.
    - The QR opens the article at the outlet with its tracking tags removed —
      never a redirect, which is why Reuters and AP (no direct-link feeds) are
      not offered.
    - **Quiet hours** (10pm–5am by default): nothing is fetched; the card keeps
      cycling what it has. **Soften mornings** (5–8am by default) leaves out
      headlines built around deaths and attacks.
    - Beats are edited in the phone menu's card settings (and the tablet's
      Settings sheet): feeds as checkboxes, topics as comma lists, plus any
      other RSS address. A change re-sorts the stories already in hand at once.
- Saving a card's settings now polls its provider straight away instead of at
  its next turn.

### Removed

- **The did-you-know card.** Saved layouts move its slot to the news card on
  startup.

### Changed

- **The two QR codes sit in opposite corners, on frosted plates.** The
  photo card's "Settings" code moves to its top-left corner (label beneath),
  and the kiosk shows news in the bottom-right cell so its "Read" code takes
  the opposite corner. Both codes now sit on a translucent white plate
  instead of solid white, so the photo or story picture shows through
  while they still scan reliably.
- **The QR codes lose their white box.** The photo card's "Settings" label
  overflowed its badge; now the label is white type on a dark fade out of the
  photo's corner (a gradient, not a blur, so the Pi's crossfade stays cheap),
  and only the code keeps a thin white quiet zone for scanning. The news
  card's "Read" code matches, with its label up to caption size.

- **The phone menu is a hub now.** `/menu` (the photo card's QR) opens on a
  home page instead of one long scroll: the live miniature of the screen,
  "Your screen" with a one-line summary, a quick-access row (**Timer**,
  **Alarm**, **Clock only**) and four big buttons — **Themes**, **Add
  photos**, **Settings**, **Device** — each showing something current (the
  theme's colours and name, how many photos there are, whether the screen
  is healthy). The three pages behind them are picked by the URL hash
  (`#themes`, `#settings`, `#device`), so the phone's back gesture works;
  old `/menu#look` links (the `/settings` redirect) now land on `#themes`.
    - **Themes**: the theme swatches, "Make your own", the clock face and the
      Liquid Glass background picture.
    - **Settings**: "Arrange this screen" first, then card settings, then the
      Night section.
    - **Device**: health for the screen's Pi and the server, then the PIN-gated
      restarts.
- **Card settings are a grid of this screen's cards.** The long alphabetical
  accordion — every card, each labelled "On this screen" / "Not on this
  screen" — is replaced by chips for just the cards on this screen that have
  something to set, in the order the screen shows them, each dotted with its
  theme colour. Tapping one opens its settings in a sheet. Cards that aren't
  on this screen fold away under "Not on this screen (n)".
- **"Arrange this screen" moved up**, out of the old Cards section to just
  above the theme picker (and now leads the Settings page).
- **The night clock can be switched off, or held on.** The small-hours clock
  (Mon–Fri 0–5am, Sat/Sun 2–5am) was always on; each screen now has a **Night
  clock** switch (on by default, same as before) and, under it, **Keep the
  clock on**, which shows the clock right away, day or night, until it's
  switched off. New device fields `night_clock` / `night_clock_hold`, passed
  through the view model; switching the night clock off releases a held
  clock. **Clock only** on the menu's home page is the same hold.
- **Alarms show when they go off, not a countdown.** Wherever a running timer
  appears (the timer card, the home-cams pill, the moon & climate cluster),
  an alarm reads "7:00 AM" instead of "480m00s".
- **The photo card's QR badge says "Settings"**, so a guest knows what it's
  for before scanning.
- **The layout builder only offers recently seen screens** (the last 30 days),
  each labelled with its size: the live server had 182 paired devices, nearly
  all long-gone browser tabs called "Screen".

### Removed

- **The brightness slider.** Every screen runs at full brightness; the menu's
  Screen section became **Night** (night clock, keep the clock on, go dark
  overnight). The `brightness` device field and the dimming overlay are
  still there for anything that sets them through the API.

### Fixed

- **The dashboard's service worker no longer claims server pages.** Its
  navigation fallback now skips `/menu`, `/upload`, `/connect` and `/api`, so
  a browser that has opened the dashboard (or the layout builder) over a
  secure origin is never handed the dashboard in place of the phone menu.
- **Dry-day radar gap.** A hidden radar now leaves the grid, so the last card
  (did-you-know on the kiosk) stretches into the gap instead of an empty cell.
  It only keeps its empty slot when now-playing would be the card stretched.
- **Cyclers froze on the first item.** Every SSE view-model push re-evaluates
  a card's `facts.length`-style `count` prop with a fresh array identity, and
  a raw getter prop has no value check — so the Cycler's effect restarted
  and reset to item 0 on each push, which lands every few seconds. No
  rotating card (affirmations, phrases, did-you-know facts) ever outlived one
  dwell. The Cycler now routes `count` through a derived, which only
  invalidates when the number itself changes.

### Added

- **A live miniature of the screen on the phone menu.** The sketch at the top
  of `/menu` is now the real dashboard, running read-only in an iframe on
  the phone and scaled to the miniature's width — same cards, same photo,
  same clock, updating live from the same stream the screen reads. It costs
  the Pi nothing (the phone does the drawing) and the server one more SSE
  connection. It fades in over the old sketch once it has connected, with a
  small "Live" badge.
    - `/?preview=<device id>` is the dashboard's read-only mode: it never pairs
      the phone as a screen, never writes localStorage, never reports what it
      shows, and hides the gear and status pill.
    - A screen's clock face, Pi mode and text scale live in its own browser
      (launch-URL flags and localStorage), so the dashboard now reports them —
      `POST /api/now-showing/look`, open like the other now-showing reports —
      and `GET /api/now-showing?device_id=` returns them as `look` for the
      preview to copy (`forceScale` pins the text scale).
    - The preview's photo card doesn't run its own slideshow: it follows the
      photo the screen last reported, crossfading when the screen does.
- **Device health on the menu.** The new **Device** page shows, for the
  screen's Raspberry Pi and for the server: how busy it is in plain words
  (Relaxed / Steady / Busy / Overloaded, with the load and core count
  underneath), memory in use, free storage, temperature (warm at 70 °C, "hot
  enough to slow itself down" at 80 °C) and how long it's been running,
  refreshed every 5 seconds while the page is open. A screen that hasn't
  reported for three minutes says when it was last heard from.
    - `pinedaview.system.local_stats()` reads `/proc` and `statvfs` — a few
      tiny file reads.
    - The Pi's AirPlay bridge (`pineda-airplay-bridge`) publishes its own stats
      once a minute as a retained `<topic>/stats` MQTT message; the server's
      MQTT bridge keeps the latest, and `GET /api/system` returns
      `{server, screen}`.
- **Alarms.** **Alarm** on the menu sets a time of day (with an optional
  label) — tomorrow if that time has already passed today — and lists the
  ones set, each cancellable. When one goes off, every screen shows a
  full-screen **alarm takeover** (new takeover `kind: "alarm"`): the label,
  the time set large in the clock's Fraunces, and a slow breath of the
  theme's accent behind it (opacity only; still under the Lite tier and
  reduced motion). It stays up for ten minutes, over the night clock too,
  until it's turned off — by a tap on a touchscreen, or **Turn off the
  alarm**, which appears on the menu's home page while one is ringing.
    - Timers gained `kind: "timer" | "alarm"` (`POST /api/timers` takes it);
      `TimerService` calls an `on_fire` hook, and the runtime puts up the
      alarm takeover when an alarm fires. Plain timers behave as before.
    - Alarms are in memory, like timers: a server restart before one goes off
      forgets it. There's no sound.
- **Make your own theme.** The theme picker ends with a **Make your own**
  tile: name it, pick a background, a highlight and colours for most cards,
  the clock card and the quote card, watching a live preview; the writing on
  top picks itself (light or dark, whichever contrasts better), so the
  theme stays readable whatever the colours. Saving applies it straight
  away. Themes you made show an **Edit** link; one can be deleted once the
  screen isn't using it.
    - Stored in a new `custom_themes` table and served in `/api/themes`
      alongside the built-in ones (`custom: true`).
      `POST /api/themes/custom`, `PUT`/`DELETE /api/themes/custom/{name}`
      (admin paths; delete answers 409 while a profile uses the theme).
    - The view model carries `theme_rev`, which bumps on every save, so live
      screens fetch the theme list again and repaint in the edited colours
      without a reload.
- **Arrange this screen — the layout builder.** `/layout?screen=` (from the
  menu) gives one screen a hand-placed layout, Lego-style: every card is
  **Small** (one cell), **Medium** (two cells wide) or **Large** (the big
  spot, pinned top-left or top-right; at most one). Small and Medium cards
  click into the first free spot in order, so nothing is placed freeform
  and a layout can't get messy; free spots show as studs on a baseplate.
  Drag a card onto another and the two trade places (the shape stays put);
  **Earlier** / **Later** move a card along the order; the × on a selected
  card, or "Remove … from the screen", takes it off, with an undo. Cards
  come back from an **Add a card** tray.
    - Edits are a draft until **Save** (with an undo toast); undo/redo, and
      **Undo all** (it used to say "Discard", which read like "discard this
      card") goes back to what's on the screen.
    - **Earlier layouts** brings back any of the last 10 saved; **Copy to
      another screen**; **Let the screen arrange itself** returns to the
      automatic layout.
    - Warns before the photo card (and with it the settings QR) comes off,
      when the photo would be too small for the QR to scan, and about cards
      that would come out very small, short or narrow on the real screen.
    - The server keeps the layout in `devices.grid` (a column count plus a box
      per card) with a `layout_history` table: `PUT /api/devices/{id}/grid`,
      `GET /api/devices/{id}/grid/history`. The biggest box is the hero
      (countdowns and weather alerts still take it), and nothing reflows — a
      card with nothing to show today leaves its spot empty. Screens without
      a grid keep the automatic `card_stack` flow.
    - It began as a free drag-and-resize snap grid; on a phone that was fiddly
      and messy, so it became the brick model above. The saved format didn't
      change.

- **The did-you-know card.** A fact-of-the-day for grown-ups: the server polls
  Wikipedia's live "Did you know" feed — the curated hooks the encyclopedia
  itself rotates onto its main page, a fresh set a few times a day — and the
  card cross-fades through the current 5–9 facts (a ~24s dwell, cycling dots
  off to keep the card quiet), each stated plainly ("... that tardigrades can
  survive the vacuum of space?" reads "Tardigrades can survive the vacuum of
  space."). An eyebrow tags the fact's topic (space, nature, medicine,
  science, history, …) from a keyword read, and a QR in the corner opens the
  article the fact promotes — scan to read more. `fetchHosts` pins it to
  `en.wikipedia.org`; a dead network leaves the last good set, marked stale.
- **Home cameras card, in the moon & indoor climate card's place.** With
  `[cameras] snapshots_dir` set, the `home-cams` mini card shows the
  doorbell and garage photos Antigua takes every so often (one at a time,
  10s each), served from `/api/home-cams/{name}.jpg`. A battery under
  Antigua's warning level puts a red "Battery 17% · charge it soon" note on
  that camera's photo; a running timer shows as a pill in the corner.
  `moon-climate` is retired (in the default `disabled_cards`): startup puts
  `home-cams` in its slot on every saved stack.
- **Camera takeover — a live doorbell or garage camera, full screen.** A
  takeover with `kind: "camera"` names a camera from `[cameras.streams]` and
  plays it from `/api/cameras/{name}/stream.mp4`, a relay of go2rtc's
  fragmented MP4 that answers only while that camera's takeover is up (the
  server has no auth). Beside the video: the title and a caption Antigua
  changes with `PATCH {caption}` ("Identifying…", then who it is). Antigua
  starts and stops the camera's livestream itself.
- **Full-screen takeover — the first full-screen card.** `PUT /api/takeover`
  covers every screen with one card until `DELETE /api/takeover` or its
  `seconds` (default 120) run out; the view model carries it as `takeover`.
  The one kind so far is a recipe (title, source, servings, time, grouped
  ingredients, numbered steps), drawn in the theme's colours and fonts with
  the text sized to fit and a bar draining along the bottom. Antigua puts up
  the recipe it's reading, and `current_step` highlights the step it's
  reading (`PATCH /api/takeover` moves it without re-showing the card).
- **The recipe follows along.** Once the steps start, the recipe card shows
  the step being read as large as it fits, with the one before above it and
  the one after below, smaller and dimmed; "next" slides the ladder, a jump
  crossfades, and a dot per step shows how far along it is. The ingredients
  shrink to a rail that lights the lines the current step uses. Before the
  steps, the list fills the screen beside a preview of step 1, lighting the
  line being checked or asked about. New card fields: `stage`,
  `current_ingredients`, `checked`, `skipped` and `swaps` (struck through,
  "→ coconut milk"). `PATCH /api/takeover` now changes only the fields it's
  sent.
- **How-to guides on the recipe card.** A card with `kind: "howto"` reads as
  a household guide ("How to" over the title, "You'll need" over the
  supplies), and its `caution` line (power tools, ladders, chemicals) stays
  in the footer the whole time it's up.
- **Voice-assistant hooks (Antigua).** `GET /api/now-showing` says which
  photo and quote each screen has up (the Photo and Traffic/quote cards
  report every swap to `POST /api/now-showing`, open like guest photo
  uploads) with the photo's EXIF date, the quote's author and year, and the
  day's Spanish phrase. `PUT /api/timers/sync/{source}` mirrors another
  system's running timers here, and the moon-climate mini card turns 2×2
  while one runs: the soonest in the bottom-left quadrant, "+N" for the rest.

- **The calendar card, Google and/or Apple.** Connects entirely from a phone —
  scan the QR on the (blocked) calendar card, or visit `/connect-calendar` /
  `/connect-apple-calendar` directly. Google uses OAuth 2.0 (Authorization
  Code + PKCE, read-only `calendar.readonly`) via a small static "bounce" page
  the operator hosts, since Google requires an HTTPS redirect URI a bare LAN
  device can't offer on its own; see `docs/INSTALL.md#calendar-google--apple`
  for the five-minute Google Cloud setup. Apple/iCloud uses CalDAV over HTTP
  Basic auth with an app-specific password — no OAuth exists for iCloud, so
  that's the whole "connect" step. Both list every calendar the account can
  see, including ones shared with you, and revisiting the connect page once
  already connected refreshes that list in place (no re-auth) so a
  newly-shared calendar shows up on its own. A `type` tag on each saved
  calendar keeps the two backends from clobbering each other's selections.
  Card scales `strip` (a compact agenda) up to `hero` (day/week/month, opt-in
  via the usual `hero_card` pin) — see `CARD_MANIFEST.md` for the settings.

- **Remote restart, from the photo card's QR.** The QR now opens `/menu`, a
  small switchboard (photos, theme, **Restart display** / **Restart
  Raspberry Pi**) instead of dropping straight into the uploader. The
  hardened service account can't `sudo`, so the buttons reach systemd over
  D-Bus via a polkit rule (`packaging/pineda-restart.rules` — the `.deb`
  installs it automatically; manual setups need one `install` + a polkit
  restart, see `docs/INSTALL.md`). A phone-sized theme/wallpaper sheet
  (`/settings`) is linked from the same menu.

- **Split-host `[control]`.** The server no longer has to run on the same
  box as the kiosk it's displayed on — see
  `docs/OPERATIONS.md#running-the-server-on-a-different-box-than-the-kiosk`.
  When it doesn't, the QR-menu restart/reboot buttons need `[control]`
  configured (`host`/`user`/`ssh_key`) so they SSH to the actual kiosk
  device instead of acting on the server's own host; a forced-command
  wrapper on the kiosk side (`packaging/pineda-control-wrapper.sh`)
  restricts that key to exactly the two actions the buttons issue. Unset by
  default — a single-device install is unaffected.

- **Pin the hero card.** A profile (or a single device) can now set `hero_card`
  to override the automatic hero pick — Settings › Devices › **Hero card**
  (Automatic / any card in that screen's stack). A now-playing / countdown /
  alert takeover still wins. Additive on `Profile` and `Device` (openapi regen).

- **The indoor-climate card.** A new built-in polls the home's AC telemetry
  server (`ac-data-server` on primary-server, port 8321, read-only) every ~90 s and
  shows the indoor temperature with humidity, setpoint, outdoor temp, and the
  compressor's last 30-min runtime. Values are normalized to SI server-side
  (the client formats per unit, like the weather card). The provider degrades
  the same way every other one does: on a bad payload it raises and retries,
  and the store keeps its last good value (the card just goes stale).
  `permissions.fetchHosts` pins it to `192.0.2.171`.

- **The affirmation and phrase cards cycle again.** Bringing back the legacy
  app's rotation: the server now sends the day's _set_ of ~5 quotes
  (`dailyContent.affirmations`, deterministic and still honouring the 60-day
  no-repeat window on the lead quote), and a shared `Cycler` component
  cross-fades the affirmation card through them (~27s) and the phrase card
  through its four languages (15s, matching the old `PHRASE_CYCLE_SECONDS`),
  each with a row of cycle dots. Lite / reduced-motion swap hard instead of
  fading. `dailyContent.affirmation` (singular) stays for older clients.

- **Album art on the Now-playing card.** The MQTT bridge now understands
  shairport-sync's `publish_parsed` fields (title / artist / album / genre /
  year) and `publish_cover` (the album-art JPEG on `…/cover`, held in memory
  and served at `GET /api/nowplaying/cover`). The card shows the cover, and
  fills the screen with it as the hero while music plays. `docs/NOW_PLAYING.md`
  covers the shairport-sync config.
- **Now-playing animations.** The cover crossfades and the text slides in on a
  song change; the cover springs down and dims when paused (lock-screen style);
  a small equalizer animates beside "Now playing" and disappears when paused.
  All tied to `--dur-mid` so Lite / reduced-motion make them instant.

### Fixed

- The Now-playing bridge now handles shairport-sync's plain `playing` / `active`
  topics, ignores stale retained `play_*` events (they were wiping a live
  track), keeps the track visible while paused, and re-resolves card readiness
  when the broker connects (the card was staying greyed). `now-playing` is in
  the default card stack.

### Changed

- **The weather card is now a three-page rolodex.** Replacing the single
  front/back flip, it cross-fades on a dwell timer (~13s, with cycle dots)
  through: **Now** (conditions, place, today's high/low, feels-like, wind,
  humidity, UV) → **Later today** (the 3-hourly walk through the rest of the
  day, rolling into tomorrow once today runs out, with rain-chance and
  sunrise/sunset) → **Next 3 days** (the daily outlook with a shared hi/lo
  range bar, warm-to-cool tinted). This folds the old standalone forecast
  strip into the one card; radar stays on its own card. Hero and tile render
  the same three pages, tighter on the tile.
- **Weather now comes from Open-Meteo** (keyless, structured, reliable)
  instead of wttr.in. The provider geocodes the configured location by name
  (unless it's already `lat,lon` or the config pins coordinates), pulls
  current + hourly + daily, maps WMO codes back to the glyph set the client
  already knows, and trims the hourly feed to a ~24h 3-hourly walk (not the
  raw 96-row wall). It still surfaces `coords` + `place` for the
  air-quality / alerts / radar providers to follow. `fetchHosts` →
  `api.open-meteo.com`, `geocoding-api.open-meteo.com`.
- **Night-aware weather glyphs.** Hourly slots (and the current conditions)
  carry an `isDay` flag now; a clear or partly-cloudy slot after dusk shows a
  moon instead of ☀️, so a 3am forecast row reads right. Rain-chance shows a
  small 💧 in a calmer colour instead of the old sage-green percent.
- **The clock tile echoes the hero.** Its non-hero face is now the "stack"
  composition shrunk to fit — hour over minutes in Fraunces, no colon, a
  quiet date line — instead of the plain one-line time.
- **The page cycler pauses on a closer look.** Weather / affirmation / phrase
  stop their dwell timer while a pointer is over the card or focus is inside
  it (so the detail view doesn't flip away mid-read) and while the tab is
  hidden; the weather hero's pages also drift up slightly on the turn rather
  than a straight dissolve.
- **The photo frame owns the hero slot; the clock drops to a tile.** Family
  photos fill the big 2×2 cell now, and the time moves to a normal grid tile
  (its compact face). When a screen has no photos the clock keeps the hero,
  and a now-playing / countdown / alert takeover still overrides both.
- **Settings reorganized.** The six equal tabs are now labelled, collapsible
  sections (Display · Content · Cards & layout · Accessibility · Photos · This
  screen · Server · Help) with a search field that filters and auto-expands
  matching sections. Theme and background image moved to their own **Display**
  section; a "Rearrange the card layout" button lives under **Cards & layout**.
- **Photo editor.** Tap a thumbnail to rotate it 90°, move it up/down in the
  slideshow order, use it as the Liquid Glass background, or delete it. Photos
  now carry an explicit `sort` order (`POST /api/photos/reorder`), and
  `POST /api/photos/{name}/use-as-wallpaper` hands a photo to the wallpaper.
- Tests: `photos_dir` is now sandboxed per test (it was writing to the real
  `data/photos`).

### Accessibility

- **Accessibility settings panel.** Motion (Auto / Standard / Lite, persisted
  per device), Reduce transparency (drops the glass blur, opaque cards),
  Larger text, High contrast, and Announce updates (speaks alerts / now-playing
  to a screen reader). Each also honours the matching OS media query
  (`prefers-reduced-transparency`, `prefers-contrast`) as a floor. The `-soft`
  / `-faint` text tiers are now derived in CSS so High contrast can strengthen
  them.

- **Modals are real modals.** The setup wizard, Settings sheet, and card
  detail views trap focus, return it to the trigger on close, close on Escape,
  and mark everything behind them `inert` (`use:modal`).
- **Keyboard layout editing.** Tab on the dashboard offers a "Rearrange cards"
  button; Arrow keys then move the focused card, with each move announced.
  Cards with no tap action are no longer spurious tab stops.
- Settings tabs are a proper tablist (Arrow-key navigation). The connection
  status is a polite live region. The word-of-the-day card marks each
  translation with `lang` (and `dir="rtl"` for Arabic). Decorative glyphs are
  `aria-hidden`; icon buttons have labels; standalone touch targets are ≥44px;
  the focus ring gained a contrasting halo. `docs/ACCESSIBILITY.md` added.

### Added

- **Liquid Glass theme.** Frosted translucent cards floating over a wallpaper,
  with the top sheen and specular rim ported from the Pi's
  `_draw_liquid_glass_chrome`, concentric 28px corners, and the system SF type
  stack (real SF on Apple devices, zero bytes). Themes now carry a `surface`
  field (`solid` / `glass`); the client switches the whole card treatment from
  it. The backdrop blur is tied to a token the Lite tier and reduce-motion drop
  to zero while making the fill opaque, so it stays readable on weak hardware.

- **Custom Liquid Glass background.** Settings → Content → Background image (only
  shown when a glass theme is selected): upload any JPEG/PNG/WebP and the panes
  float over it; leave it empty for the built-in dawn gradient. `PUT`/`GET`/
  `DELETE /api/wallpaper`, and a `wallpaper_rev` on the view model so a new
  upload repaints live displays without a reload.

- **Scan-to-add-photos.** The photo card now shows a QR in the corner (and a
  full-card QR when the frame is empty) pointing at a new standalone `/upload`
  page — a tiny self-contained document, not the SPA — so anyone on the LAN can
  add photos from their own phone. `POST /api/photos` is exempt from
  `write_token` for this; rotate and delete still require it.

- **Photo card animations ported from the Pi.** Photos are fitted (letterboxed
  against the card, never cropped) and cross-dissolve on an 8s-hold / 2s-fade
  cycle, matching the framebuffer module. Honours reduced-motion and the Lite
  motion tier (static, no cycling).

- **Photo management in Settings.** A new _Photos_ tab uploads (multi-select),
  previews as a thumbnail grid, and deletes photos for the photo-frame card,
  plus a toggle to show/hide the photo card on the current display. Adding the
  first photo turns the card on automatically. `photo` is also back in the
  default card stack (it stays hidden until a photo exists).

- **App icons.** A warm sunrise-over-horizon mark on black, matching the
  PinedaDisplay palette. Ships `favicon.svg` / `favicon.ico` for tabs, a 180×180
  `apple-touch-icon.png` so "Add to Home Screen" on iOS gets the real icon
  instead of a page snapshot, and 192/512 plus a maskable 512 in the web
  manifest for Android/desktop installs. `index.html` also declares
  `apple-mobile-web-app-capable` and a translucent status bar for a clean
  full-screen launch.

### Fixed

- **Standalone home-screen app clipped its top card under the notch / Dynamic
  Island.** The stage now pads by `env(safe-area-inset-*)` (falling back to the
  normal gap) so `viewport-fit=cover` no longer runs content under the status
  bar or home indicator.
- **Cards clipped their content on phones.** Three causes, found testing on a
  real handset: `Flip.svelte` positioned both faces absolutely so the weather
  hero collapsed to the row minimum; `grid-auto-rows: minmax(min, auto)` (and
  plain `auto`) collapse a row to its minimum when a flex-item card is the only
  thing in the track and the grid overflows its scroll container; and big emoji
  under-reported their height with `line-height: 1`. Flip now stacks its faces
  in one CSS-grid cell, the stage uses `grid-auto-rows: max-content` with a
  per-cell `min-height` floor, and glyph line-heights were relaxed.
- **`forecast` and `air-quality` built-in cards rendered as a raw JSON dump**
  via the generic fallback — they had no web component. Added `Forecast.svelte`
  (3-day high/low with glyphs) and `AirQuality.svelte` (US AQI + category band +
  PM2.5 / ozone).
- The Phase-10 `content-visibility: auto` on off-screen cards is removed — it
  contributed to the clipping and saved nothing on a 6–12 card stack.

### Changed

- Type scale mins reduced (`--type-hero`, `--type-xl`, `--type-lg`, `--type-md`)
  so a phone-width dashboard isn't oversized.

### Fixed

- **Standalone home-screen app clipped its top card under the notch / Dynamic
  Island.** The stage now pads by `env(safe-area-inset-*)` (falling back to the
  normal gap) so `viewport-fit=cover` no longer runs content under the status
  bar or home indicator.

### Added

- **Phase 10 — Hardening & 1.0.** Deep `GET /api/health` — `ok` plus
  per-subsystem `checks` (database, scheduler, broker, store freshness) and
  `uptime_s`; returns **503** when the database is down (this is the Docker
  `HEALTHCHECK`). New `GET /api/metrics` (Prometheus text) and a no-JS
  `GET /status` operator page. Every request now carries a correlation id —
  `X-Request-ID` on the response and `req_id` on every log line it produces.
  Optional `api.admin_token` splits the surface: the admin routes (config,
  secrets, control, setup, profiles, devices, card settings) require the bearer
  token on reads too; the public surface stays open. Client hardening:
  `content-visibility` on off-screen cards, an idle throttle that pauses
  decorative animation after 60 s untouched or when the tab is hidden, and
  battery awareness (`getBattery()` → effective tier drops to Lite when unplugged
  and low, keeping the user's preference). `SECURITY.md` rewritten with a threat
  model; a CI `audit` job runs `pnpm audit` + `pip-audit`. `docs/OPERATIONS.md`
  added. Version is `1.0.0`. 163 core tests, 37 web.
- **Phase 09 — Packaging & release.** The compiled web client is now bundled
  _inside_ every artifact (`scripts/stage-web.sh` → `pineda_web/webroot/`, served
  by `mount_web()` with a `/assets` mount + an `index.html` SPA fallback; the
  server runs API-only when it's absent). A multi-stage `Dockerfile` (node build
  → `python:3.12-slim`, non-root, `HEALTHCHECK`) + `docker-compose.yml`; one
  `packaging/nfpm.yaml` produces both `.deb` and `.rpm` (bundled venv at
  `/opt/pineda-web/venv`, a hardened systemd unit, a `pineda` system user,
  `/etc/pineda-web/config.toml` kept on upgrade); `scripts/install.sh` for
  `curl … | sh`; `pipx install pineda-web` carries the client. Config lookup
  gained `$PINEDA_CONFIG_FILE` and `/etc/pineda-web/config.toml`, with the full
  precedence documented and tested. The release is SemVer `0.9.0`; `__version__`
  comes from installed metadata and shows at `GET /api/health` (`app_version`)
  and the foot of the Settings sheet. `release.yml` (on `v*` tags) publishes to
  PyPI, pushes a multi-arch `ghcr.io` image, and attaches per-arch packages to a
  GitHub Release; a CI `package` job smoke-tests the image on every push.
  `docs/INSTALL.md` covers every path. 157 core tests.
- **Phase 08 — Secret-gated cards & integrations.** Secrets are now Fernet-
  encrypted at rest (`secrets.enc` + a machine-local `secrets.key`, `chmod 600`);
  a corrupt file degrades to empty and only names are ever exposed. The scheduler
  gained a `sync()` that reconciles running poll loops against the live provider
  list, so adding a Maps key **hot-starts the Commute provider without a
  restart** and removing it stops it — the card un-greys / re-greys with no
  reload. An optional MQTT bridge (`[mqtt] enabled = true`, paho on its own
  thread) maps `airplaypi/track|play_start|play_end` read-only into the
  `nowPlaying` store, driving a new **Now playing** folder-card (progress bar)
  that runs alongside a live PinedaDisplay; `mqtt:<topic>` needs resolve once the
  broker connects. `POST /api/ingest/{store}` lets any outside system (Home
  Assistant, a cron job) publish a value into a store and feed a card with no
  `provider.py`. An optional `api.write_token` gates every write with a bearer
  check; reads stay open (per-IP rate-limiting deferred to Phase 10). A new
  Settings › **Cards** tab renders each manifest's settings schema (boolean /
  int / enum / timerange / list, with a "Label | Address" editor for the commute
  stops). `docs/API.md` + published OpenAPI. Deps: `cryptography`, `paho-mqtt`.
  149 core tests.
- **Phase 07 — Onboarding & Help.** A fresh server (no `config.toml`) opens a
  seven-screen wizard instead of the dashboard: Welcome, Location (with keyless
  IP geolocation and manual fallback), Numbers & time, Look, Cards + optional
  Maps key, This screen (name + a 24-frame motion benchmark), Add more screens
  (QR). Every step defaults, "Skip — use defaults" is always there, and the
  draft persists so it's resumable. `POST /api/setup/complete` writes the config
  file and flips `setup_complete`. A searchable in-app **Help** sheet (14
  entries, tag-matched) covers settings, layout editing, profiles, the Commute
  key, motion, reconnecting, HTTPS/install and writing a card. The Settings
  sheet's Content and Server tabs are now functional (`ConfigForm`), and
  "Run setup again" re-opens the wizard.
- **Phase 06 — Multi-device & profiles.** One server drives many screens, each
  with its own profile. `POST/PATCH/DELETE /api/profiles` (delete is guarded —
  not the default, not one in use); a device points at a profile and the view
  model projects it. Pairing now returns a 4-digit code; **Settings › Devices**
  (a gear-opened sheet) lists every screen with an editable name, profile picker,
  brightness slider, mirror picker, **Identify** (a targeted SSE flash) and
  **Remove**. Per-device columns `brightness` / `blackout_start` / `blackout_end`
  / `follow` layer over the profile; `ViewModel` gained `profile_name`,
  `brightness`, `blackout` (window wraps past midnight), and the client
  `Overlay` dims / near-blacks accordingly. All additive under v0.
- **Phase 05 — Touch & layout editing.** A pointer-event gesture layer
  (`classifyGesture` + a `use:gesture` action) drives tap, long-press and swipe.
  Long-press enters a layout editor: drag cells to reorder with FLIP reflow, then
  save to **this screen** (per-device `card_stack` override) or **the profile**.
  Tapping a card flagged `detail` in its manifest opens it full-size. The photo
  card swipes between images and crossfades. `Flip.svelte` does CSS-3D rotateY on
  Standard/Rich and an instant swap on Lite; the weather hero flips conditions ↔
  metrics. `square` and `material` layouts join `wide`; `material` restyles via a
  `data-layout` token block. A locked device ignores the editor. Server:
  `devices` gained `card_stack` / `layout` / `locked` columns, `ViewModel` gained
  `locked` and per-card `detail`, `PATCH /api/profiles/{id}` was added — all
  additive under v0. 32 web tests.
- **Phase 04 — The card SDK.** A card is a folder with a `card.json`. Manifests
  (`CardManifest`) declare `needs` (`location`, `network`, `photos`,
  `secret:<key>`, `mqtt:<topic>`, `provider:<store>`), `provides`, `slots`,
  `refresh`, `settings`, `tier`, `permissions.fetchHosts`. The loader merges
  bundled built-ins with a user `cards/` dir; `CardRegistry.resolve()` is a
  fixpoint that marks each card `ready` or `blocked` with a reason. Only ready
  cards get a running provider and appear in a screen's stack. A `SecretStore`
  (file + env, `chmod 600`, never serialized) backs `secret:` needs and
  `ctx.secret()`; `ctx.fetch_json` enforces the per-card host allow-list.
  `PhotoStore` + `/api/photos/*` (upload, thumbnails, rotate, delete) and the
  `photos` need. `GET /api/cards`, `/api/cards/{id}/settings`, `/api/secrets`.
  `pineda-web dev` hot-reloads manifests. `scripts/new-card.sh`,
  `docs/CARD_MANIFEST.md`, `docs/CARD_SDK.md`. The 11 built-ins are now folder
  cards; core has no card-specific branching. Deps: pillow, python-multipart,
  watchfiles. 111 core tests.
- **Phase 03 — Web client shell.** A Svelte 5 + Vite PWA that renders the live
  dashboard: `Connection` streams the view model over SSE (`EventSource`,
  reconnect-aware, last-good cached in `localStorage`); `Stage` lays cards into a
  JSON-driven responsive grid; `Card` / `Metric` / `WeatherGlyph` chrome; clock,
  weather, affirmation, phrase, moon cards plus now-playing / countdown hero
  variants. Three motion tiers keyed off `<html data-motion>`, auto-detected,
  with `prefers-reduced-motion` as a hard floor. `packages/tokens` holds the
  structural CSS variables and an `applyTheme()` that paints the server's
  palette. The clock and the countdown tick client-side. `ViewModel` gained
  `units` and `data` (store payloads for the on-screen cards) so a screen
  renders in one round trip. Bundle ~21 KB gzip; 19 web unit tests.
- **Phase 02 — The protocol.** FastAPI + SSE API on one Uvicorn process; the
  scheduler and timer loops run inside its lifespan. A pure `build_view_model`
  turns (state, profile, stores) into a finished `ViewModel` the client just
  renders. `GET /api/view/{device}` and a live `GET /api/stream/{device}`
  (snapshot then a fresh view model on every change, heartbeats between).
  `GET/POST /api/config`, `/api/themes`, `/api/devices` (SQLite registry with a
  seeded default profile, pair / patch / unpair), `/api/control/state`,
  `/api/timers`. Four-state machine (idle / playing / countdown / alert) with an
  **optional, off-by-default** weekday countdown. The v0 contract is frozen: the
  OpenAPI schema is exported to `packages/protocol/openapi.json` and a typed
  TypeScript client is generated from it, both CI-checked. 82 tests, 95 %.
- **Phase 01 — Headless core.** `pineda-web serve` runs a headless async data
  engine: typed `pydantic-settings` config (TOML + env + CLI), a `Provider` +
  `Scheduler` pair, and named stores (`weather`, `airQuality`, `alerts`, `moon`,
  `dailyContent`) that keep the last good value and flag it stale. Weather is
  normalized to SI; air quality and alerts follow the resolved coordinates.
  Content (affirmations, multilingual words, weather glyphs) vendored from
  PinedaDisplay with the MD5-of-date daily rotation intact. Flag-gated
  `GET /_debug/stores`. 46 tests, 94 % coverage. Nothing from the framebuffer,
  OLED, Antigua, or hardware-profile layers carried over.
- **Phase 00 — Foundations & scaffolding.** Monorepo layout (`core/`, `web/`,
  `packages/*`, `cards/`), pnpm workspace, `core` as a `uv`-managed Python
  package. Full quality gate wired and green: ruff + ruff-format + `mypy --strict`
    - pytest (≥85 % coverage) for Python; eslint + prettier + svelte-check + vitest
    - `size-limit` (≤100 KB) for the web client. GitHub Actions CI, pre-commit
      hooks, and an SPDX-header check.
- Planning docs: `docs/EPIC.md`, `docs/ROADMAP.md`, `docs/DECISIONS.md`,
  `CONTRIBUTING.md`.
