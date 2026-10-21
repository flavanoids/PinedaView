# SPDX-License-Identifier: Apache-2.0
"""Data providers and the scheduler that runs them."""

from __future__ import annotations

from pinedaview.providers.air_quality import AirQualityProvider
from pinedaview.providers.alerts import AlertsProvider
from pinedaview.providers.base import Provider, ProviderContext, ProviderError
from pinedaview.providers.daily import DailyContentProvider
from pinedaview.providers.moon import MoonProvider
from pinedaview.providers.scheduler import Scheduler
from pinedaview.providers.weather import WeatherProvider

__all__ = [
    "AirQualityProvider",
    "AlertsProvider",
    "DailyContentProvider",
    "MoonProvider",
    "Provider",
    "ProviderContext",
    "ProviderError",
    "Scheduler",
    "WeatherProvider",
    "default_providers",
]


def default_providers() -> list[Provider]:
    """The providers a stock server runs. Order is cosmetic — the scheduler
    runs them concurrently; air quality and alerts defer until weather has
    resolved coordinates."""
    return [
        WeatherProvider(),
        AirQualityProvider(),
        AlertsProvider(),
        MoonProvider(),
        DailyContentProvider(),
    ]
