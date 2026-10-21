# `card.json` reference

A card is a folder under `cards/` (or a built-in shipped in
`core/src/pinedaview/cards/builtin/`). Its `card.json` is validated at startup;
an invalid one is logged and skipped, never fatal.

```jsonc
{
    "id": "weather", // required · kebab or reverse-dns (com.acme.aurora)
    "name": "Weather", // required
    "version": "1.0.0",
    "description": "",
    "author": "you",

    // What the card can't run without. An unmet need greys the card in the
    // picker with the first missing thing named — it never crashes.
    "needs": ["location", "network"],
    //   "location"          a place is configured
    //   "network"           outbound HTTP allowed (always granted for now)
    //   "photos"            the photo library has >= 1 image
    //   "secret:<key>"      a named secret is present (e.g. "secret:google_maps")
    //   "mqtt:<topic>"      the broker is connected (for now-playing)
    //   "provider:<store>"  some other ready card publishes that store
    "optionalNeeds": [],

    // Stores this card publishes for itself and others.
    "provides": ["weather"],

    // A built-in provider key, or "module.path:ClassName" for your own.
    "provider": "weather",
    "refresh": { "interval": "15m", "jitter": "90s" }, // duration strings only

    // Size hints. min/ideal/max ∈ strip | small | medium | hero.
    "slots": {
        "min": "small",
        "ideal": "medium",
        "max": "hero",
        "aspect": "4/3",
    },

    // User-editable options → rendered into the settings sheet.
    // type ∈ boolean | integer | number | string | enum | list | timerange | secret
    "settings": {
        "showFeelsLike": {
            "type": "boolean",
            "title": "Show ‘feels like’",
            "default": true,
        },
    },

    // Motion. min = the tier the card is still usable at.
    // features = per-effect minimum tier the client checks with ctx.tier.allows().
    "tier": { "min": "lite", "features": { "flip": "standard" } },

    // ctx.fetch() host allow-list — a fetch to any other host is refused.
    "permissions": {
        "fetchHosts": ["api.open-meteo.com", "geocoding-api.open-meteo.com"],
    },

    "entry": "weather", // client component id — informational for the server
}
```

Everything except `id`, `name` has a default. Durations are always strings
(`"15m"`, `"90s"`, `"1h"`, `"2d"`), never raw numbers.

## Disabling a built-in

`disabled_cards = ["commute", "phrase"]` in `config.toml`, or `PINEDA_DISABLED_CARDS`.

- `"commute"`: disabled by default to avoid running up billing against the Google Directions API (`maps.googleapis.com`).
- `"phrase"`: retired by default in favor of live traffic cameras (`"traffic"`), which automatically takes its slot in saved stacks.

Both can be re-enabled deliberately by overriding `disabled_cards` in `config.toml` (or setting the `PINEDA_DISABLED_CARDS` environment variable).

## Card Slots & Hero Mode

Cards declare slot sizing hints (`slots.min`, `slots.ideal`, `slots.max`). When displayed in the hero position (`slot="hero"`) — either pinned statically or promoted dynamically via **Dynamic Shuffle** — cards render a rich, glanceable Hero layout:

- **`indoor_climate`**: Large thermostat hero displaying target temperature setpoint, HVAC mode/status pill, and outdoor/indoor humidity telemetry.
- **`moon`**: Celestial hero layout with large glowing moon glyph, illuminated phase percentage, and waxing/waning status.
- **`timer`**: Prominent countdown digits with high-contrast active state and multi-timer secondary list.
- **`forecast`**: 7-day extended forecast grid with weather glyphs, precipitation chances, and temperature bars.
- **`calendar`**: Prominent agenda layout highlighting current/upcoming event with week overview columns.
- **`on_this_day`**: Full-resolution historical photo display with memory badge and vignette details.
- **`traffic`**: Multi-camera split view and high-definition traffic camera feed with location badges.
- **`phrase`**: Large display typography with phonetic pronunciation guide and language origin chip.
