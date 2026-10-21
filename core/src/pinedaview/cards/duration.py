# SPDX-License-Identifier: Apache-2.0
"""Parse the ``"15m"`` / ``"90s"`` / ``"1h"`` duration strings the manifest uses."""

from __future__ import annotations

import re

_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)\s*$")
_UNIT_SECONDS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}


def parse_duration(value: str) -> float:
    match = _PATTERN.match(value)
    if match is None:
        raise ValueError(f"not a duration: {value!r} (want e.g. '15m', '90s')")
    return float(match.group(1)) * _UNIT_SECONDS[match.group(2)]
