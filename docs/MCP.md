# PinedaView MCP — specification

Status (2026-10-15): **phases 1–3 built and live on the primary** (standby pending). Built:
§5.1 and §5.2 tools (`pinedaview/mcp_server.py`, plus `takeover_get`),
`BearerScopes` + audit, `CameraService` (`pinedaview/cameras.py`: the stream
follows the camera card, whoever puts it up), a camera covering a recipe hands
it back on expiry or `camera_stop`, and `pinedaview mcp-token`. Antigua's side:
`HttpMcpServer` + `ToolLog` (`mcp_client.py`), `PinedaClient` over MCP,
doorbell `show_on_motion`. Measured on loopback: 1–2.4 ms p50 per tool call,
the same as REST, because audit and tool-log writes are batched off the
request path.
Not built yet:
- MRTR: `display_reboot` takes `confirm: true` for now.
- Faces (§5.3, phase 4).
- LLM tool calling (phase 5).
- Events (phase 6).
- A dedicated HA user for pinedaview.

Protocol target: **MCP 2026-07-28** (stateless core). Server SDK: `mcp` **2.x** (Python).

pinedaview exposes its display, camera and face-ID functions as an MCP
server. Antigua stops calling pinedaview's REST API and becomes an MCP client
of it. The kiosk and the phone menu keep using REST; MCP is a second front
door onto the same internal services, not a replacement for the web API.

Goals, in priority order:

1. **Speed.** A voice turn can't feel the change. Display tools stay within a
   few milliseconds of today's REST calls (1–9 ms on loopback, measured
   2026-10-15).
2. **Security.** Every MCP caller is authenticated and scoped, even though
   the REST API stays open by choice. MCP is the surface that can reboot the
   kiosk, open a camera and name a face, so it gets locked down from day one.
3. **Efficiency.** No handshakes, no sessions, no per-call process spawn,
   no tool list re-sent on every turn.
4. **Portability.** The LLM, the MCP server and the display can each move to
   another host (a GPU box, the standby) by changing a URL.
5. **History.** Every tool call is recorded at both ends and can be tied to
   the voice turn that caused it.

---

## 1. Topology

```
 mic / satellites ──► Antigua (primary-server)                    pinedaview (primary-server :8090)
                      ├─ regex intents ─┐                   ├─ REST /api/*   ◄── kiosk, phone menu
                      ├─ Qwen tool-call ┤── MCP over HTTP ─►├─ MCP  /mcp     ◄── Antigua (token)
                      └─ tool-call log ─┘   (stateless)     ├─ services: takeover, themes, devices,
                                                            │  now-showing, timers, cameras, faces
                                                            ├─ HA (stream start/stop) ─► Eufy
                                                            └─ go2rtc :1984 (frames + video)
                      fallback ─────────── MCP over HTTP ──► pinedaview standby (standby-server :8090)
```

- **One process.** The MCP server is mounted inside pinedaview's FastAPI app.
  MCP tools call the same service objects the REST routes call
  (`runtime.takeover`, `runtime.registry`, …), so the two front doors can't
  drift apart and a tool call costs no extra network hop.
- **Antigua's client has an ordered list of endpoints:** primary, then
  standby. The core is now stateless, so any instance can answer any call and
  failing over needs no session to rebuild.
- **The GPU box later:** face ID can move to a separate `faces` MCP server
  (§6.4) without changing the tool names Antigua calls.

## 2. Protocol profile (MCP 2026-07-28)

What we use, what we don't, and why.

