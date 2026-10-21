#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -e

if ! getent passwd pineda >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/pineda-web --shell /usr/sbin/nologin \
        --comment "PinedaDisplay Web" pineda || \
    adduser --system --home /var/lib/pineda-web --no-create-home pineda || true
fi

mkdir -p /var/lib/pineda-web/photos /var/lib/pineda-web/cards
chown -R pineda:pineda /var/lib/pineda-web
chmod 750 /var/lib/pineda-web

# Lets the "Restart display" / "Restart Raspberry Pi" menu buttons work: the
# pineda user runs NoNewPrivileges=true, so it can only reach systemctl/reboot
# via this polkit rule, never sudo. Harmless on setups without a kiosk unit —
# the rule only matches pineda-kiosk.service and the reboot action.
if [ -d /etc/polkit-1/rules.d ]; then
    install -m 644 /opt/pineda-web/pineda-restart.rules \
        /etc/polkit-1/rules.d/49-pineda-web.rules 2>/dev/null || true
    systemctl try-restart polkit 2>/dev/null || true
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl enable pineda-web.service || true
    # LAN only: the guard keeps :8090 off the internet and away from tunnels
    # (docs/OPERATIONS.md#keeping-it-on-the-lan).
    systemctl enable --now pineda-web-guard.service || true
    echo "PinedaDisplay Web installed. Start it with:  systemctl start pineda-web"
    echo "Then open http://<this-host>:8090 to run the setup wizard."
fi
