#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# test-update-pipeline.sh — Diagnostic and verification tool for the PinedaView update pipeline.
set -euo pipefail

root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$root"

echo "=========================================================="
echo "      PinedaView Update Pipeline Diagnostics"
echo "=========================================================="

# 1. Local and Remote Git Status
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || echo 'unknown')"
CURRENT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "[1/5] Git Branch: $CURRENT_BRANCH @ $CURRENT_COMMIT"

# 2. Check GitHub reachability
echo -n "[2/5] GitHub Public Repository: "
if git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
  echo "OK (remote 'origin' reachable)"
elif git ls-remote --exit-code "https://github.com/flavanoids/PinedaView.git" HEAD >/dev/null 2>&1; then
  echo "OK (public repo reachable)"
else
  echo "FAILED (network or repository error)"
fi

# Compare against origin/main
REMOTE_MAIN="$(git ls-remote origin refs/heads/main 2>/dev/null | cut -c1-7 || git ls-remote https://github.com/flavanoids/PinedaView.git refs/heads/main 2>/dev/null | cut -c1-7 || echo 'unknown')"
echo "      origin/main latest commit: $REMOTE_MAIN"

# 3. Check Systemd Units
echo -n "[3/5] Systemd Service & Timer: "
timer_status="$(systemctl is-active pinedaview-update.timer 2>/dev/null || systemctl is-active pineda-update.timer 2>/dev/null || echo 'inactive')"
svc_status="$(systemctl is-active pinedaview.service 2>/dev/null || systemctl is-active pineda-web.service 2>/dev/null || echo 'inactive')"
echo "Timer is '$timer_status', Server is '$svc_status'"

# 4. Check Kiosk Reachability
echo -n "[4/5] Kiosk Target: "
kiosk_host="${PINEDA_KIOSK_HOST:-}"
if [ -z "$kiosk_host" ] && [ -f "config.toml" ]; then
  kiosk_host="$(grep -E '^[[:space:]]*host[[:space:]]*=' config.toml | cut -d'"' -f2 2>/dev/null || echo '')"
fi

if [ -n "$kiosk_host" ]; then
  if ping -c 1 -W 2 "$kiosk_host" >/dev/null 2>&1; then
    echo "Host '$kiosk_host' is online"
  else
    echo "Host '$kiosk_host' unreachable or ping filtered"
  fi
else
  echo "Local / standalone mode (no external kiosk host configured)"
fi

# 5. Live Update API Status
echo -n "[5/5] Current Update Status API: "
update_json="$(curl -sf --connect-timeout 2 http://127.0.0.1:8090/api/system/update 2>/dev/null || echo '')"
if [ -n "$update_json" ]; then
  state="$(echo "$update_json" | grep -o '"state":"[^"]*"' | cut -d'"' -f4 || echo 'unknown')"
  msg="$(echo "$update_json" | grep -o '"message":"[^"]*"' | cut -d'"' -f4 || echo '')"
  echo "state='$state' ($msg)"
else
  echo "unavailable (server not responding on :8090)"
fi

echo "=========================================================="

runner="/usr/local/bin/pinedaview-update"
[ -f "$runner" ] || runner="$root/scripts/pinedaview-update.sh"

if [ "${1:-}" = "--run" ]; then
  echo "Triggering immediate update test..."
  sudo "$runner"
elif [ "${1:-}" = "--check-only" ]; then
  echo "Running pre-flight check only..."
  sudo "$runner" --check-only
else
  echo "To test the runner directly, run: $0 --check-only"
  echo "To execute a full update cycle, run: $0 --run"
fi
