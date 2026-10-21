# SPDX-License-Identifier: Apache-2.0
"""The home cameras' livestreams, kept in step with the camera card.

The Eufy cameras are battery-powered: Home Assistant's eufy_security starts
a camera's P2P livestream (pushed into go2rtc, which /api/cameras/…/stream.mp4
relays) only when asked, and every second it runs costs battery. So the
stream follows the card: up when a camera card goes up — whoever put it there,
the MCP tools, the REST API, a doorbell ring — and down the moment it isn't
(dismissed, replaced, timed out). One reconciler does the HA calls, one at a
time, so a quick show-hide-show never leaves a stream running."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import httpx

from pinedaview.config import CamerasConfig
from pinedaview.takeover import CameraTakeover, Takeover, TakeoverService

logger = logging.getLogger(__name__)


class CameraError(RuntimeError):
    pass


def read_ha_token(cfg: CamerasConfig) -> str | None:
    if cfg.ha_token_file is None:
        return None
    try:
        for line in cfg.ha_token_file.read_text().splitlines():
            if line.startswith("HA_TOKEN="):
                return line.split("=", 1)[1].strip()
    except OSError as exc:
        logger.warning("cameras: can't read the HA token: %s", exc)
    return None


class CameraService:
    def __init__(self, cfg: CamerasConfig, takeover: TakeoverService, http: httpx.AsyncClient):
        self._cfg = cfg
        self._takeover = takeover
        self._http = http
        self._token = read_ha_token(cfg) if cfg.ha_url else None
        self._want: list[str] = []
        self._live: set[str] = set()
        self._wake = asyncio.Event()
        if self.drives_streams:
            takeover.on_change(self._follow)

    @property
    def names(self) -> list[str]:
        return list(self._cfg.streams)

    @property
    def drives_streams(self) -> bool:
        return bool(self._cfg.ha_url and self._token)

    def title(self, name: str) -> str:
        return self._cfg.titles.get(name) or name.replace("_", " ").capitalize()

    @property
    def live(self) -> str | None:
        """The primary camera whose livestream this server has running (or None)."""
        for cam in self._want:
            if cam in self._live:
                return cam
        return next(iter(self._live)) if self._live else None

    async def started(self, name: str, timeout: float = 8.0) -> None:
        """Wait (up to `timeout`) for `name`'s livestream to be started, when
        this server starts them: asked for the video as the card goes up, the
        screen would otherwise get an error and only try again later."""
        if not self.drives_streams:
            return
        end = asyncio.get_running_loop().time() + timeout
        while name not in self._live and name in self._want:
            if asyncio.get_running_loop().time() > end:
                return
            await asyncio.sleep(0.1)

    def show(self, name: str, seconds: float, pip: str | None = None) -> Takeover:
        if name not in self._cfg.streams:
            raise CameraError(f"unknown camera: {name}")
        if pip is not None and pip not in self._cfg.streams:
            raise CameraError(f"unknown camera: {pip}")
        card = CameraTakeover(
            kind="camera",
            camera=name,
            title=self.title(name),
            pip_camera=pip,
            pip_title=self.title(pip) if pip else "",
        )
        return self._takeover.show(card, seconds)

    def status(self) -> list[dict[str, Any]]:
        """Each camera with its battery (from the latest snapshot's notes)."""
        up = self._takeover.current()
        showing_cams: set[str] = set()
        if up and isinstance(up.card, CameraTakeover):
            showing_cams.add(up.card.camera)
            if up.card.pip_camera:
                showing_cams.add(up.card.pip_camera)
        out = []
        for name in self._cfg.streams:
            meta: dict[str, Any] = {}
            if self._cfg.snapshots_dir is not None:
                with contextlib.suppress(OSError, ValueError):
                    meta = json.loads((self._cfg.snapshots_dir / f"{name}.json").read_text())
            out.append(
                {
                    "name": name,
                    "title": self.title(name),
                    "battery": meta.get("battery"),
                    "showing": name in showing_cams,
                }
            )
        return out

    # ── the stream follows the card ──

    def _follow(self, up: Takeover | None) -> None:
        want: list[str] = []
        if up and isinstance(up.card, CameraTakeover):
            want.append(up.card.camera)
            if up.card.pip_camera and up.card.pip_camera in self._cfg.streams:
                want.append(up.card.pip_camera)
        if want != self._want:
            self._want = want
            self._wake.set()

    async def run(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            # Stop any camera that's live but no longer wanted
            for cam in list(self._live):
                if cam not in self._want:
                    await self._call("stop_p2p_livestream", cam)
                    self._live.discard(cam)
            # All at once: one after the other, the second camera's wake
            # (~2-5 s) was added to the first's, and the doorbell sat at 95%.
            # A pip that won't start still leaves the primary up.
            todo = [cam for cam in self._want if cam not in self._live]
            for cam, ok in zip(todo, await asyncio.gather(*map(self._start, todo)), strict=True):
                if ok:
                    self._live.add(cam)

    async def _start(self, cam: str) -> bool:
        ok = await self._call("start_p2p_livestream", cam, timeout=20)
        if ok is not False:
            # Slower than that (a cold wake): it's still coming, so it counts
            # as live, and gets stopped with the card.
            return True
        # Refused: a start that hung can leave the bridge saying "already
        # running" while nothing reaches go2rtc: stop it, then try once more.
        await self._call("stop_p2p_livestream", cam)
        return await self._call("start_p2p_livestream", cam, timeout=20) is not False

    async def stop(self) -> None:
        """Shutdown: never leave a battery camera streaming."""
        for cam in list(self._live):
            await self._call("stop_p2p_livestream", cam)
        self._live.clear()

    async def _call(self, service: str, name: str, timeout: float = 8) -> bool | None:
        """True when Home Assistant did it, False when it refused, None when
        it didn't answer in time."""
        entity = self._cfg.entities.get(name)
        if entity is None:
            logger.warning("cameras: no HA entity for %s", name)
            return False
        try:
            resp = await self._http.post(
                f"{self._cfg.ha_url}/api/services/eufy_security/{service}",
                json={"entity_id": entity},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("cameras: %s %s: no answer in %g s", service, name, timeout)
            return None
        except httpx.HTTPError as exc:
            logger.warning("cameras: %s %s failed: %s", service, name, exc)
            return False
        logger.info("cameras: %s %s", service, name)
        return True
