# SPDX-License-Identifier: Apache-2.0
"""The display as an MCP server, at /mcp (spec: docs/MCP.md).

MCP 2026-07-28, stateless Streamable HTTP: each call is one POST, no
handshake, no session. The tools wrap the same services the REST routes use,
so the two front doors can't drift apart; the kiosk and the phone menu keep
using REST.

Unlike the REST API, nothing here is open: every request carries a client's
bearer token, which is checked (hashed, constant-time) along with its scopes
against the ``Mcp-Name`` header before the body is parsed — the SDK then
refuses a body whose tool name doesn't match that header (-32020). Every call
is logged, with the caller's trace id, to ``mcp_audit.db``."""

import asyncio
import contextvars
import functools
import hashlib
import hmac
import json
import logging
import queue
import random
import re
import secrets
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.caching import CacheHint
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

from pinedaview.cameras import CameraError, CameraService
from pinedaview.config import McpConfig
from pinedaview.control import ControlError, restart_display, restart_system
from pinedaview.runtime import Runtime
from pinedaview.takeover import (
    AlarmTakeover,
    CameraTakeover,
    ImageSearchTakeover,
    RecipeTakeover,
    Takeover,
    TakeoverUpdate,
)
from pinedaview.themes import Theme, all_themes, find_theme
from pinedaview.timers import SyncedTimer

logger = logging.getLogger(__name__)

SCOPES: dict[str, str] = {
    "display_status": "display:read",
    "themes_list": "display:read",
    "now_showing": "display:read",
    "takeover_get": "display:read",
    "theme_set": "display:write",
    "clock_mode": "display:write",
    "takeover_show": "display:write",
    "takeover_update": "display:write",
    "takeover_clear": "display:write",
    "timers_sync": "display:write",
    "display_restart": "system",
    "display_reboot": "system",
    "cameras_list": "camera:view",
    "camera_show": "camera:view",
    "camera_caption": "camera:view",
    "camera_stop": "camera:view",
}
"""Tool → the scope a token needs to call it. A tool missing here can't be
called by anyone."""

