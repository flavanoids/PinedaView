# SPDX-License-Identifier: Apache-2.0
"""First-run setup: IP geolocation and writing the config file that marks the
wizard done."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
import tomli_w

from pinedaview.config import Settings

logger = logging.getLogger(__name__)

_GEO_URL = "http://ip-api.com/json/?fields=status,city,regionName,country,lat,lon,query"


class DetectedLocation:
    def __init__(self, label: str, query: str, lat: float | None, lon: float | None) -> None:
        self.label = label
        self.query = query
        self.latitude = lat
        self.longitude = lon

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "query": self.query,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


async def detect_location(client: httpx.AsyncClient) -> DetectedLocation | None:
    """Best-effort geolocation from the server's public IP. Returns ``None`` if
    it can't be reached — the wizard falls back to manual entry."""
    try:
        response = await client.get(_GEO_URL, timeout=5.0)
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("geolocation unavailable: %s", exc)
        return None
    if not isinstance(data, dict) or data.get("status") != "success":
        return None
    city = data.get("city") or ""
    region = data.get("regionName") or ""
    label = ", ".join(part for part in (city, region) if part) or data.get("country", "")
    lat, lon = data.get("lat"), data.get("lon")
    query = f"{lat},{lon}" if lat is not None and lon is not None else label
    return DetectedLocation(label=label, query=query, lat=lat, lon=lon)


def _config_document(settings: Settings) -> dict[str, Any]:
    loc = settings.location
    doc: dict[str, Any] = {
        "units": settings.units,
        "theme": settings.theme,
        "setup_complete": True,
        "location": {"query": loc.query},
    }
    if loc.label:
        doc["location"]["label"] = loc.label
    if loc.latitude is not None and loc.longitude is not None:
        doc["location"]["latitude"] = loc.latitude
        doc["location"]["longitude"] = loc.longitude
    if settings.countdown.enabled:
        doc["countdown"] = {
            "enabled": True,
            "start": settings.countdown.start,
            "end": settings.countdown.end,
        }
    return doc


def write_config(settings: Settings, path: Path = Path("config.toml")) -> None:
    path.write_text(tomli_w.dumps(_config_document(settings)))
    settings.setup_complete = True
    logger.info("wrote %s — setup complete", path)
