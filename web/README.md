# @pinedaview/client

The dashboard, as an installable web app. Svelte 5 + Vite. Renders the view
model the server streams over SSE; no display logic lives here.

```bash
# from the repo root, in one terminal:
uv run --project core pineda-web serve --location "Austin"

# in another:
pnpm --filter @pinedaview/client dev      # http://localhost:5173, /api proxied to :8090
```

Set `VITE_API_URL` to point the dev proxy elsewhere.

## Layout of the source

| Path                            | What                                                                              |
| ------------------------------- | --------------------------------------------------------------------------------- |
| `lib/connection.svelte.ts`      | SSE stream → current `ViewModel`, reconnect status, `localStorage` last-good      |
| `lib/time.svelte.ts`            | ticking clock + `remaining(target)` for the countdown                             |
| `lib/tier.svelte.ts`            | motion tier detection (`lite` / `standard` / `rich`) → `<html data-motion>`       |
| `lib/platform.svelte.ts`        | Raspberry Pi & platform detection (`detectPi`)                                    |
| `lib/daypart.ts`                | solar elevation / daypart ambient tint calculation                                |
| `lib/photoPick.ts`              | Photo Clock's next photo: shuffle, recent memory, bursts, time-of-day lean        |
| `lib/photoShare.svelte.ts`      | The photo on screen, shared by the Photo Clock and Photo card across a handoff    |
| `lib/display.svelte.ts`         | blackout window, brightness, and screen state management                          |
| `lib/frame.svelte.ts`           | picture-frame inset (`frame_inset` → `--frame-x`): content moves in, photos fill  |
| `lib/clockface.svelte.ts`       | clock face registry, selection, and preview state                                 |
| `lib/edit.svelte.ts`            | layout editor and card rearranging state                                          |
| `lib/idle.svelte.ts`            | idle detection (`data-idle="true"`) to pause decorative work                      |
| `lib/settle.ts`                 | settled value change easing action                                                |
| `lib/balloon.ts`                | camera card's inflate/deflate transitions (spring out of the bottom-right corner) |
| `lib/loadGuess.ts`              | guessed load percentage for the camera card while its video connects              |
| `lib/wizard.svelte.ts`          | first-run onboarding wizard flow and drafts                                       |
| `lib/shuffle.svelte.ts`         | dynamic shuffle queue controller, card dwell timers, and ambient rotation         |
| `lib/cellMotion.ts`             | 60fps FLIP animation elevating cards into the hero slot                           |
| `lib/coverTint.ts`              | an album cover's average colour, for tinting the glass/panel it sits on           |
| `lib/themeHelpers.ts`           | WCAG luminance, dynamic ink contrast calculation, and palette harmony generation  |
| `layouts/*.json` + `resolve.ts` | responsive grid config (`wide_grid`, `square_grid`, etc.) picked by width         |
| `components/`                   | `Stage`, `Hero`, `Card`, `ThemeStudio`, `ThemePreviewCard`, `Settings`, etc.      |
| `cards/`                        | one Svelte component per card id + `index.ts` registry fallback                   |

Motion tiers and the on-hardware visual pass: see
[`../docs/phases/PHASE_03.md`](../docs/phases/PHASE_03.md).
