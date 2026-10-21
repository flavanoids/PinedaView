# SPDX-License-Identifier: Apache-2.0
"""Commute — Google Directions. Needs a key (``secret:google_maps``) and a list
of stops in the card's own settings; nothing is hardcoded."""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError
from pinedaview.state import parse_hhmm

_URL = "https://maps.googleapis.com/maps/api/directions/json"


def _leg(stop: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    routes = response.get("routes") if isinstance(response, dict) else None
    leg = routes[0]["legs"][0] if routes else {}
    traffic = leg.get("duration_in_traffic") or leg.get("duration") or {}
    base = leg.get("duration", {})
    minutes = round(traffic.get("value", 0) / 60) if traffic else 0
    base_minutes = round(base.get("value", 0) / 60) if base else minutes
    return {
        "label": stop.get("label") or stop.get("address", "Stop"),
        "address": stop.get("address", ""),
        "minutes": minutes,
        "delayMinutes": max(0, minutes - base_minutes),
        "status": response.get("status", "UNKNOWN") if isinstance(response, dict) else "ERROR",
    }


def _during_rush(window: object, now: datetime) -> bool:
    """Whether ``now`` falls in a "HH:MM-HH:MM" window (wraps past midnight)."""
    if not isinstance(window, str) or "-" not in window:
        return False
    try:
        start, end = (parse_hhmm(part) for part in window.split("-", 1))
    except ValueError:
        return False
    current = now.time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


class CommuteProvider(Provider):
    key = "commute"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:  # noqa: ARG002
        return 240

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        key = ctx.secret("google_maps")
        if not key:
            return None
        origin = ctx.settings.location.query
        stops = ctx.card_setting("commute", "stops") or []
        routes = []
        for stop in stops:
            if not isinstance(stop, dict) or not stop.get("address"):
                continue
            params = {
                "origin": origin,
                "destination": stop["address"],
                "departure_time": "now",
                "key": key,
            }
            if stop.get("avoid"):
                params["avoid"] = stop["avoid"]
            query = urllib.parse.urlencode(params)
            response = await ctx.fetch_json(f"{_URL}?{query}", allow_hosts=["maps.googleapis.com"])
            if not isinstance(response, dict):
                raise ProviderError("unexpected Directions payload")
            routes.append(_leg(stop, response))

        during_rush = _during_rush(
            ctx.card_setting("commute", "rushWindow"), datetime.now().astimezone()
        )
        if during_rush:
            # The routes that need attention right now lead — the legacy app's
            # "primary routes get the large ETA treatment" during the commute
            # window, generalized to whichever stop is actually delayed today
            # rather than a fixed, hand-picked pair.
            routes.sort(key=lambda r: r["delayMinutes"], reverse=True)
        return {"routes": routes, "duringRush": during_rush}
