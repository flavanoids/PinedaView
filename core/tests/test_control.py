# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import Any

import httpx
import pytest

from pinedaview import api as api_module
from pinedaview.control import ControlError, PinGate, turned


async def test_menu_page_served(client: httpx.AsyncClient) -> None:
    resp = await client.get("/menu")
    assert resp.status_code == 200
    assert "/api/control/restart-display" in resp.text
    assert "/api/control/restart-system" in resp.text
    assert 'id="dark-toggle"' in resp.text
    assert 'id="bottom-tab-bar"' in resp.text
    assert 'id="stage-header"' in resp.text
    assert 'rel="apple-touch-icon"' in resp.text
    assert 'rel="manifest"' in resp.text


async def test_manifest_and_apple_touch_icon_served(client: httpx.AsyncClient) -> None:
    manifest = await client.get("/manifest.json")
    assert manifest.status_code == 200
    data = manifest.json()
    assert data["name"] == "Pineda Display"
    assert data["display"] == "standalone"

    icon = await client.get("/apple-touch-icon.png")
    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/png"

    precomposed = await client.get("/apple-touch-icon-precomposed.png")
    assert precomposed.status_code == 200
    assert precomposed.headers["content-type"] == "image/png"


async def test_old_settings_page_redirects_to_menu(client: httpx.AsyncClient) -> None:
    resp = await client.get("/settings")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/menu#themes"


async def test_restart_needs_the_pin(
    client: httpx.AsyncClient, runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(api_module, "restart_display", lambda _control: calls.append("display"))
    monkeypatch.setattr(api_module, "restart_system", lambda _control: calls.append("system"))
    runtime.settings.control.pin = "100808"

    assert (await client.get("/api/control")).json() == {"pin_required": True, "snapshot": False}
    assert (await client.post("/api/control/restart-display")).status_code == 403
    wrong = {"x-control-pin": "123456"}
    assert (await client.post("/api/control/restart-system", headers=wrong)).status_code == 403
    assert calls == []

    right = {"x-control-pin": "100808"}
    assert (await client.post("/api/control/restart-display", headers=right)).status_code == 202
    assert (await client.post("/api/control/restart-system", headers=right)).status_code == 202
    assert calls == ["display", "system"]


async def test_wrong_pins_lock_out(
    client: httpx.AsyncClient, runtime: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(api_module, "restart_display", lambda _control: calls.append("display"))
    runtime.settings.control.pin = "100808"

    for _ in range(PinGate.MAX_MISSES):
        resp = await client.post("/api/control/restart-display", headers={"x-control-pin": "0"})
        assert resp.status_code == 403
    right = {"x-control-pin": "100808"}
    assert (await client.post("/api/control/restart-display", headers=right)).status_code == 429
    assert calls == []


async def test_restart_display_calls_control(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(api_module, "restart_display", lambda _control: calls.append("display"))

    resp = await client.post("/api/control/restart-display")
    assert resp.status_code == 202
    assert calls == ["display"]


async def test_restart_system_calls_control(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(api_module, "restart_system", lambda _control: calls.append("system"))

    resp = await client.post("/api/control/restart-system")
    assert resp.status_code == 202
    assert calls == ["system"]


async def test_restart_failure_is_500(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_control: Any) -> None:
        raise ControlError("no polkit rule")

    monkeypatch.setattr(api_module, "restart_display", _boom)

    resp = await client.post("/api/control/restart-display")
    assert resp.status_code == 500


def test_control_run_wraps_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from pinedaview import control
    from pinedaview.config import ControlConfig

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr("pinedaview.control.subprocess.run", _raise)
    with pytest.raises(ControlError):
        control.restart_display(ControlConfig())


def test_control_run_wraps_to_ssh_when_host_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from pinedaview import control
    from pinedaview.config import ControlConfig

    seen: list[list[str]] = []

    def _capture(cmd: list[str], **_kwargs: Any) -> Any:
        seen.append(cmd)

        class _Result:
            pass

        return _Result()

    monkeypatch.setattr("pinedaview.control.subprocess.run", _capture)
    control.restart_display(ControlConfig(host="airplaypi", user="pineda"))

    # seen[0] archives a diagnostic snapshot first; the restart comes last.
    assert all(cmd[:1] == ["ssh"] for cmd in seen)
    assert "pineda@airplaypi" in seen[-1]
    assert seen[-1][-1] == "pinedaview-kiosk.service"


def test_snapshot_shrinks_the_kiosk_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    from PIL import Image

    from pinedaview import control
    from pinedaview.config import ControlConfig

    frame = io.BytesIO()
    Image.new("RGB", (2048, 1280), "teal").save(frame, "PNG")
    seen: list[list[str]] = []

    def _grim(cmd: list[str], **_kwargs: Any) -> Any:
        seen.append(cmd)

        class _Result:
            stdout = frame.getvalue()

        return _Result()

    monkeypatch.setattr("pinedaview.control.subprocess.run", _grim)
    jpeg = control.snapshot(ControlConfig(host="airplaypi", user="pineda"))

    assert seen[0][-1] == "pinedaview-snapshot"
    assert Image.open(io.BytesIO(jpeg)).size == (1024, 640)
    with pytest.raises(ControlError):
        control.snapshot(ControlConfig())


async def test_snapshot_is_shared_and_fails_soft(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def _snap(_control: Any) -> bytes:
        calls.append(1)
        return b"jpeg"

    monkeypatch.setattr(api_module, "snapshot", _snap)
    for _ in range(3):
        resp = await client.get("/api/control/snapshot")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
    assert calls == [1]


async def test_snapshot_without_a_kiosk_is_503(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/control/snapshot")).status_code == 503


async def test_rotation_turns_the_kiosk(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    turned: list[str] = []
    monkeypatch.setattr(api_module, "rotation", lambda _control: "90")
    monkeypatch.setattr(api_module, "rotate", lambda _control, turn: turned.append(turn))

    assert (await client.get("/api/control/rotation")).json() == {"rotation": "90"}
    resp = await client.put("/api/control/rotation", json={"rotation": "270"})
    assert resp.status_code == 200
    assert turned == ["270"]
    assert (await client.put("/api/control/rotation", json={"rotation": "45"})).status_code == 422
    assert turned == ["270"]


async def test_rotation_without_a_kiosk_host(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_control: Any, _turn: str = "") -> str:
        raise ControlError("turning the screen needs [control].host")

    monkeypatch.setattr(api_module, "rotate", fail)
    resp = await client.put("/api/control/rotation", json={"rotation": "90"})
    assert resp.status_code == 503


@pytest.mark.parametrize(
    ("now", "to", "then"),
    [
        ("normal", "tall", "90"),
        ("270", "tall", "270"),
        ("90", "wide", "normal"),
        ("180", "wide", "180"),
        ("90", "flip", "270"),
        ("normal", "flip", "180"),
        ("180", "turn", "90"),
        ("270", "turn", "normal"),
    ],
)
def test_turned(now: str, to: str, then: str) -> None:
    assert turned(now, to) == then
