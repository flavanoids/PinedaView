# SPDX-License-Identifier: Apache-2.0
"""How a machine is doing: load, memory, disk, temperature, uptime.

Read straight from ``/proc`` and ``statvfs`` — a handful of tiny file reads,
cheap enough to take every minute on the Pi. The server reports its own; the
screen's Pi publishes its own over MQTT (``airplay_bridge``), and the menu's
Device page shows both.
"""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

_GB = 1024**3


class HostStats(BaseModel):
    load1: float
    load5: float
    load15: float
    cores: int
    mem_used_pct: float | None = None
    disk_free_gb: float
    disk_total_gb: float
    temp_c: float | None = None
    uptime_s: float | None = None
    at: datetime


def _meminfo() -> float | None:
    try:
        fields = {
            line.split(":")[0]: int(line.split()[1])
            for line in Path("/proc/meminfo").read_text().splitlines()
            if ":" in line
        }
        total, avail = fields["MemTotal"], fields["MemAvailable"]
    except (OSError, KeyError, ValueError, IndexError):
        return None
    return round(100 * (1 - avail / total), 1) if total else None


def _temp() -> float | None:
    try:
        return round(int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000, 1)
    except (OSError, ValueError):
        return None


def _uptime() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def local_stats(disk: Path = Path("/")) -> HostStats:
    load1, load5, load15 = os.getloadavg()
    usage = shutil.disk_usage(disk)
    return HostStats(
        load1=round(load1, 2),
        load5=round(load5, 2),
        load15=round(load15, 2),
        cores=os.cpu_count() or 1,
        mem_used_pct=_meminfo(),
        disk_free_gb=round(usage.free / _GB, 1),
        disk_total_gb=round(usage.total / _GB, 1),
        temp_c=_temp(),
        uptime_s=_uptime(),
        at=datetime.now(UTC),
    )
