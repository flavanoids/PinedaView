# SPDX-License-Identifier: Apache-2.0
"""Data stores.

A provider publishes its latest reading into a named :class:`Store`. Every
consumer — the debug route now, per-device view models and the SSE stream later —
reads the same store, so there is no "held fetcher reference vs. event bus"
split. A store keeps the last good value and flags it ``stale`` when a refresh
has failed for too long.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

ChangeListener = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class StoreEntry:
    value: Any
    updated_at: datetime
    stale: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "updatedAt": self.updated_at.isoformat(),
            "stale": self.stale,
        }


def _now() -> datetime:
    return datetime.now(UTC)


class Store:
    """One named slot holding the latest value from a single provider."""

    def __init__(self, key: str, stale_after_s: float) -> None:
        self.key = key
        self._stale_after_s = stale_after_s
        self._entry: StoreEntry | None = None
        self._last_success: datetime | None = None

    def publish(self, value: Any) -> None:
        self._last_success = _now()
        self._entry = StoreEntry(value=value, updated_at=self._last_success, stale=False)

    def note_failure(self) -> None:
        """Called after a failed refresh. Marks the held value stale once it is
        older than ``stale_after_s``; a store with no value yet stays empty."""
        if self._entry is None or self._last_success is None:
            return
        age = (_now() - self._last_success).total_seconds()
        if age >= self._stale_after_s and not self._entry.stale:
            self._entry = StoreEntry(
                value=self._entry.value,
                updated_at=self._entry.updated_at,
                stale=True,
            )

    def snapshot(self) -> StoreEntry | None:
        return self._entry


class StoreRegistry:
    """All stores, plus change notification for downstream consumers."""

    def __init__(self) -> None:
        self._stores: dict[str, Store] = {}
        self._listeners: list[ChangeListener] = []

    def get_or_create(self, key: str, *, stale_after_s: float) -> Store:
        store = self._stores.get(key)
        if store is None:
            store = Store(key, stale_after_s)
            self._stores[key] = store
        return store

    def get(self, key: str) -> Store | None:
        return self._stores.get(key)

    def on_change(self, listener: ChangeListener) -> None:
        self._listeners.append(listener)

    def notify(self, key: str) -> None:
        for listener in self._listeners:
            listener(key)

    def snapshot(self) -> dict[str, dict[str, Any] | None]:
        return {
            key: (entry.as_dict() if (entry := store.snapshot()) is not None else None)
            for key, store in sorted(self._stores.items())
        }
