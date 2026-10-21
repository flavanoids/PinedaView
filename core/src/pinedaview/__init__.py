# SPDX-License-Identifier: Apache-2.0
"""PinedaDisplay Web — a self-hosted server that renders the PinedaDisplay
dashboard in any browser.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pineda-web")
except PackageNotFoundError:  # pragma: no cover - only when run from a bare tree
    __version__ = "0.0.0+unknown"
