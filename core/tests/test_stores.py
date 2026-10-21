# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import time

from pinedaview.stores import Store, StoreRegistry


def test_publish_then_snapshot() -> None:
    store = Store("weather", stale_after_s=100)
    assert store.snapshot() is None
    store.publish({"tempC": 20})
    entry = store.snapshot()
    assert entry is not None
    assert entry.value == {"tempC": 20}
    assert entry.stale is False


def test_failure_marks_stale_only_after_ttl() -> None:
    store = Store("weather", stale_after_s=0)
    store.publish({"tempC": 20})
    time.sleep(0.01)
    store.note_failure()
    entry = store.snapshot()
    assert entry is not None and entry.stale is True


def test_failure_before_any_value_is_a_noop() -> None:
    store = Store("weather", stale_after_s=0)
    store.note_failure()
    assert store.snapshot() is None


def test_registry_reuses_and_notifies() -> None:
    reg = StoreRegistry()
    first = reg.get_or_create("moon", stale_after_s=10)
    assert reg.get_or_create("moon", stale_after_s=10) is first

    seen: list[str] = []
    reg.on_change(seen.append)
    reg.notify("moon")
    assert seen == ["moon"]


def test_registry_snapshot_shape() -> None:
    reg = StoreRegistry()
    reg.get_or_create("a", stale_after_s=10).publish(1)
    reg.get_or_create("b", stale_after_s=10)
    snap = reg.snapshot()
    assert snap["b"] is None
    assert snap["a"] is not None and snap["a"]["value"] == 1
    assert list(snap) == ["a", "b"]