| Feature | Use | Notes |
|---|---|---|
| Streamable HTTP, `POST /mcp` | **Yes** | The only transport. No stdio: the server is a long-running web service, and stdio would mean spawning a process per client. |
| Stateless requests (no `initialize`, no `Mcp-Session-Id`) | **Yes** | Each call is a single POST. `_meta` carries `io.modelcontextprotocol/protocolVersion`, `…/clientCapabilities` and `…/clientInfo`. |
| `server/discover` | **Yes** | The client calls it once at startup and again after any `UnsupportedProtocolVersionError` (-32022). It's also the health probe. |
| `Mcp-Method` / `Mcp-Name` headers | **Yes (required)** | The auth middleware reads them to check scopes **without parsing the JSON body**. |
| JSON responses (`application/json`) | **Default** | Every display tool replies in one JSON body: no SSE framing, no stream to hold open. |
| SSE response stream | **Only where needed** | `camera_show` and `faces_identify` stream `notifications/progress` ("stream up", "2 faces found"). |
| `CacheableResult` (`ttlMs`, `cacheScope`) | **Yes** | `tools/list` returns `ttlMs: 3600000, cacheScope: "private"`, in a fixed order. Antigua fetches the list once an hour, not per turn, and the stable order keeps Ollama's prompt prefix cache warm. |
| `structuredContent` + `outputSchema` | **Yes, on every tool** | Antigua reads typed results. The text content is a short summary for an LLM. |
| Tool annotations | **Yes** | `read_only_hint`, `destructive_hint`, `idempotent_hint`, `open_world_hint`. These are hints, not security: scopes (§4) do the enforcing. |
| Server-minted handles (SEP-2567) | **Yes** | `sighting_id` from `faces_identify` and `view_id` from `camera_show` are passed back as plain arguments. Cross-call state never relies on the transport. |
| Multi Round-Trip Requests (`input_required`) | **Yes, narrowly** | `display_reboot` returns `input_required` with a confirm request unless `confirm: true` was sent. `faces_enroll` does the same when the name is new. Antigua turns these into a spoken "are you sure?". |
| `subscriptions/listen` | **Phase 6** | Push events from the server (a takeover dismissed on screen, a face seen). Until then, the existing MQTT topic `antigua/alarm_stop` stays as it is. |
| Tasks extension (`io.modelcontextprotocol/tasks`) | **Later** | Only for jobs measured in minutes, such as bulk enrollment from the event archive. No voice-path tool runs long enough to need it. |
| OpenTelemetry `traceparent` in `_meta` | **Yes** | One trace id per voice turn joins Antigua's log to pinedaview's (§7). |
| Roots, Sampling, Logging | **No** | All three are deprecated in 2026-07-28. Logging goes to stderr/journald, per-request log level goes in `_meta` only if ever needed, and the server never asks the client's LLM for anything. |
| Legacy HTTP+SSE transport | **No** | Deprecated. |
| Resources | **Minimal** | `pineda://status`, cacheable for 2 s, for clients that would rather read than call. Prompts: none. |

**Version policy.** The server supports `2026-07-28` and, through SDK 2.x,
earlier revisions as well. Antigua pins `2026-07-28`. A future spec revision
gets adopted by bumping the server SDK first (it keeps serving the old
version), then the client.

## 3. Transport and performance

**Mount**, on pinedaview's existing uvicorn listener (:8090):

```python
mcp = MCPServer("pineda-display", ...)                 # mcp 2.x
app.mount("/mcp", BearerScopes(mcp.streamable_http_app(streamable_http_path="/", ...)))
# lifespan: async with mcp.session_manager.run(): ...   (the host app has to start it)
```

`transport_security` allows only the hosts that should reach it:
`127.0.0.1`, `localhost`, `192.0.2.171` (primary-server), `192.0.2.16`
(standby-server) and the wg0 addresses. Anything else gets a 421, which also blocks
DNS rebinding from a browser. CORS is off for `/mcp`, since no browser
client should ever call it.

**Client: hand-rolled and synchronous.** This matches `mcp_client.py`.
Antigua is threaded, not asyncio, and the stateless wire format is small:
one POST, headers plus a JSON-RPC body.

- One `httpx.Client` per endpoint with HTTP/1.1 keep-alive, so there's no
  TCP connect per call. Timeouts: connect 0.3 s, read set per tool (§5).
