# SPDX-License-Identifier: Apache-2.0
"""Operational surfaces: a deep health check, Prometheus metrics, and a plain
HTML status page — because a headless server has no screen to look at.

None of these touch the frozen v0 wire contract; they're for operators, not the
client.
"""

from __future__ import annotations

import html
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pinedaview import __version__

if TYPE_CHECKING:
    from pinedaview.runtime import Runtime

_STARTED = time.monotonic()


def uptime_s() -> float:
    return time.monotonic() - _STARTED


async def health_report(runtime: Runtime) -> dict[str, Any]:
    """A deep check: the database, the scheduler, the broker, and store freshness.

    ``ok`` is false only when something a running server genuinely needs is
    broken (the database). A stale provider or a disconnected optional broker is
    reported but doesn't fail the check.
    """
    checks: dict[str, str] = {}

    try:
        await runtime.devices.profiles()
        checks["database"] = "ok"
    except Exception as exc:  # report any failure verbatim, don't crash the check
        checks["database"] = f"error: {exc}"

    provider_keys = runtime.scheduler.provider_keys
    checks["scheduler"] = "ok" if provider_keys else "no providers running"

    if runtime.mqtt is not None:
        if runtime.mqtt.connected:
            checks["mqtt"] = "connected"
        elif runtime.mqtt.last_error:
            checks["mqtt"] = f"configured, not connected ({runtime.mqtt.last_error})"
        else:
            checks["mqtt"] = "configured, not connected"

    snap = runtime.stores.snapshot()
    stale = [k for k, v in snap.items() if v and v.get("stale")]
    checks["stores"] = f"{len(snap) - len(stale)}/{len(snap)} fresh"
    if stale:
        checks["stale_stores"] = ", ".join(sorted(stale))

    ok = checks["database"] == "ok"
    return {
        "ok": ok,
        "status": "ok" if ok else "degraded",
        "app_version": __version__,
        "uptime_s": round(uptime_s(), 1),
        "checks": checks,
    }


def _store_age_s(updated_at: str) -> float:
    try:
        dt = datetime.fromisoformat(updated_at)
    except ValueError:  # pragma: no cover - stored values are always isoformat
        return -1.0
    return (datetime.now(UTC) - dt).total_seconds()


def render_metrics(runtime: Runtime) -> str:
    """Prometheus text exposition (version 0.0.4)."""
    snap = runtime.stores.snapshot()
    lines: list[str] = [
        "# HELP pineda_up 1 if the server is responding.",
        "# TYPE pineda_up gauge",
        "pineda_up 1",
        "# HELP pineda_build_info Build metadata.",
        "# TYPE pineda_build_info gauge",
        f'pineda_build_info{{version="{__version__}"}} 1',
        "# HELP pineda_uptime_seconds Seconds since start.",
        "# TYPE pineda_uptime_seconds gauge",
        f"pineda_uptime_seconds {uptime_s():.0f}",
        "# HELP pineda_sse_subscribers Currently connected live-stream clients.",
        "# TYPE pineda_sse_subscribers gauge",
        f"pineda_sse_subscribers {runtime.broadcaster.subscriber_count}",
        "# HELP pineda_providers_running Scheduler poll loops running.",
        "# TYPE pineda_providers_running gauge",
        f"pineda_providers_running {len(runtime.scheduler.provider_keys)}",
        "# HELP pineda_cards_ready Cards whose needs are met.",
        "# TYPE pineda_cards_ready gauge",
        f"pineda_cards_ready {len(runtime.cards.ready_ids())}",
        "# HELP pineda_cards_total Cards installed.",
        "# TYPE pineda_cards_total gauge",
        f"pineda_cards_total {len(runtime.cards.all())}",
    ]
    if runtime.mqtt is not None:
        lines += [
            "# HELP pineda_mqtt_connected 1 if the broker is connected.",
            "# TYPE pineda_mqtt_connected gauge",
            f"pineda_mqtt_connected {int(runtime.mqtt.connected)}",
        ]
    lines += [
        "# HELP pineda_store_stale 1 if a store's held value is stale.",
        "# TYPE pineda_store_stale gauge",
        "# HELP pineda_store_age_seconds Age of a store's held value.",
        "# TYPE pineda_store_age_seconds gauge",
    ]
    for key, value in snap.items():
        stale = 1 if value and value.get("stale") else 0
        lines.append(f'pineda_store_stale{{store="{key}"}} {stale}')
        if value:
            lines.append(
                f'pineda_store_age_seconds{{store="{key}"}} {_store_age_s(value["updatedAt"]):.0f}'
            )
    return "\n".join(lines) + "\n"


async def render_status_page(runtime: Runtime) -> str:
    """A no-JS operator page. There is no screen on the server itself."""
    report = await health_report(runtime)
    snap = runtime.stores.snapshot()

    rows = "".join(
        f"<tr><td>{html.escape(k)}</td>"
        f"<td>{'stale' if v and v.get('stale') else ('—' if not v else 'fresh')}</td>"
        f"<td>{'' if not v else html.escape(str(v['updatedAt']))}</td></tr>"
        for k, v in snap.items()
    )
    checks = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(val))}</td></tr>"
        for k, val in report["checks"].items()
    )
    badge = "#3fb950" if report["ok"] else "#d29922"
    mins = int(uptime_s() // 60)
    store_rows = rows or '<tr><td colspan="3">no stores yet</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PinedaDisplay Web — status</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;padding:2rem;background:#0d1117;color:#c9d1d9}}
 h1{{font-size:1.1rem;margin:0 0 .25rem}} .v{{color:#8b949e}}
 .dot{{display:inline-block;width:.6rem;height:.6rem;border-radius:50%;background:{badge};margin-right:.4rem}}
 table{{border-collapse:collapse;margin:1rem 0;width:100%;max-width:40rem}}
 td,th{{text-align:left;padding:.35rem .6rem;border-bottom:1px solid #21262d}}
 th{{color:#8b949e;font-weight:600}}
</style></head><body>
<h1><span class="dot"></span>PinedaDisplay Web</h1>
<p class="v">v{html.escape(__version__)} · up {mins} min · {report["status"]}</p>
<table><tr><th>check</th><th>result</th></tr>{checks}</table>
<table><tr><th>store</th><th>state</th><th>updated</th></tr>{store_rows}</table>
<p class="v">Live JSON at <a href="/api/health">/api/health</a> ·
metrics at <a href="/api/metrics">/api/metrics</a></p>
</body></html>
"""
