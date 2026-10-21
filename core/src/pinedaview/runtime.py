# SPDX-License-Identifier: Apache-2.0
"""The live object graph for one server process."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from pinedaview.broadcast import Broadcaster
from pinedaview.cameras import CameraService
from pinedaview.cards import CardRegistry, build_providers
from pinedaview.config import Settings
from pinedaview.connections import load_connections
from pinedaview.google_oauth import PendingAuthStore
from pinedaview.household import HouseholdPrefs, load_household, save_household
from pinedaview.mqtt import MqttBridge
from pinedaview.now_showing import NowShowingStore
from pinedaview.photos import PhotoStore
from pinedaview.providers import Provider, Scheduler
from pinedaview.registry import Registry
from pinedaview.secrets import SecretStore
from pinedaview.state import StateController
from pinedaview.stores import StoreRegistry
from pinedaview.sun import SunScheduler
from pinedaview.takeover import ALARM_SECONDS, AlarmTakeover, TakeoverService
from pinedaview.timers import Timer, TimerService
from pinedaview.wallpaper import WallpaperStore

logger = logging.getLogger(__name__)


def _load_card_settings(settings: Settings, cards: CardRegistry) -> dict[str, dict[str, Any]]:
    defaults = {
        manifest.id: dict(manifest.setting_defaults())
        for manifest in cards.all()
        if manifest.settings
    }
    path = settings.state_dir / "card_settings.json"
    try:
        saved: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        saved = {}
    if isinstance(saved, dict):
        for card_id, values in saved.items():
            if isinstance(values, dict):
                defaults.setdefault(card_id, {}).update(values)
    return defaults


@dataclass
class Runtime:
    settings: Settings
    stores: StoreRegistry
    devices: Registry
    broadcaster: Broadcaster
    state: StateController
    timers: TimerService
    takeover: TakeoverService
    cameras: CameraService
    sun: SunScheduler
    secrets: SecretStore
    photos: PhotoStore
    wallpaper: WallpaperStore
    cards: CardRegistry
    http: httpx.AsyncClient
    card_settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    household: HouseholdPrefs = field(default_factory=HouseholdPrefs)
    provider_override: list[Provider] | None = None
    mqtt: MqttBridge | None = None
    on_playing: Callable[[bool], None] | None = None
    """Kept so a bridge rebuilt from Settings → Connect reports the same way."""
    oauth_pending: PendingAuthStore = field(default_factory=PendingAuthStore)
    now_showing: NowShowingStore = field(default_factory=NowShowingStore)
    online: dict[str, int] = field(default_factory=dict)
    """Open view streams per device id: a screen with one is on right now."""
    scheduler: Scheduler = field(init=False)

    def resolve_cards(self) -> None:
        self.cards.resolve(
            settings=self.settings,
            secrets=self.secrets,
            mqtt_connected=self.mqtt.connected if self.mqtt is not None else False,
            has_photos=self.photos.count() > 0,
        )
        self.scheduler.sync()

    def __post_init__(self) -> None:
        self.cards.resolve(
            settings=self.settings,
            secrets=self.secrets,
            has_photos=self.photos.count() > 0,
        )
        source = (
            self.provider_override
            if self.provider_override is not None
            else (lambda: build_providers(self.cards))
        )
        self.scheduler = Scheduler(
            self.settings,
            self.stores,
            source,
            secrets=self.secrets,
            card_settings=self.card_settings,
            client=self.http,
        )
        self.stores.on_change(lambda key: self.broadcaster.publish({"type": "store", "key": key}))
        if self.mqtt is not None:
            self.mqtt.on_ready = self.resolve_cards

    async def reconnect_mqtt(self) -> None:
        """Swap in a bridge for the broker ``settings.mqtt`` now names — or
        none, once it's turned off."""
        if self.mqtt is not None:
            await self.mqtt.stop()
            self.mqtt = None
        if self.settings.mqtt.enabled:
            self.mqtt = MqttBridge(
                self.settings.mqtt,
                self.stores,
                on_playing=self.on_playing,
                on_ready=self.resolve_cards,
            )
            await self.mqtt.start()
        self.resolve_cards()

    def save_household(self) -> None:
        save_household(self.settings, self.household)

    def save_card_settings(self) -> None:
        path = self.settings.state_dir / "card_settings.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.card_settings))
        except OSError as exc:
            logger.error("could not persist card settings: %s", exc)


def build_runtime(
    settings: Settings,
    *,
    cards: CardRegistry | None = None,
    providers: list[Provider] | None = None,
) -> Runtime:
    broadcaster = Broadcaster()
    household = load_household(settings)  # before anything reads settings
    load_connections(settings)
    secrets = SecretStore(settings.state_dir)
    registry = cards or CardRegistry.load(settings.cards_dir, set(settings.disabled_cards))
    photos = PhotoStore(settings.photos_dir)
    wallpaper = WallpaperStore(settings.state_dir)
    stores = StoreRegistry()
    state = StateController(settings.countdown)

    def _on_playing(playing: bool) -> None:
        state.playing = playing
        broadcaster.publish({"type": "state", "playing": playing})

    mqtt = (
        MqttBridge(settings.mqtt, stores, on_playing=_on_playing) if settings.mqtt.enabled else None
    )

    takeover = TakeoverService(broadcaster)

    def _ring(timer: Timer) -> None:
        if timer.kind in ("alarm", "reminder"):
            label = timer.label[:1].upper() + timer.label[1:]  # a reminder's "call mom"
            card = AlarmTakeover(kind="alarm", label=label, fires_at=timer.fires_at)
            takeover.show(card, ALARM_SECONDS)

    timers = TimerService(broadcaster, on_fire=_ring)
    http = httpx.AsyncClient(timeout=settings.providers.http_timeout_s)

    return Runtime(
        settings=settings,
        stores=stores,
        devices=Registry(settings.api.db_path),
        broadcaster=broadcaster,
        state=state,
        timers=timers,
        takeover=takeover,
        cameras=CameraService(settings.cameras, takeover, http),
        sun=SunScheduler(settings, stores, broadcaster),
        secrets=secrets,
        photos=photos,
        wallpaper=wallpaper,
        cards=registry,
        http=http,
        card_settings=_load_card_settings(settings, registry),
        household=household,
        provider_override=providers,
        mqtt=mqtt,
        on_playing=_on_playing,
    )
