#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Kiosk-side failover between a primary and a standby pineda-web — runs on the
# kiosk device next to nginx (packaging/pineda-failover.nginx.conf), which the
# kiosk's Chromium loads from localhost. Polls the primary's /api/health and
# points nginx's upstream at whichever server should be live, the same way
# Antigua's fallback watches its primary: down after DOWN_AFTER misses, back
# after UP_AFTER hits, so one slow poll doesn't bounce the screen.
#
# A reload cuts the open SSE stream (worker_shutdown_timeout), the client
# reconnects through the proxy and lands on the new server with the same
# origin, so its cached view and device id (?device=) carry over.
set -u

PRIMARY="${PINEDA_PRIMARY:?set PINEDA_PRIMARY=host:port}"
STANDBY="${PINEDA_STANDBY:?set PINEDA_STANDBY=host:port}"
UPSTREAM="${PINEDA_UPSTREAM_FILE:-/etc/nginx/pineda-upstream.conf}"
POLL_S="${PINEDA_POLL_S:-5}"
DOWN_AFTER="${PINEDA_DOWN_AFTER:-2}"
UP_AFTER="${PINEDA_UP_AFTER:-3}"

healthy() { curl -sf -m 3 -o /dev/null "http://$1/api/health"; }

# The live server first; the other as nginx's backup, so a request that hits
# a dead live server between polls still gets an answer.
point_at() {
    printf '# Written by pineda-failover — do not edit.\nserver %s max_fails=1 fail_timeout=10s;\nserver %s backup;\n' \
        "$1" "$2" > "$UPSTREAM.tmp" && mv "$UPSTREAM.tmp" "$UPSTREAM"
    nginx -s reload 2>/dev/null || true
    echo "pineda-failover: serving from $1"
}

if healthy "$PRIMARY"; then live=primary; point_at "$PRIMARY" "$STANDBY"
else live=standby; point_at "$STANDBY" "$PRIMARY"; fi

misses=0 hits=0
while sleep "$POLL_S"; do
    if healthy "$PRIMARY"; then misses=0 hits=$((hits + 1)); else hits=0 misses=$((misses + 1)); fi
    if [ "$live" = primary ] && [ "$misses" -ge "$DOWN_AFTER" ]; then
        if healthy "$STANDBY"; then
            live=standby; point_at "$STANDBY" "$PRIMARY"
        fi
    elif [ "$live" = standby ] && [ "$hits" -ge "$UP_AFTER" ]; then
        live=primary; point_at "$PRIMARY" "$STANDBY"
    fi
done
