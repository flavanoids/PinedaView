# Writing a card

A card is a folder. Scaffold one:

```bash
scripts/new-card.sh sunrise "Sunrise"
```

```
cards/sunrise/
  card.json      manifest — see docs/CARD_MANIFEST.md
  provider.py    optional — only if the card fetches its own data
  README.md
```

Point the server at your `cards/` dir (default `./cards`) and run:

```bash
pinedaview dev --location "Austin"      # watches cards/ and hot-reloads manifests
```

`GET /api/cards` now lists it with a `status` of `ready` or `blocked` plus the
reason. Blocked cards still appear — that's the picker's "needs a key" state.

## The provider (`provider.py`)

Only if the card fetches its own data. One `poll()` runs per ready card that
declares a provider, on the manifest's `refresh` cadence, and its return value
is published to every store in `provides`.

```python
# SPDX-License-Identifier: Apache-2.0
from pinedaview.providers.base import Provider, ProviderContext
from pinedaview.config import ProviderConfig


class SunriseProvider(Provider):
    key = "sunrise"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return 3600

    async def poll(self, ctx: ProviderContext) -> dict | None:
        lat = ctx.settings.location.latitude
        if lat is None:
            return None                                  # defer — retries soon
        data = await ctx.fetch_json(
            f"https://api.sunrise-sunset.org/json?lat={lat}&lng={ctx.settings.location.longitude}",
            allow_hosts=["api.sunrise-sunset.org"],        # must match permissions.fetchHosts
        )
        return {"sunrise": data["results"]["sunrise"]}
```

Point the manifest at it: `"provider": "sunrise.provider:SunriseProvider"`
(a dotted import — put `provider.py` on the Python path, e.g. install your card
as a package) or use a built-in key.

### What `ctx` gives a provider

| | |
|---|---|
| `ctx.settings` | the server config (`location`, `units`, …) |
| `ctx.store_value("weather")` | another card's latest published value, or `None` |
| `ctx.secret("google_maps")` | a key from Settings → Server; server-side only |
| `ctx.card_setting("sunrise", "key")` | this card's own setting |
| `ctx.fetch_json(url, allow_hosts=[…])` | cached HTTP; the host must be allow-listed |

Return `None` to leave the store unchanged and retry sooner (a dependency isn't
ready). Raise `ProviderError` for a transient failure — the store keeps its last
good value and goes `stale` after two misses.

## The view

A card with a bespoke look adds a Svelte component to `web/src/cards/` and
registers it in `web/src/cards/index.ts` (this needs a web rebuild). A card
without one renders through **Generic** — its name plus any store data — so it
still shows up with no rebuild. Fully-dynamic third-party views are a later
phase.

Client-side `ctx` today: `ctx.data(store)` via `view.data`, `ctx.format.*`
(unit-aware), `ctx.tier.allows("standard")` for `tier.features`.
