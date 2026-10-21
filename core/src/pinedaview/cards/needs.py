# SPDX-License-Identifier: Apache-2.0
"""Resolve a manifest's ``needs`` against the running environment.

An unmet need never crashes a card — it comes back ``blocked`` with the first
missing thing named, so the picker can grey it and the setup wizard can jump to
the setting that unblocks it.
"""

from __future__ import annotations

from dataclasses import dataclass

from pinedaview.cards.manifest import CardManifest
from pinedaview.config import Settings
from pinedaview.secrets import SecretStore


@dataclass(frozen=True, slots=True)
class NeedsEnv:
    settings: Settings
    secrets: SecretStore
    provided_stores: frozenset[str]
    """Store names that some *ready* card publishes (for ``provider:<id>``)."""
    mqtt_connected: bool = False
    has_photos: bool = False


@dataclass(frozen=True, slots=True)
class CardStatus:
    ready: bool
    reason: str | None = None

    @classmethod
    def ok(cls) -> CardStatus:
        return cls(ready=True)

    @classmethod
    def blocked(cls, reason: str) -> CardStatus:
        return cls(ready=False, reason=reason)


_HUMAN = {
    "location": "needs a location",
    "network": "needs network access",
    "photos": "needs at least one photo",
}


def _check_one(need: str, env: NeedsEnv) -> bool:
    if need == "location":
        loc = env.settings.location
        return bool(loc.query) or (loc.latitude is not None and loc.longitude is not None)
    if need == "network":
        return True  # no offline mode yet; always granted
    if need == "photos":
        return env.has_photos
    if need.startswith("secret:"):
        return env.secrets.has(need.split(":", 1)[1])
    if need.startswith("mqtt:"):
        return env.mqtt_connected
    if need.startswith("provider:"):
        return need.split(":", 1)[1] in env.provided_stores
    return False


def _describe(need: str) -> str:
    if need in _HUMAN:
        return _HUMAN[need]
    if need.startswith("secret:"):
        return f"needs a {need.split(':', 1)[1].replace('_', ' ')} key"
    if need.startswith("mqtt:"):
        return "needs an MQTT broker"
    if need.startswith("provider:"):
        return f"needs the {need.split(':', 1)[1]} feed"
    return f"unmet requirement: {need}"


def resolve_status(manifest: CardManifest, env: NeedsEnv) -> CardStatus:
    for need in manifest.needs:
        if not _check_one(need, env):
            return CardStatus.blocked(_describe(need))
    return CardStatus.ok()
