# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from pinedaview.config import Settings
from pinedaview.registry import Device, Grid, GridItem, Profile, Registry
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.view import ViewModel, build_view_model


def _grid(*items: tuple[str, int, int, int, int], cols: int = 4) -> Grid:
    return Grid(cols=cols, items=[GridItem(card=c, x=x, y=y, w=w, h=h) for c, x, y, w, h in items])


@pytest.fixture
async def registry(tmp_path: Path) -> Registry:
    reg = Registry(tmp_path / "reg.db")
    await reg.init()
    return reg


def test_grid_rejects_overlap_offgrid_and_duplicates() -> None:
    with pytest.raises(ValidationError, match="overlaps"):
        _grid(("clock", 0, 0, 2, 2), ("moon", 1, 1, 1, 1))
    with pytest.raises(ValidationError, match="off the grid"):
        _grid(("clock", 3, 0, 2, 1))
    with pytest.raises(ValidationError, match="twice"):
        _grid(("clock", 0, 0, 1, 1), ("clock", 1, 0, 1, 1))


def test_hero_item_is_the_biggest_box_first_in_reading_order() -> None:
    grid = _grid(("moon", 0, 0, 1, 1), ("photo", 2, 0, 2, 2), ("clock", 0, 2, 2, 2))
    assert grid.rows == 4
    hero = grid.hero_item()
    assert hero is not None and hero.card == "photo"


async def test_set_grid_keeps_history(registry: Registry) -> None:
    device = await registry.pair_device("Kitchen")
    first = _grid(("clock", 0, 0, 2, 2))
    second = _grid(("moon", 0, 0, 1, 1))
    await registry.set_grid(device.id, first)
    updated = await registry.set_grid(device.id, second)
    assert updated is not None and updated.grid == second
    history = await registry.layout_history(device.id)
    # newest first: the grid before `second`, then the automatic layout
    assert [h.grid for h in history] == [first, None]
    back = await registry.set_grid(device.id, None)
    assert back is not None and back.grid is None
    assert await registry.set_grid("ghost", first) is None


async def test_history_is_capped(registry: Registry) -> None:
    device = await registry.pair_device("Kitchen")
    for n in range(14):
        await registry.set_grid(device.id, _grid(("clock", 0, 0, 1, n + 1)))
    assert len(await registry.layout_history(device.id)) == 10


def _view(grid: Grid, state: DisplayState = DisplayState.IDLE) -> ViewModel:
    device = Device(
        id="d",
        name="d",
        profile_id="p",
        paired_at=datetime.now(UTC),
        card_stack=["weather"],
        cards_off=["clock"],
        grid=grid,
    )
    profile = Profile(id="p", name="p", card_stack=["weather"], hero_card="weather")
    return build_view_model(
        device=device,
        profile=profile,
        settings=Settings(),
        stores=StoreRegistry(),
        state=state,
    )


def test_view_follows_the_grid_not_the_stack() -> None:
    grid = _grid(("moon", 0, 0, 1, 1), ("clock", 1, 0, 3, 2), ("phrase", 0, 1, 1, 1))
    vm = _view(grid)
    assert vm.grid == grid
    assert vm.hero.kind == "card" and vm.hero.card == "clock"
    assert [c.id for c in vm.cards] == ["moon", "phrase"]


def test_grid_card_with_nothing_today_leaves_an_empty_box() -> None:
    grid = _grid(("on-this-day", 0, 0, 2, 2), ("moon", 2, 0, 1, 1))
    vm = _view(grid)
    assert vm.hero.card is None
    assert [c.id for c in vm.cards] == ["moon"]


def test_countdown_still_takes_the_big_box() -> None:
    vm = _view(_grid(("clock", 0, 0, 2, 2), ("moon", 2, 0, 1, 1)), DisplayState.COUNTDOWN)
    assert vm.hero.kind == "countdown"
    assert [c.id for c in vm.cards] == ["moon"]


async def _pair(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/devices/pair", json={"name": "Kitchen"})
    return str(r.json()["id"])


async def test_grid_endpoints(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    body = {"grid": {"cols": 4, "items": [{"card": "clock", "x": 0, "y": 0, "w": 2, "h": 2}]}}
    r = await client.put(f"/api/devices/{device_id}/grid", json=body)
    assert r.status_code == 200
    assert r.json()["grid"]["items"][0]["card"] == "clock"
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["grid"]["cols"] == 4

    bad = {"grid": {"cols": 4, "items": [{"card": "nope", "x": 0, "y": 0, "w": 1, "h": 1}]}}
    assert (await client.put(f"/api/devices/{device_id}/grid", json=bad)).status_code == 422
    overlap = {
        "grid": {
            "cols": 4,
            "items": [
                {"card": "clock", "x": 0, "y": 0, "w": 2, "h": 2},
                {"card": "moon", "x": 1, "y": 1, "w": 1, "h": 1},
            ],
        }
    }
    assert (await client.put(f"/api/devices/{device_id}/grid", json=overlap)).status_code == 422

    r = await client.put(f"/api/devices/{device_id}/grid", json={"grid": None})
    assert r.json()["grid"] is None
    history = (await client.get(f"/api/devices/{device_id}/grid/history")).json()
    assert [h["grid"] is None for h in history] == [False, True]
    assert (await client.get("/api/devices/ghost/grid/history")).status_code == 404