_client: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_client", default="?")
_TOOLS_TTL = CacheHint(ttl_ms=3_600_000, scope="private")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """(token, its hash): the token goes to the client, the hash to config."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


# ── auth: bearer token + scopes, before the body is read ─────────────────────


class BearerScopes:
    """ASGI wrapper for the MCP app. Discovery and listing need only a valid
    token; ``tools/call`` needs the scope its ``Mcp-Name`` maps to."""

    def __init__(self, app: ASGIApp, cfg: McpConfig) -> None:
        self._app = app
        self._clients = {
            c.token_sha256.lower(): (name, set(c.scopes)) for name, c in cfg.clients.items()
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        auth = headers.get("authorization", "")
        client = self._client_for(auth[7:].strip() if auth[:7].lower() == "bearer " else "")
        if client is None:
            await _deny(send, 401, "a valid MCP client token is required")
            return
        name, scopes = client
        if headers.get("mcp-method") == "tools/call":
            need = SCOPES.get(headers.get("mcp-name", ""))
            if need is None or need not in scopes:
                await _deny(send, 403, "this token may not call that tool")
                return
        token = _client.set(name)
        try:
            await self._app(scope, receive, send)
        finally:
            _client.reset(token)

    def _client_for(self, token: str) -> tuple[str, set[str]] | None:
        if not token:
            return None
        presented = token_hash(token)
        found = None
        for digest, client in self._clients.items():
            # Every entry compared, constant-time: no early exit to time.
            if hmac.compare_digest(presented, digest):
                found = client
        return found


async def _deny(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    if status == 401:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


# ── the audit log ────────────────────────────────────────────────────────────


class Audit:
    """One row per request: who, what, how long, ok, and the caller's trace
    id (W3C traceparent in _meta) to join with the client's own log.
    Arguments are kept as a hash only — the caller keeps the details.
    Rows are written by a background thread, in batches: a commit costs
    ~8 ms of fsync, ten times the call itself, so it stays off the reply."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._rows: queue.SimpleQueue[tuple[Any, ...]] = queue.SimpleQueue()
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS calls (ts REAL, client TEXT, method TEXT, tool TEXT,"
                " args_hash TEXT, ok INTEGER, ms REAL, trace TEXT)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS calls_ts ON calls (ts)")
            db.execute("DELETE FROM calls WHERE ts < ?", (time.time() - 30 * 86400,))
        threading.Thread(target=self._write, daemon=True, name="mcp-audit").start()

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=2)

    def _write(self) -> None:
        while True:
            rows = [self._rows.get()]
            while not self._rows.empty() and len(rows) < 200:
                rows.append(self._rows.get_nowait())
            try:
                with self._db() as db:
                    db.executemany("INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
            except sqlite3.Error as exc:
                logger.warning("mcp audit: %s", exc)

    def flush(self, timeout: float = 2.0) -> None:
        """Wait for queued rows to land (tests)."""
        end = time.monotonic() + timeout
        while not self._rows.empty() and time.monotonic() < end:
            time.sleep(0.01)
        time.sleep(0.05)

    async def __call__(self, ctx: Any, call_next: Callable[[Any], Awaitable[Any]]) -> Any:
        if ctx.request_id is None:
            return await call_next(ctx)
        params = dict(ctx.params or {})
        meta = params.get("_meta") or {}
        tool = params.get("name") if ctx.method == "tools/call" else None
        args = params.get("arguments")
        start = time.perf_counter()
        ok = False
        try:
            result = await call_next(ctx)
            ok = not getattr(result, "is_error", False)
            return result
        finally:
            ms = (time.perf_counter() - start) * 1000
            trace = str(meta.get("traceparent", ""))[:64]
            client = _client.get()
            if tool:
                logger.info(
                    "mcp tool=%s client=%s ms=%.1f ok=%s trace=%s", tool, client, ms, ok, trace
                )
            self._rows.put(
                (
                    time.time(),
                    client,
                    ctx.method,
                    tool,
                    hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
                    if args
                    else None,
                    int(ok),
                    round(ms, 2),
                    trace,
                )
            )


# ── tool failures the caller can act on ──────────────────────────────────────


class Fail(Exception):
    """A tool failed in a way the caller should hear about: ``code`` for
    code (Antigua's spoken replies), the message for a model to read."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


def _failing(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except Fail as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))],
                structured_content={"error": exc.code, "message": str(exc), **exc.extra},
                is_error=True,
            )

    return wrapper


# ── results ──────────────────────────────────────────────────────────────────


class ThemeChoice(BaseModel):
    name: str
    label: str


class ThemeResult(BaseModel):
    theme: str
    label: str
    changed: bool


class TakeoverSummary(BaseModel):
    kind: str
    title: str = ""
    camera: str | None = None
    shown_at: datetime
    expires_at: datetime


class DisplayStatus(BaseModel):
    theme: str
    theme_label: str
    clock_mode: bool
    """A screen is held on its Clock only view."""
    screens: int
    takeover: TakeoverSummary | None
    camera_streaming: str | None


class ClockResult(BaseModel):
    changed: int
    """Screens switched; 0 when they were all that way already."""


class Cleared(BaseModel):
    was: str | None
    """The kind of card that came down, or null when none was up."""


class Count(BaseModel):
    count: int


class Accepted(BaseModel):
    accepted: bool


class CameraInfo(BaseModel):
    name: str
    title: str
    battery: int | None
    showing: bool


class CameraShown(BaseModel):
    camera: str
    title: str
    pip_camera: str | None = None
    pip_title: str | None = None
    expires_at: datetime
    restores: bool
    """A card it covered (a recipe) comes back when it ends."""


class Ok(BaseModel):
    ok: bool


class Stopped(BaseModel):
    stopped: bool


# ── themes, matched the way they're said ─────────────────────────────────────


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z ]", " ", text.lower().replace("_", " ")).split())


def base_themes(themes: list[Theme]) -> list[Theme]:
    """Themes you'd pick by name — not the night twins a light theme
    switches to on its own at sundown."""
    twins = {t.night for t in themes if t.night}
    return [t for t in themes if t.name not in twins]


def match_theme(said: str, themes: list[Theme]) -> Theme | None:
    """The theme named in `said`: its label ("cocoa ember"), its id, or one
    word of its label no other theme shares ("cocoa")."""
    if (exact := find_theme(said)) is not None:
        return exact
    padded = f" {_norm(said)} "
    choices = base_themes(themes)
    words: dict[str, list[Theme]] = {}
    for t in choices:
        for w in _norm(t.label).split():
            words.setdefault(w, []).append(t)
    best, best_len = None, 0
    for t in choices:
        names = {_norm(t.label), _norm(t.name)}
        names |= {w for w in _norm(t.label).split() if len(w) >= 4 and len(words[w]) == 1}
        for n in names:
            if f" {n} " in padded and len(n) > best_len:
                best, best_len = t, len(n)
    return best


def _label(name: str) -> str:
    themes = all_themes()
    for t in themes:
        if t.name == name:
            return t.label
    for t in themes:
        if t.night == name:
            return f"{t.label}, night"
    return name.replace("_", " ")


# ── the server ───────────────────────────────────────────────────────────────


def build_mcp(  # noqa: C901 - one closure per tool
    runtime: Runtime,
    cameras: CameraService,
    now_showing: Callable[[Runtime, str | None], BaseModel],
    on_save: Callable[[str], None],
) -> MCPServer:
    """The tools, bound to this runtime. `now_showing` is api._now_showing;
    `on_save(reason)` tells the screens (and a standby's sync) something
    saved changed."""
    cfg = runtime.settings.mcp
    mcp = MCPServer(
        "pineda-display",
        title="PinedaDisplay",
        version="1.0.0",
        instructions="The kitchen display: its theme, its full-screen cards, and the home cameras.",
        cache_hints={"tools/list": _TOOLS_TTL},
        middleware=[audit := Audit(runtime.settings.state_dir / "mcp_audit.db")],
    )
    mcp.audit = audit  # type: ignore[attr-defined]
    read = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    write = ToolAnnotations(read_only_hint=False, idempotent_hint=True, open_world_hint=False)
    once = ToolAnnotations(read_only_hint=False, idempotent_hint=False, open_world_hint=False)
    harsh = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)
    llm = {"io.pineda/llm": True}
    no_llm = {"io.pineda/llm": False}

    async def profile_theme() -> str:
        prof = await runtime.devices.profile(cfg.profile)
        return (prof.theme if prof is not None else None) or runtime.settings.theme

    async def live_screens(within_s: float = 600) -> list[Any]:
        """The kiosk's screen records: the last one to load and any that
        loaded within `within_s` of it — the kiosk gets a new id each time
        its cache is cleared, and a clear can leave two. last_seen is when a
        screen last loaded (not a heartbeat), so it's compared to the
        newest, not to now. With ``[control] screen`` set it's just that
        one, so a tablet that loaded since is never the kiosk."""
        if (home := runtime.settings.control.screen) is not None:
            kiosk = await runtime.devices.device(home)
            return [kiosk] if kiosk is not None else []
        seen = [(d, d.last_seen) for d in await runtime.devices.devices() if d.last_seen]
        if not seen:
            return []
        newest = max(ts for _, ts in seen)
        return [d for d, ts in seen if (newest - ts).total_seconds() <= within_s]

    def summary(t: Takeover | None) -> TakeoverSummary | None:
        if t is None:
            return None
        card = t.card
        return TakeoverSummary(
            kind=card.kind,
            title=getattr(card, "title", "") or getattr(card, "label", ""),
            camera=card.camera if isinstance(card, CameraTakeover) else None,
            shown_at=t.shown_at,
            expires_at=t.expires_at,
        )

    # ── display ──

    @mcp.tool(title="What the display is doing", annotations=read, meta=llm)
    async def display_status() -> DisplayStatus:
        """The display right now: its theme, whether it's showing just the clock,
        and the full-screen card that's up (a recipe, an alarm, a camera), if any."""
        theme = await profile_theme()
        screens = await live_screens()
        return DisplayStatus(
            theme=theme,
            theme_label=_label(theme),
            clock_mode=any(d.night_clock and d.night_clock_hold for d in screens),
            screens=len(screens),
            takeover=summary(runtime.takeover.current()),
            camera_streaming=cameras.live,
        )

    @mcp.tool(title="List themes", annotations=read, meta=llm)
    async def themes_list() -> list[ThemeChoice]:
        """The display's themes, by name and label."""
        return [ThemeChoice(name=t.name, label=t.label) for t in base_themes(all_themes())]

    @mcp.tool(name="now_showing", title="What's on screen", annotations=read, meta=llm)
    async def now_showing_tool(device_id: str | None = None) -> dict[str, Any]:
        """The quote, photo and Spanish phrase the display is showing."""
        return now_showing(runtime, device_id).model_dump(mode="json")

    @mcp.tool(title="The full-screen card", annotations=read, meta=no_llm)
    async def takeover_get() -> Takeover | None:
        """The full-screen card that's up, in full, or null."""
        return runtime.takeover.current()

    @mcp.tool(title="Change the theme", annotations=write, meta=llm)
    @_failing
    async def theme_set(name: str) -> ThemeResult:
        """Switch the display's theme. `name` as said ("cocoa", "ocean blue") or
        "random" for any other theme."""
        themes = all_themes()
        current = await profile_theme()
        if name.strip().lower() in ("random", "any", "surprise me"):
            pool = [t for t in base_themes(themes) if t.name != current] or base_themes(themes)
            chosen: Theme | None = random.choice(pool)
        else:
            chosen = match_theme(name, themes)
        if chosen is None:
            labels = [t.label for t in base_themes(themes)]
            raise Fail(
                "unknown_theme",
                f"No theme called {name!r}. Themes: {', '.join(labels)}.",
                themes=labels,
            )
        if chosen.name != current:
            # The profile, not the server-wide theme: a profile's own theme wins.
            await runtime.devices.update_profile(cfg.profile, theme=chosen.name)
            on_save("profile")
        return ThemeResult(theme=chosen.name, label=chosen.label, changed=chosen.name != current)

    @mcp.tool(title="Clock only", annotations=write, meta=llm)
    @_failing
    async def clock_mode(on: bool) -> ClockResult:
        """Show only the clock on the display (on=true), or go back to the
        dashboard (on=false)."""
        screens = await live_screens()
        if not screens:
            raise Fail("no_screen", "No screen has loaded the display recently.")
        changed = 0
        for d in screens:
            if bool(d.night_clock and d.night_clock_hold) == on:
                continue
            body = (
                {"night_clock": True, "night_clock_hold": True}
                if on
                else {"night_clock_hold": False}
            )
            await runtime.devices.update_device(d.id, **body)
            changed += 1
        if changed:
            on_save("device")
        return ClockResult(changed=changed)

    @mcp.tool(title="Show a full-screen card", annotations=once, meta=llm)
    async def takeover_show(
        card: RecipeTakeover | AlarmTakeover | ImageSearchTakeover, seconds: float = 120
    ) -> Takeover:
        """Put a full-screen card (a recipe or how-to guide, an image search collage,
        or an alarm) on the display for `seconds` (1-3600); it replaces any card that's up."""
        return runtime.takeover.show(card, max(1.0, min(seconds, 3600.0)))

    @mcp.tool(title="Update the full-screen card", annotations=write, meta=no_llm)
    async def takeover_update(change: TakeoverUpdate) -> Takeover | None:
        """Change what's being read on the card that's up (only the fields sent);
        null when none is up. Never re-shows a dismissed card."""
        return runtime.takeover.update(change)

    @mcp.tool(title="Take the card down", annotations=write, meta=llm)
    async def takeover_clear() -> Cleared:
        """Take the full-screen card down ("stop the display")."""
        up = runtime.takeover.current()
        runtime.takeover.clear()
        if up is not None and isinstance(up.card, AlarmTakeover) and runtime.mqtt is not None:
            runtime.mqtt.publish("antigua/alarm_stop", {})
        return Cleared(was=up.card.kind if up else None)

    @mcp.tool(title="Mirror timers", annotations=write, meta=no_llm)
    @_failing
    async def timers_sync(source: str, timers: list[SyncedTimer]) -> Count:
        """Replace every timer `source` mirrors on the display with `timers`."""
        if not source.replace("-", "").replace("_", "").isalnum():
            raise Fail("bad_source", "source must be letters, digits, - or _")
        runtime.timers.sync(source, timers)
        return Count(count=len(timers))

    @mcp.tool(title="Restart the display", annotations=harsh, meta=llm)
    @_failing
    async def display_restart() -> Accepted:
        """Restart the kiosk's browser (the screen goes dark for ~20 s)."""
        try:
            await asyncio.to_thread(restart_display, runtime.settings.control)
        except ControlError as exc:
            raise Fail("control_failed", str(exc)) from exc
        return Accepted(accepted=True)

    @mcp.tool(title="Reboot the kiosk", annotations=harsh, meta=no_llm)
    @_failing
    async def display_reboot(confirm: bool = False) -> Accepted:
        """Reboot the kiosk computer. Needs confirm=true."""
        if not confirm:
            raise Fail("confirm_required", "Rebooting needs confirm=true.")
        try:
            await asyncio.to_thread(restart_system, runtime.settings.control)
        except ControlError as exc:
            raise Fail("control_failed", str(exc)) from exc
        return Accepted(accepted=True)

    # ── cameras ──

    if cameras.names:
        Camera = Literal[tuple(cameras.names)]  # type: ignore[valid-type]  # the schema's enum

        @mcp.tool(title="List cameras", annotations=read, meta=llm)
        async def cameras_list() -> list[CameraInfo]:
            """The home cameras, their batteries, and which one is on screen."""
            return [CameraInfo(**c) for c in cameras.status()]

        @mcp.tool(title="Show a camera", annotations=write, meta=llm)
        @_failing
        async def camera_show(
            camera: Camera,
            seconds: float = 60,
            pip: Camera | None = None,
        ) -> CameraShown:  # type: ignore[valid-type]
            """Show a camera's live video full screen for `seconds` (10-600), optionally
            with a second camera in Picture-in-Picture. Over a recipe, the recipe comes
            back when it ends. Showing the camera that's already up gives it more time."""
            try:
                t = cameras.show(camera, max(10.0, min(seconds, 600.0)), pip=pip)
            except CameraError as exc:
                raise Fail("unknown_camera", str(exc)) from exc
            card = t.card
            assert isinstance(card, CameraTakeover)
            return CameraShown(
                camera=card.camera,
                title=card.title,
                pip_camera=card.pip_camera,
                pip_title=card.pip_title or None,
                expires_at=t.expires_at,
                restores=runtime.takeover.covering is not None,
            )

        @mcp.tool(title="Caption the camera", annotations=write, meta=no_llm)
        @_failing
        async def camera_caption(text: str) -> Ok:
            """Set the line under the camera's video (who's at the door)."""
            up = runtime.takeover.current()
            if up is None or not isinstance(up.card, CameraTakeover):
                raise Fail("no_camera", "No camera is on screen.")
            runtime.takeover.update(TakeoverUpdate(caption=text[:120]))
            return Ok(ok=True)

        @mcp.tool(title="Stop the camera", annotations=write, meta=llm)
        async def camera_stop(camera: Camera | None = None) -> Stopped:  # type: ignore[valid-type]
            """Take the camera off the screen; what it covered comes back."""
            return Stopped(stopped=runtime.takeover.release(camera))

    return mcp


def mcp_app(server: MCPServer, cfg: McpConfig) -> ASGIApp:
    """The ASGI app to mount at /mcp: the token check around the SDK's
    Streamable HTTP app. JSON replies unless a tool sends progress."""
    inner = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=cfg.allowed_hosts,
            allowed_origins=[],
        ),
    )
    return BearerScopes(inner, cfg)
