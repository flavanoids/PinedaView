#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -e

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
fi
# The user's photos, config and database in /var/lib/pineda-web and
# /etc/pineda-web are left in place on purpose. Remove them by hand to purge.
