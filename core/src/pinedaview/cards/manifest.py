# SPDX-License-Identifier: Apache-2.0
"""``card.json`` — the manifest schema.

A card is a folder with a ``card.json``. The manifest says what the card needs,
what data it publishes, how big it wants to be, and what options it exposes. The
server validates every manifest at startup; an invalid one is skipped with a
logged error, never a crash.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from pinedaview.cards.duration import parse_duration

_ID_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z0-9-]+)*$")
_NEED_RE = re.compile(
    r"^(location|network|photos|secret:[a-z0-9_]+|mqtt:\S+|provider:[A-Za-z0-9._-]+)$"
)

SlotSize = Literal["strip", "small", "medium", "hero"]
Tier = Literal["lite", "standard", "rich"]
SettingType = Literal[
    "boolean", "integer", "number", "string", "enum", "list", "timerange", "secret", "beats"
]


class Slots(BaseModel):
    min: SlotSize = "small"
    ideal: SlotSize = "medium"
    max: SlotSize = "hero"
    aspect: str | None = None


class Refresh(BaseModel):
    interval: str = "15m"
    jitter: str = "0s"

    @field_validator("interval", "jitter")
    @classmethod
    def _valid_duration(cls, value: str) -> str:
        parse_duration(value)
        return value

    @property
    def interval_s(self) -> int:
        return round(parse_duration(self.interval))

    @property
    def jitter_s(self) -> int:
        return round(parse_duration(self.jitter))


class Setting(BaseModel):
    type: SettingType
    title: str
    description: str = ""
    """One sentence under the title in Settings, when the title alone won't do."""
    default: object = None
    enum: list[str] | None = None
    labels: dict[str, str] | None = None
    """Display names for ``enum`` values, where an id alone won't do."""
    min: float | None = None
    max: float | None = None


class TierHint(BaseModel):
    min: Tier = "lite"
    features: dict[str, Tier] = Field(default_factory=dict)


class Permissions(BaseModel):
    fetch_hosts: list[str] = Field(default_factory=list, alias="fetchHosts")

    model_config = {"populate_by_name": True}


class CardManifest(BaseModel):
    id: str
    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = "unknown"

    needs: list[str] = Field(default_factory=list)
    optional_needs: list[str] = Field(default_factory=list, alias="optionalNeeds")
    provides: list[str] = Field(default_factory=list)

    slots: Slots = Field(default_factory=Slots)
    refresh: Refresh = Field(default_factory=Refresh)
    settings: dict[str, Setting] = Field(default_factory=dict)
    tier: TierHint = Field(default_factory=TierHint)
    permissions: Permissions = Field(default_factory=Permissions)

    provider: str | None = None
    """A built-in provider key (``"weather"``) or a ``"module.path:Class"`` import."""
    entry: str | None = None
    """Client component path — informational for the server."""
    detail: bool = False
    """The card opens an expanded view when tapped."""

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError(f"card id must be kebab / reverse-dns: {value!r}")
        return value

    @field_validator("needs", "optional_needs")
    @classmethod
    def _valid_needs(cls, value: list[str]) -> list[str]:
        for need in value:
            if not _NEED_RE.match(need):
                raise ValueError(f"unknown need: {need!r}")
        return value

    def setting_defaults(self) -> dict[str, object]:
        return {key: spec.default for key, spec in self.settings.items()}