- Each request sends `Authorization`, `Mcp-Method`, `Mcp-Name`,
  `MCP-Protocol-Version`, `Content-Type`, and
  `Accept: application/json, text/event-stream`.
- `_meta` carries the protocol version, clientInfo `{name: "antigua",
  version}`, the turn's `traceparent`, and `io.antigua/speaker` when the
  speaker is known.
- Replies are read as JSON, or as SSE when the server chose to stream.
  Progress events go to a callback, for example to say "identifying…".
- **Retry rules:** a connection error, 5xx, or broken stream on an
  **idempotent** tool is retried once on the same endpoint and then tried on
  the standby. Non-idempotent tools (`display_reboot`, `display_restart`,
  `faces_enroll`) are never retried automatically.
- `server/discover` runs at startup and every 10 min in the background.
  It's both the health check and the protocol-version check.
- `mcp_client.py` gains an `HttpMcpServer` beside `McpServer` (stdio). Roku
  and Govee stay on stdio with the old handshake: their servers pin
  `mcp==1.2.0` and aren't ours to rewrite.

**Latency budgets (p50 / p95, primary-server loopback):**

| Tool class | p50 | p95 | Today (REST) |
|---|---|---|---|
| Read-only display (`display_status`, `themes_list`, `now_showing`) | ≤ 8 ms | ≤ 25 ms | 1–9 ms |
| Display writes (`theme_set`, `takeover_*`, `clock_mode`, `timers_sync`) | ≤ 8 ms | ≤ 25 ms | 1–6 ms |
| `camera_show` (until the card is up) | ≤ 300 ms | ≤ 800 ms | n/a |
| `camera_show` (until the first frame) | ≤ 1.5 s | ≤ 3 s | about 1 s |
| `faces_identify` (stream up, 3 frames, CPU) | ≤ 2.5 s | ≤ 4 s | n/a |

A CI benchmark (`core/tests/test_mcp_perf.py`) times 200 calls of each
display tool against an in-process server and fails above the p95 budget.

## 4. Security

The REST API stays open on the LAN (the earlier decision: the kiosk sends no
token). **`/mcp` is not open**, because it's the surface built for machines,
and one of those machines is an LLM.

### 4.1 Authentication: static bearer tokens

- Tokens are 32 random bytes, base64url-encoded. pinedaview's config stores
  only a **SHA-256 hash** of each, under `[mcp.clients.<name>]`, so a leaked
  `config.toml` gives nothing away.
- Antigua keeps its token in `/etc/antigua/pineda-mcp.env` (root, 600),
  alongside the HA token, and never in git or server.yaml.
- A small ASGI middleware (`BearerScopes`) wraps the mount. It hashes the
  presented token, compares it in constant time, maps it to a client name and
  scopes, and checks the `Mcp-Name` header against those scopes **before the
  body is parsed**. A wrong or missing token gets a 401. A tool outside the
  token's scopes gets a 403.
  - Why not the SDK's `TokenVerifier`: in SDK 2.x it requires `AuthSettings`
    with an OAuth `issuer_url` and advertises an authorization server. We
    have no OAuth issuer on the LAN. If one ever appears (a host outside the
    house), switch to `TokenVerifier` + `AuthSettings` and Client ID Metadata
    Documents, which is the 2026-07-28 path. Tool code doesn't change either
    way, because tools only read `client` and `scopes` from the request
    context.
- The middleware also checks that the `Mcp-Name` header matches
  `params.name` in the body once the body is parsed. A mismatch returns
  `HeaderMismatchError` (-32020), so a header can't be spoofed to pass the
  scope check while the body calls something else.
- Rotation: `pinedaview mcp-token new <client>` prints a new token once and
  writes its hash. Old hashes can stay listed until the client has switched.

### 4.2 Scopes

| Scope | Tools |
|---|---|
| `display:read` | `display_status`, `themes_list`, `now_showing` |
| `display:write` | `theme_set`, `clock_mode`, `takeover_show`, `takeover_update`, `takeover_clear`, `timers_sync` |
| `system` | `display_restart`, `display_reboot` |
| `camera:view` | `cameras_list`, `camera_show`, `camera_caption`, `camera_stop` |
| `faces:identify` | `faces_identify`, `faces_list` |
| `faces:manage` | `faces_enroll`, `faces_forget` |

