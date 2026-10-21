# SPDX-License-Identifier: Apache-2.0
"""Package-level smoke checks."""

from pinedaview import __version__


def test_version_is_a_semver_string() -> None:
    major, minor, *_ = __version__.split(".")
    assert major.isdigit() and minor.isdigit()
