# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from pinedaview.config import Settings
from pinedaview.registry import DEFAULT_PROFILE_ID, Device, Profile, Registry
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.view import ViewModel, _in_blackout, build_view_model


@pytest.fixture
async def registry(tmp_path: Path) -> Registry:
    reg = Registry(tmp_path / "reg.db")
    await reg.init()
    return reg


# ── profile CRUD ─────────────────────────────────────────────────────────────


async def test_create_profile_from_template(registry: Registry) -> None:
    await registry.update_profile("default", card_stack=["clock", "moon"])
    default = await registry.profile("default")
    made = await registry.create_profile("Bedside", template=default)
    assert made.name == "Bedside"
    assert made.card_stack == ["clock", "moon"]
    assert made.id != "default"


async def test_delete_profile_guards(registry: Registry) -> None:
    assert await registry.delete_profile("default") == "the default profile can't be deleted"

    p = await registry.create_profile("Desk")
    device = await registry.pair_device("D")
    await registry.update_device(device.id, profile_id=p.id)
    assert "device" in (await registry.delete_profile(p.id) or "")

    await registry.update_device(device.id, profile_id="default")
    assert await registry.delete_profile(p.id) is None
    assert await registry.delete_profile(p.id) == "unknown profile"


async def test_pair_device_gets_a_code(registry: Registry) -> None:
    device = await registry.pair_device("Screen")
    assert device.pair_code is not None and len(device.pair_code) == 4
    assert device.brightness == 1.0


# ── projection + follow + blackout ───────────────────────────────────────────


def _vm(device: Device, profile: Profile, now: datetime | None = None) -> ViewModel:
    return build_view_model(
        device=device,
        profile=profile,
        settings=Settings(),
        stores=StoreRegistry(),
        state=DisplayState.IDLE,
        now=now,
    )


def test_view_model_projects_the_profile() -> None:
    device = Device(id="d", name="Kitchen", profile_id="p", paired_at=datetime.now(UTC))
    profile = Profile(id="p", name="Kitchen", card_stack=["clock", "moon"], theme="ocean")
    vm = _vm(device, profile)
    assert vm.profile_name == "Kitchen"
    assert vm.theme == "ocean"
    assert {vm.hero.card, *[c.id for c in vm.cards]} == {"clock", "moon"}


def test_view_model_carries_brightness_and_profile_name() -> None:
    device = Device(id="d", name="d", profile_id="p", paired_at=datetime.now(UTC), brightness=0.4)
    vm = _vm(device, Profile(id="p", name="Desk", card_stack=["clock"]))
    assert vm.brightness == pytest.approx(0.4)
    assert vm.blackout is False


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 1, 1, 23, 30), True),
        (datetime(2026, 1, 1, 3, 0), True),
        (datetime(2026, 1, 1, 12, 0), False),
    ],
)
def test_blackout_window_wraps_past_midnight(now: datetime, expected: bool) -> None:
    assert _in_blackout(now, "23:00", "06:00") is expected


def test_no_blackout_without_a_window() -> None:
    assert _in_blackout(datetime(2026, 1, 1, 3, 0), None, None) is False


async def test_api_follow_mirrors_another_screen(client: httpx.AsyncClient) -> None:
    a = (await client.post("/api/devices/pair", json={"name": "A"})).json()["id"]
    b = (await client.post("/api/devices/pair", json={"name": "B"})).json()["id"]

    # give A a custom stack, point B at A
    await client.patch(f"/api/devices/{a}", json={"card_stack": ["clock", "moon"]})
    await client.patch(f"/api/devices/{b}", json={"follow": a})

    view_b = (await client.get(f"/api/view/{b}")).json()
    assert view_b["device_id"] == b  # still addressed to B
    assert {view_b["hero"]["card"], *[c["id"] for c in view_b["cards"]]} == {"clock", "moon"}


async def test_api_identify_and_profile_flow(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "K"})).json()["id"]
    assert (await client.post(f"/api/devices/{device_id}/identify")).status_code == 202
    assert (await client.post("/api/devices/ghost/identify")).status_code == 404

    created = await client.post(
        "/api/profiles", json={"name": "Bedside", "copy_from": DEFAULT_PROFILE_ID}
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    await client.patch(f"/api/devices/{device_id}", json={"profile_id": pid})
    # can't delete a profile in use
    assert (await client.delete(f"/api/profiles/{pid}")).status_code == 409
    assert (await client.delete("/api/profiles/default")).status_code == 409