Clients:

- **antigua** (primary and fallback share one token): every scope.
- **Read-only token** (for a dashboard or a test harness): `display:read`
  only.

### 4.3 What the LLM sees

Scopes limit what Antigua's *token* can do. What the *model* can pick is
narrower still:

- Each tool carries `_meta["io.pineda/llm"]: true|false`. Antigua passes the
  model only tools marked true.
- Marked false, and only ever reached through the regex path: `timers_sync`,
  `takeover_update`, `display_reboot`, `faces_enroll`, `faces_forget`.
- Destructive tools need an MRTR confirmation (§2) whichever path reaches
  them.
- No tool unlocks a door, and no tool takes a free-form URL or shell string.
  Camera names, theme names and people are all checked against fixed lists
  on the server.

### 4.4 Network

- Done (2026-10-16): `pinedaview-guard` allows `:8090` only from loopback,
  wg0 and the LAN, and blocks tunnels from reaching it (see
  [OPERATIONS.md](OPERATIONS.md#keeping-it-on-the-lan)). `/mcp` itself is
  protected by the token, not the firewall.
- **Home Assistant:** pinedaview gets its own HA user (`pineda-display`,
  non-admin) and its own long-lived token in `/etc/pinedaview/ha.env`
  (pineda user, 600). It does not reuse Antigua's root-only token. HA has no
  per-service token scopes, so the code path is the real limit: pinedaview
  calls only `eufy_security.start_p2p_livestream` and
  `eufy_security.stop_p2p_livestream` and reads camera states.

### 4.5 Face data (biometrics)

- **Data stays on the box.** Embeddings and face crops are stored in
  `state_dir/faces.db` and `state_dir/faces/` (mode 600, pineda user). No
  tool returns an embedding.
- **Unknown faces expire.** Unknown-face sightings are deleted after **14
  days**. Enrolled people keep up to 20 reference crops each.
- **The standby has no copy unless you opt in.** `sync-standby.sh` leaves
  `faces.db` out unless `[faces] sync_standby = true`.
- **Only the regex path can enroll or forget.** `faces_enroll` and
  `faces_forget` need `faces:manage` and are hidden from the LLM.

## 5. Tools

Names are `snake_case` (`[a-z0-9_]`). This is valid for MCP, and also for
OpenAI- and Ollama-style function names, so the same list can go straight to
any model backend. `tools/list` returns them in the order below.

Each entry gives the tool's scope, its annotations (R = read-only,
D = destructive, I = idempotent), whether the LLM sees it, and its client
timeout.

### 5.1 Display

| Tool | Args | Returns (`structuredContent`) | Scope | Ann. | LLM | Timeout |
|---|---|---|---|---|---|---|
| `display_status` | — | `{theme, theme_label, clock_mode, takeover: {kind, title?, camera?, expires_at}?, screens: n, now_showing: {quote?, photo?, phrase?}}` | display:read | R | ✓ | 1 s |
| `themes_list` | — | `[{name, label}]` (night twins left out) | display:read | R | ✓ | 1 s |
| `now_showing` | `item?: "quote"\|"photo"\|"phrase"` | the item, as `/api/now-showing` returns it | display:read | R | ✓ | 1 s |
| `theme_set` | `name: str \| "random"` | `{theme, label, changed: bool}` | display:write | I | ✓ | 1 s |
| `clock_mode` | `on: bool` | `{changed: int}` (screens switched) | display:write | I | ✓ | 1 s |
| `takeover_show` | `card: RecipeTakeover \| AlarmTakeover \| ImageSearchTakeover, seconds` | `Takeover` | display:write | — | ✓ | 1 s |
| `takeover_update` | `TakeoverUpdate` (only the fields sent) | `Takeover \| null` | display:write | I | ✗ | 1 s |
| `takeover_clear` | — | `{was: kind \| null}` | display:write | I | ✓ | 1 s |
| `timers_sync` | `source, timers[]` | `{count}` | display:write | I | ✗ | 1 s |
| `display_restart` | — | `{accepted}` | system | D | ✓ (confirm) | 3 s |
| `display_reboot` | `confirm?: bool` | `{accepted}` or `input_required` | system | D | ✗ | 3 s |

`theme_set` does the name matching on the server: it moves
`match_theme`/`base_themes` from Antigua into pinedaview. Antigua and the
LLM both send what was said ("cocoa"), and the server resolves it. An unknown
name returns `isError` with the list of valid themes, so the model can try
again by itself.

`display_status` exists to save round trips. It answers "what's on the
screen?" in one call, and Antigua can put it in the LLM's context instead of
calling three tools.

### 5.2 Cameras (moved from Antigua's `security.py`)

| Tool | Args | Returns | Scope | Ann. | LLM | Timeout |
|---|---|---|---|---|---|---|
| `cameras_list` | — | `[{name, title, battery, charging, live}]` | camera:view | R | ✓ | 2 s |
| `camera_show` | `camera: enum, seconds?: 10–600 = 60, identify?: bool = false` | `{view_id, camera, expires_at, sighting_id?}` | camera:view | I | ✓ | 5 s |
| `camera_caption` | `view_id, text` | `{ok}` | camera:view | I | ✗ | 1 s |
| `camera_stop` | `view_id?` | `{stopped: bool}` | camera:view | I | ✓ | 2 s |

`camera` is an `enum` in the input schema (`front_door`, `garage`), built
from `[cameras.streams]`, so the model can't make up a camera.

What pinedaview does on `camera_show`:

1. Starts the P2P livestream through HA (`start_p2p_livestream`).
2. Puts up the `kind: "camera"` takeover.
3. Sends progress `"stream"` once go2rtc has a producer.
4. If `identify` was set, runs `faces_identify` in the background and
   captions the card with the result.
5. Returns the `view_id`.

The stream stops on its own the moment the camera card is no longer up
(dismissed, replaced, timed out, or `camera_stop`). pinedaview owns the
takeover, so it sees this directly. That replaces Antigua's
`_watch_live` polling loop, and it means a battery camera can't be left
streaming because Antigua crashed.

The doorbell-ring auto-show stays in Antigua's poller (it's an event, not a
request). It now calls `camera_show(front_door, identify=true)`.

