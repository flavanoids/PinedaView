# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
from typing import Any

from pinedaview.config import ProviderConfig, Settings
from pinedaview.providers.base import Provider, ProviderContext, ProviderError
from pinedaview.providers.scheduler import Scheduler
from pinedaview.stores import Store, StoreRegistry


class _StubProvider(Provider):
    key = "stub"

    def __init__(self, result: dict[str, Any] | None | Exception, key: str = "stub") -> None:
        super().__init__()
        self.key = key  # type: ignore[misc]
        self._result = result
        self.calls = 0

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return 300

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _fixture() -> tuple[Scheduler, StoreRegistry, ProviderContext, Store]:
    settings = Settings()
    registry = StoreRegistry()
    scheduler = Scheduler(settings, registry, [])
    ctx = ProviderContext(settings, registry)
    store = registry.get_or_create("stub", stale_after_s=600)
    return scheduler, registry, ctx, store


async def test_success_publishes_and_returns_interval_plus_jitter() -> None:
    scheduler, _reg, ctx, store = _fixture()
    provider = _StubProvider({"ok": 1})
    delay = await scheduler._poll_once(provider, ctx, store, 300)
    assert 300 <= delay <= 300 + ProviderConfig().jitter_s
    snap = store.snapshot()
    assert snap is not None and snap.value == {"ok": 1}


async def test_none_result_retries_soon_without_touching_store() -> None:
    scheduler, _reg, ctx, store = _fixture()
    delay = await scheduler._poll_once(_StubProvider(None), ctx, store, 300)
    assert delay == ProviderConfig().defer_interval_s
    assert store.snapshot() is None


async def test_provider_error_retries_and_notes_failure() -> None:
    scheduler, reg, ctx, store = _fixture()
    seen: list[str] = []
    reg.on_change(seen.append)
    store.publish({"old": 1})
    delay = await scheduler._poll_once(_StubProvider(ProviderError("boom")), ctx, store, 300)
    assert delay == ProviderConfig().retry_interval_s
    assert seen == ["stub"]


async def test_unexpected_exception_is_contained() -> None:
    scheduler, _reg, ctx, store = _fixture()
    delay = await scheduler._poll_once(_StubProvider(RuntimeError("kaboom")), ctx, store, 300)
    assert delay == ProviderConfig().retry_interval_s


async def test_run_starts_a_loop_per_provider_and_sync_adds_and_removes() -> None:
    settings = Settings()
    registry = StoreRegistry()
    pool = [_StubProvider({"ok": 1}, key="a")]

    async def quick_sleep(_seconds: float) -> None:
        await asyncio.sleep(0)

    scheduler = Scheduler(settings, registry, lambda: list(pool), sleep=quick_sleep)
    run_task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.02)
    assert set(scheduler.provider_keys) == {"a"}
    assert pool[0].calls >= 1

    # a card becomes ready → its provider appears without a restart
    pool.append(_StubProvider({"ok": 2}, key="b"))
    scheduler.sync()
    await asyncio.sleep(0)
    assert set(scheduler.provider_keys) == {"a", "b"}

    # a card becomes blocked → its loop is cancelled
    pool.pop(0)
    scheduler.sync()
    await asyncio.sleep(0)
    assert set(scheduler.provider_keys) == {"b"}

    run_task.cancel()
    await asyncio.gather(run_task, return_exceptions=True)


def test_sync_is_a_noop_before_run() -> None:
    scheduler = Scheduler(Settings(), StoreRegistry(), [_StubProvider({"ok": 1})])
    scheduler.sync()
    assert scheduler.provider_keys == ["stub"]  # reported from the source, no tasks yet


async def test_refresh_polls_a_provider_again_now() -> None:
    settings = Settings()
    registry = StoreRegistry()
    stub = _StubProvider({"ok": 1}, key="a")

    async def long_sleep(_seconds: float) -> None:
        await asyncio.sleep(3600)

    scheduler = Scheduler(settings, registry, [stub], sleep=long_sleep)
    runner = asyncio.create_task(scheduler.run())
    for _ in range(5):
        await asyncio.sleep(0)
    assert stub.calls == 1
    scheduler.refresh("a")
    scheduler.refresh("missing")  # not running: nothing to do
    for _ in range(5):
        await asyncio.sleep(0)
    assert stub.calls == 2
    runner.cancel()
    await asyncio.gather(runner, return_exceptions=True)
