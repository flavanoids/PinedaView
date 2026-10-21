# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from pinedaview.broadcast import Broadcaster
from pinedaview.timers import TimerService


async def test_subscription_receives_and_cleans_up() -> None:
    bus = Broadcaster()
    with bus.subscription() as queue:
        assert bus.subscriber_count == 1
        bus.publish({"type": "store", "key": "weather"})
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event["key"] == "weather"
    assert bus.subscriber_count == 0


async def test_publish_drops_events_for_a_full_queue() -> None:
    bus = Broadcaster()
    with bus.subscription():
        for _ in range(500):  # far more than the queue holds — must not raise
            bus.publish({"n": 1})


async def test_publish_with_no_subscribers_is_a_noop() -> None:
    Broadcaster().publish({"type": "store", "key": "moon"})


async def test_timer_add_list_cancel() -> None:
    svc = TimerService(Broadcaster())
    timer = svc.add(60, "Tea")
    assert [t.id for t in svc.list()] == [timer.id]
    assert svc.cancel(timer.id) is True
    assert svc.cancel(timer.id) is False
    assert svc.list() == []


async def test_timer_fires_and_broadcasts() -> None:
    bus = Broadcaster()
    with bus.subscription() as queue:
        svc = TimerService(bus)
        svc.add(0.001, "Now")
        await asyncio.wait_for(queue.get(), timeout=1.0)  # the "set" event

        await asyncio.sleep(0.02)
        svc._fire_due(datetime.now(UTC))
        fired = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert fired["action"] == "fire"
        assert fired["label"] == "Now"
        assert svc.list() == []


async def test_timer_run_loop_starts_and_stops() -> None:
    svc = TimerService(Broadcaster())
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
