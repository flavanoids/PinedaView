# SPDX-License-Identifier: Apache-2.0
"""Turn ready cards into running providers.

A manifest's ``provider`` is either a built-in key or a ``"module.path:Class"``
import. One provider instance per ready card that declares one; its refresh
cadence comes from the manifest.
"""

from __future__ import annotations

import importlib
import logging

from pinedaview.cards.registry import CardRegistry
from pinedaview.providers.air_quality import AirQualityProvider
from pinedaview.providers.alerts import AlertsProvider
from pinedaview.providers.base import Provider
from pinedaview.providers.calendar import CalendarProvider
from pinedaview.providers.commute import CommuteProvider
from pinedaview.providers.daily import DailyContentProvider
from pinedaview.providers.home_cams import HomeCamsProvider
from pinedaview.providers.indoor_climate import IndoorClimateProvider
from pinedaview.providers.moon import MoonProvider
from pinedaview.providers.news import NewsProvider
from pinedaview.providers.on_this_day import OnThisDayProvider
from pinedaview.providers.radar import RadarProvider
from pinedaview.providers.traffic_cams import TrafficCamsProvider
from pinedaview.providers.weather import WeatherProvider

logger = logging.getLogger(__name__)

_BUILTIN: dict[str, type[Provider]] = {
    "weather": WeatherProvider,
    "airQuality": AirQualityProvider,
    "alerts": AlertsProvider,
    "moon": MoonProvider,
    "dailyContent": DailyContentProvider,
    "commute": CommuteProvider,
    "radar": RadarProvider,
    "indoorClimate": IndoorClimateProvider,
    "calendar": CalendarProvider,
    "onThisDay": OnThisDayProvider,
    "trafficCams": TrafficCamsProvider,
    "homeCams": HomeCamsProvider,
    "news": NewsProvider,
}


def _load_provider_class(spec: str) -> type[Provider]:
    if ":" in spec:
        module_name, _, class_name = spec.partition(":")
        module = importlib.import_module(module_name)
        obj = getattr(module, class_name)
        if not (isinstance(obj, type) and issubclass(obj, Provider)):
            raise TypeError(f"{spec} is not a Provider subclass")
        return obj
    if spec in _BUILTIN:
        return _BUILTIN[spec]
    raise KeyError(spec)


def build_providers(registry: CardRegistry) -> list[Provider]:
    providers: list[Provider] = []
    for card_id in registry.ready_ids():
        manifest = registry.manifest(card_id)
        if manifest is None or manifest.provider is None:
            continue
        try:
            provider_cls = _load_provider_class(manifest.provider)
        except (KeyError, ImportError, AttributeError, TypeError) as exc:
            logger.error("card %s: provider %r unavailable (%s)", card_id, manifest.provider, exc)
            continue
        providers.append(provider_cls(interval_s=manifest.refresh.interval_s))
    return providers
