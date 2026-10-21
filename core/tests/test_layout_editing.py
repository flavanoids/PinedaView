# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from pinedaview.config import Settings
from pinedaview.registry import Device, Profile, Registry
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.view import build_view_model


@pytest.fixture
async def registry(tmp_path: Path) -> Registry:
    reg = Registry(tmp_path / "reg.db")
    await reg.init()
    return reg


async def test_device_card_stack_override_persists(registry: Registry) -> None:
    device = await registry.pair_device("Kitchen")
    updated = await registry.update_device(
        device.id, card_stack=["clock", "moon"], layout="material", locked=True
    )
    assert updated is not None
    assert updated.card_stack == ["clock", "moon"]
    assert updated.layout == "material"
    assert updated.locked is True
    # survives a reload
    reloaded = await registry.device(device.id)
    assert reloaded is not None and reloaded.card_stack == ["clock", "moon"]


async def test_update_profile(registry: Registry) -> None:
    updated = await registry.update_profile("default", card_stack=["weather"], layout="square_grid")
    assert updated is not None
    assert updated.card_stack == ["weather"]
    assert updated.layout == "square_grid"
    assert await registry.update_profile("ghost", name="x") is None


def test_view_model_prefers_device_overrides() -> None:
    device = Device(
        id="d",
        name="d",
        profile_id="p",
        paired_at=datetime.now(UTC),
        card_stack=["clock", "moon"],
        layout="material",
        locked=True,
    )
    profile = Profile(id="p", name="p", card_stack=["weather", "phrase"], layout="wide_grid")
    vm = build_view_model(
        device=device,
        profile=profile,
        settings=Settings(),
        stores=StoreRegistry(),
        state=DisplayState.IDLE,
        detail_cards={"weather"},
    )
    assert vm.layout == "material"
    assert vm.locked is True
    assert {vm.hero.card, *[c.id for c in vm.cards]} == {"clock", "moon"}


def test_view_model_marks_detail_cards() -> None:
    device = Device(id="d", name="d", profile_id="p", paired_at=datetime.now(UTC))
    profile = Profile(id="p", name="p", card_stack=["weather", "moon", "phrase"])
    vm = build_view_model(
        device=device,
        profile=profile,
        settings=Settings(),
        stores=StoreRegistry(),
        state=DisplayState.IDLE,
        detail_cards={"moon"},
    )
    by_id = {c.id: c.detail for c in vm.cards}
    assert by_id["moon"] is True
    assert by_id["phrase"] is False


async def test_api_layout_editor_round_trip(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "K"})).json()["id"]

    patched = await client.patch(
        f"/api/devices/{device_id}", json={"card_stack": ["clock", "moon"], "layout": "square_grid"}
    )
    assert patched.status_code == 200

    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["layout"] == "square_grid"
    assert {view["hero"]["card"], *[c["id"] for c in view["cards"]]} == {"clock", "moon"}

    prof = await client.patch("/api/profiles/default", json={"card_stack": ["phrase"]})
    assert prof.status_code == 200
    assert prof.json()["card_stack"] == ["phrase"]
    assert (await client.patch("/api/profiles/ghost", json={"name": "x"})).status_code == 404


async def test_material_theme_is_served(client: httpx.AsyncClient) -> None:
    names = [t["name"] for t in (await client.get("/api/themes")).json()["themes"]]
    assert "material" in names


async def test_themes_carry_a_surface(client: httpx.AsyncClient) -> None:
    themes = {t["name"]: t for t in (await client.get("/api/themes")).json()["themes"]}
    assert themes["quiet_canvas"]["surface"] == "solid"
    glass = themes["liquid_glass"]
    assert glass["surface"] == "glass"
    assert glass["cards"]["moon"]  # glass tints the moon card too


async def test_cards_endpoint_flags_detail(client: httpx.AsyncClient) -> None:
    cards = {c["id"]: c for c in (await client.get("/api/cards")).json()}
    assert cards["weather"]["detail"] is True
    assert cards["clock"]["detail"] is False


async def test_profile_clock_face_is_pushed_through_the_view(
    client: httpx.AsyncClient,
) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "Hall"})).json()["id"]
    assert (await client.get(f"/api/view/{device_id}")).json()["clock_face"] is None

    patched = await client.patch("/api/profiles/default", json={"clock_face": "qlock"})
    assert patched.status_code == 200
    assert patched.json()["clock_face"] == "qlock"
    assert (await client.get(f"/api/view/{device_id}")).json()["clock_face"] == "qlock"

    # "" hands the choice back to each screen; unknown faces are rejected.
    cleared = await client.patch("/api/profiles/default", json={"clock_face": ""})
    assert cleared.json()["clock_face"] is None
    bogus = await client.patch("/api/profiles/default", json={"clock_face": "sundial"})
    assert bogus.status_code == 422