### 5.3 Faces

| Tool | Args | Returns | Scope | Ann. | LLM | Timeout |
|---|---|---|---|---|---|---|
| `faces_identify` | `camera: enum, frames?: 1–8 = 3` | `{sighting_id, faces: [{box, name?, score, known: bool}], at}` | faces:identify | R* | ✓ | 6 s |
| `faces_list` | — | `[{name, refs, last_seen?}]` | faces:identify | R | ✓ | 1 s |
| `faces_enroll` | `sighting_id, face: int, name` | `{name, refs}` or `input_required` (new name) | faces:manage | — | ✗ | 3 s |
| `faces_forget` | `name` | `{removed: int}` | faces:manage | D | ✗ | 1 s |

\* Read-only towards the house, though it does record the sighting.

`faces_identify` works like this:

1. If the camera isn't live, it starts the stream without a takeover, and
   stops it afterwards unless a card is up.
2. It pulls `frames` JPEGs, 300 ms apart, from go2rtc
   `/api/frame.jpeg?src=<serial>`.
3. It runs detection and embedding (InsightFace `buffalo_s` on CPU through
   onnxruntime: about 150–300 ms per 1600×1200 frame on primary-server's 16 cores,
   to be measured in phase 4).
4. It matches each face against enrolled people by cosine similarity, with
   the same rule as speaker ID: score ≥ floor and ahead of the runner-up by
   a margin (both in `[faces]` config).
5. Progress events: `"frame 1/3"`, `"faces: 2"`.

