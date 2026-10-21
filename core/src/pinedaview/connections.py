# SPDX-License-Identifier: Apache-2.0
"""Where this machine finds the services it talks to — the MQTT broker,
Antigua, go2rtc — as set from Settings → Connect.

Kept in ``<state_dir>/connections.json``, apart from ``household.json``,
because these addresses belong to one box: the primary reaches Antigua at
127.0.0.1, the standby at its own address, so ``scripts/sync-standby.sh``
leaves this file out. Laid over ``config.toml`` at startup, which is never
rewritten — a field set here wins, a field never touched here doesn't exist
in the file and the hand-written config stands.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pinedaview.config import Settings

logger = logging.getLogger(__name__)

FILENAME = "connections.json"

# section → the fields Connect may set on it.
_FIELDS: dict[str, tuple[str, ...]] = {
    "mqtt": ("enabled", "host", "port"),
    "antigua": ("url", "fallback_url"),
    "cameras": ("go2rtc",),
}


def _read(settings: Settings) -> dict[str, Any]:
    try:
        saved = json.loads((settings.state_dir / FILENAME).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return saved if isinstance(saved, dict) else {}


def load_connections(settings: Settings) -> None:
    """Lay saved connection edits over ``settings`` in place."""
    for section, values in _read(settings).items():
        if section not in _FIELDS or not isinstance(values, dict):
            continue
        target = getattr(settings, section)
        for key, value in values.items():
            if key not in _FIELDS[section]:
                continue
            try:
                checked = type(target).model_validate({**target.model_dump(), key: value})
                setattr(target, key, getattr(checked, key))
            except ValueError as exc:
                logger.warning("ignoring connections.json %s.%s: %s", section, key, exc)


def save_connection(settings: Settings, section: str, values: dict[str, Any]) -> None:
    """Apply ``values`` to ``settings.<section>`` and remember them."""
    allowed = {k: v for k, v in values.items() if k in _FIELDS[section]}
    target = getattr(settings, section)
    for key, value in allowed.items():
        setattr(target, key, value)
    doc = _read(settings)
    doc[section] = {**(doc.get(section) or {}), **allowed}
    path = settings.state_dir / FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2))
    except OSError as exc:
        logger.error("could not persist connections: %s", exc)
