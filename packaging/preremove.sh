#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -e

if command -v systemctl >/dev/null 2>&1; then
    systemctl stop pineda-web.service || true
    systemctl disable pineda-web.service || true
    systemctl disable --now pineda-web-guard.service || true
fi