Unknown faces are kept under the sighting (14-day expiry). That's what makes
the voice follow-up work:

> "Who's at the door?" → `faces_identify` → "I don't recognise them."
> "That's Sam." → `faces_enroll(sighting_id, 0, "Sam")` → `input_required`
> ("Add Sam as a new person?") → "yes" → enrolled.

### 5.4 Errors

- **Tool-level failures** (unknown theme, camera offline, no screen, HA
  down) return `isError: true` with a one-line `text` the LLM can read, plus
  `structuredContent: {error: code, …}` for Antigua's spoken replies. Codes:
  `unknown_theme`, `no_screen`, `camera_unavailable`, `ha_unreachable`,
  `stream_timeout`, `no_takeover`, `unknown_sighting`, `unknown_person`.
- **Protocol errors** use JSON-RPC codes. MCP's own range is
  -32020…-32099, so pineda-specific codes stay inside -32000…-32019.

## 6. Antigua side

### 6.1 `PinedaClient` becomes an MCP adapter

Methods and signatures stay the same (`set_theme`, `show_takeover`,
`hold_clock`, …). Inside, each one calls the matching tool through
`HttpMcpServer`. `RecipeDisplay`, `TimerMirror` and the pipeline handlers
don't change. This is what makes phase 2 a swap that can't be heard.
`PinedaError` is raised from `isError` results and transport failures, the
same as today.

`TimerMirror`'s second client, the standby, becomes the standby endpoint of
the same `HttpMcpServer`, called with `timers_sync` directly.

### 6.2 Routing: regex first, model second

```
transcript ─► regex intents (unchanged) ──match──► fixed MCP call(s) ──► spoken reply
                       │ no match
                       ▼
             looks display/camera-ish? (cheap keyword gate)
                       │ yes
                       ▼
             Ollama /api/chat with tools = MCP tools where io.pineda/llm = true
             (≤ 1 tool round; the result goes back for one spoken sentence)
```

- **The regex path stays the fast path:** no LLM, about 10 ms of tool time.
- The **LLM path** is new. Requests no regex matched, like "put the garage on
  the screen for five minutes" or "who's outside?", reach the 4B model with
  about 12 tool schemas (cached, fixed order, so the prompt prefix is
  reusable).
- Bound: one tool-call round, then the answer. Measure the added latency in
  phase 5 before turning it on: it's expected to be 0.5–1 s, and it only
  hits requests that currently fail.
