#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -e

if command -v systemctl >/dev/null 2>&1; then
    systemctl stop pinedaview.service pineda-web.service 2>/dev/null || true
    systemctl disable pinedaview.service pineda-web.service 2>/dev/null || true
    systemctl disable --now pinedaview-guard.service pineda-web-guard.service 2>/dev/null || true
    systemctl disable --now pinedaview-update.timer 2>/dev/null || true
fi
