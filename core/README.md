# pineda-web (core)

The headless server: config, data providers, state machine, view model, HTTP +
SSE API. Serves the built `web/` client as static files — one process, no nginx.

```bash
uv sync

# run the API server (data engine + HTTP + SSE, one process)
uv run pineda-web serve --location "Chicago"

curl -s localhost:8090/api/health
DID=$(curl -sXPOST localhost:8090/api/devices/pair -d '{"name":"Desk"}' \
      -H 'content-type: application/json' | python -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s localhost:8090/api/view/$DID | python -m json.tool
curl -sN localhost:8090/api/stream/$DID          # live view model

# config: copy config.example.toml → config.toml, or use PINEDA_* env vars
uv run pineda-web serve --config config.toml

# the gate
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

Stores behind the view model: `weather` · `airQuality` · `alerts` · `moon` ·
`dailyContent` · `commute` · `radar` · `indoorClimate` · `calendar` · `onThisDay` ·
`trafficCams` · `nowPlaying` (via MQTT) · `photos` · `timers` · `sun`. Each holds
`{value, updatedAt, stale}`; a provider keeps its last good value and the store
flags it stale after two missed refreshes. Outside systems can also publish
arbitrary store payloads via `POST /api/ingest/{store}`.

The API is the v0 wire contract — schema in
[`../packages/protocol/openapi.json`](../packages/protocol/openapi.json),
regenerate with `uv run --project . python ../scripts/export-openapi.py`.