- The keyword gate (display, screen, camera, door, garage, theme, clock,
  who's…) keeps general chat from ever seeing the tool list.

### 6.3 Tool-call history

`data/tool_calls.db` (SQLite, WAL), one row per call:

```
id, ts, turn_id, trace_id, path ("regex"|"llm"|"poller"|"timer"),
speaker, transcript, server, endpoint, tool, args_json, ok, error_code,
result_json (truncated 4 KB), ms
```

How it's used:

- **Follow-ups:** the last 3 calls from the past 10 minutes go into the LLM
  context and the regex follow-up resolvers. That covers "take it down",
  "make it longer", "who was that?" (`sighting_id`) and "that's Sam".
- **Debugging:** `GET /tool_calls?since=` on Antigua's API, newest first.
- **Retention:** 30 days, pruned on startup.

On pinedaview's side, `state_dir/mcp_audit.db` holds `ts, client, tool,
args_hash, ok, ms, trace_id`. It stores arguments **hashed, not in full**,
since face names and transcripts already live with Antigua. Joining on
`trace_id` matches every server-side call to the voice turn that caused it.

### 6.4 Moving parts around later

| Future change | What changes |
|---|---|
| A GPU box runs the LLM | Antigua's `llm.host` only. MCP is unaffected. |
| Face ID moves to the GPU box | Split `faces_*` into a `faces` MCP server there. Antigua's tool router maps the tool name to a server. pinedaview's `camera_show(identify=true)` then calls the faces server itself. Tool names don't change. |
| MCP on another host | Change the URL in server.yaml. Add the new host to `transport_security`. Token unchanged. |
| A second client (Hermes, a phone app) | Mint a token with narrower scopes. |
| Outside-the-house access | Switch to OAuth: SDK `TokenVerifier` + `AuthSettings`, with Client ID Metadata Documents. Tool code unchanged. |
| Push events | `subscriptions/listen` with `resourceSubscriptions` on `pineda://events/takeover` and `pineda://events/faces`. This retires MQTT `antigua/alarm_stop`. |
| Long jobs | The tasks extension, for `faces_enroll_bulk` (enrollment from the event archive). |

## 7. Observability

- **Trace ids:** Antigua creates a W3C `traceparent` per turn and sends it in
  `_meta.traceparent`. pinedaview logs it on every MCP line and in the
  audit table.
- **Health:** `server/discover` (cheap, no scope needed beyond a valid
  token). Antigua's `/status` shows each endpoint's last discover time,
  protocol version and p50 tool latency.
- **Logs:** pinedaview writes `mcp tool=<n> client=<c> ms=<t> ok=<b>
  trace=<id>`, one line per call, at INFO.

## 8. Phases

Each phase can be deployed on its own and rolled back by config.

| # | Work | Done when |
|---|---|---|
| 1 | pinedaview: add `mcp>=2.0.1,<3` to core deps; mount `/mcp`; `BearerScopes` middleware; §5.1 tools wrapping existing services; move `match_theme` server-side; audit table; tests (schemas, scopes, header mismatch, perf budget). Deploy to primary + standby. | `tools/list` and every §5.1 tool pass against both hosts, and a call with no token gets a 401. |
| 2 | Antigua: `HttpMcpServer` (stateless client, keep-alive, failover, traceparent); `PinedaClient` → MCP; `tool_calls.db`; token file. Delete the REST calls from `PinedaClient`. | A full voice regression with no audible change; p50 latency within budget; every call in the log. |
| 3 | Cameras move: §5.2 in pinedaview (HA token and user, stream lifecycle tied to the takeover); Antigua's `security.py` drops `show_camera`/`_watch_live` and calls MCP; the doorbell ring uses `camera_show`. | "Show the garage" works, and the stream stops within 2 s of the card going down (checked in the go2rtc producers list). |
| 4 | Faces: InsightFace in a `faces` extra; §5.3 tools; enrollment by voice through MRTR; the poller's person event → `faces_identify` → announcement ("Sam's at the front door"). | Known faces named at the door; unknown ones offered for enrollment; sightings expire after 14 days. |
| 5 | LLM tool calling: keyword gate + Ollama tools + one round; measure accuracy on a fixed set of 30 phrasings. | ≥ 90% correct tool choice; no extra latency on regex-handled requests. |
| 6 | `subscriptions/listen` events; retire MQTT `alarm_stop`. | Dismissing an alarm on screen stops Antigua's ringing through MCP alone. |

## 9. Open questions

1. **InsightFace licence.** The `buffalo_*` model weights are for
   non-commercial use only. That's fine for a home, but it rules out shipping
   them in pinedaview's public packaging: the model downloads on first use
   instead of being bundled.
2. **Battery cost of `identify` on every person event at the garage**
   (solar). Probably fine, but log the stream-seconds per day in phase 4
   before deciding.
3. **Standby faces.** Should failover recognise people (`sync_standby`),
   or is "someone's at the door" good enough while the primary is down?

## References

- MCP 2026-07-28 changelog: https://modelcontextprotocol.io/specification/2026-07-28/changelog
- 2026-07-28 release post: https://blog.modelcontextprotocol.io/posts/2026-07-28/
- Python SDK v2 docs (ASGI mounting, authorization, tools): https://py.sdk.modelcontextprotocol.io/
- Related: docs/API.md (REST), docs/OPERATIONS.md (deploy, standby), Antigua `server/antigua_core/mcp_client.py`, `security.py`, `pineda.py`.
