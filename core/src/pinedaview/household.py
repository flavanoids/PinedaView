# SPDX-License-Identifier: Apache-2.0
"""Household preferences: the settings that belong to the home rather than to
one screen or profile — how times and dates read, whether guests can add
photos.

They live in ``<state_dir>/household.json`` (which the standby sync already
copies) alongside the Settings sheet's edits to the server config (units,
location, the morning countdown). Those used to change only the running
process and were lost on the next restart; ``config.toml`` is left alone
because it holds hand-written operator settings this must never clobber.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from pinedaview.config import Settings

logger = logging.getLogger(__name__)

_FILENAME = "household.json"

TimeFormat = Literal["12h", "24h"]
DateStyle = Literal["long", "short", "off"]
GuestUploads = Literal["open", "review", "off"]


class HouseholdPrefs(BaseModel):
    time_format: TimeFormat = "12h"
    date_style: DateStyle = "long"
    """Under the clock: "Monday, October 12", "Mon, Oct 12", or nothing."""
    guest_uploads: GuestUploads = "open"
    """Photos added from the QR code / upload page: shown straight away, held
    for approval in Settings, or refused."""


def load_household(settings: Settings) -> HouseholdPrefs:
    """Read the saved preferences, and lay any saved config edits over
    ``settings`` in place."""
    path = settings.state_dir / _FILENAME
    try:
        saved: Any = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return HouseholdPrefs()
    if not isinstance(saved, dict):
        return HouseholdPrefs()
    _apply_overlay(settings, saved.get("config"))
    try:
        return HouseholdPrefs.model_validate(saved.get("prefs") or {})
    except ValidationError as exc:
        logger.warning("ignoring malformed household prefs: %s", exc)
        return HouseholdPrefs()


def save_household(settings: Settings, prefs: HouseholdPrefs) -> None:
    loc, countdown = settings.location, settings.countdown
    doc = {
        "prefs": prefs.model_dump(),
        "config": {
            "units": settings.units,
            "location": {"query": loc.query, "label": loc.label},
            "countdown": {
                "enabled": countdown.enabled,
                "start": countdown.start,
                "end": countdown.end,
            },
        },
    }
    path = settings.state_dir / _FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2))
    except OSError as exc:
        logger.error("could not persist household prefs: %s", exc)


def _apply_overlay(settings: Settings, overlay: Any) -> None:
    if not isinstance(overlay, dict):
        return
    if overlay.get("units") in ("imperial", "metric"):
        settings.units = overlay["units"]
    loc = overlay.get("location")
    if isinstance(loc, dict) and isinstance(loc.get("query"), str) and loc["query"]:
        if loc["query"] != settings.location.query:
            # Coordinates pinned in config.toml belong to the old place.
            settings.location.latitude = settings.location.longitude = None
        settings.location.query = loc["query"]
        settings.location.label = loc.get("label") if isinstance(loc.get("label"), str) else None
    countdown = overlay.get("countdown")
    if isinstance(countdown, dict):
        if isinstance(countdown.get("enabled"), bool):
            settings.countdown.enabled = countdown["enabled"]
        for key in ("start", "end"):
            if isinstance(countdown.get(key), str):
                setattr(settings.countdown, key, countdown[key])
