#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# pinedaview-update.sh — Production update runner for PinedaView.
# Pulls updates from public GitHub repository, runs pre-flight safety checks,
# compiles web assets, restarts service, verifies health, and auto-rolls back on failure.
set -euo pipefail

# Configuration
if [ -n "${PINEDA_REPO_DIR:-}" ]; then
  REPO_DIR="$PINEDA_REPO_DIR"
else
  REPO_DIR="$(cd -- "$(dirname -- "$0")/.." && pwd)"
fi

cd "$REPO_DIR"

STATE_DIR="${PINEDA_STATE_DIR:-/var/lib/pinedaview}"
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || echo 'main')"
TARGET_BRANCH="${PINEDA_TARGET_BRANCH:-main}"
STATUS_FILE="${STATE_DIR}/update_status.json"
HEALTH_URL="${PINEDA_HEALTH_URL:-http://127.0.0.1:8090/api/health}"
MIN_FREE_KB="${PINEDA_MIN_FREE_KB:-512000}" # 500 MB minimum
PUBLIC_REPO_URL="https://github.com/flavanoids/PinedaView.git"

log() {
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] pinedaview-update: $*"
}

# Write status file atomically
write_status() {
  local state="$1"
  local step="${2:-}"
  local message="${3:-}"
  local err_code="${4:-}"
  local err_msg="${5:-}"
  local target_ver="${6:-}"
  local target_com="${7:-}"
  local now
  now="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

  mkdir -p "$STATE_DIR"
  local tmp_file="${STATUS_FILE}.tmp.$$"
  cat > "$tmp_file" <<JSON
{
  "state": "$state",
  "step": "$step",
  "message": "$message",
  "error_code": "$err_code",
  "error_message": "$err_msg",
  "current_version": "${CURRENT_VERSION:-unknown}",
  "current_commit": "${CURRENT_COMMIT:-unknown}",
  "target_version": "$target_ver",
  "target_commit": "$target_com",
  "last_checked_at": "$now",
  "updated_at": "$now"
}
JSON
  mv -f "$tmp_file" "$STATUS_FILE"
}

# Determine current version and commit
CURRENT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
CURRENT_VERSION="1.0.0"
if [ -f "core/pyproject.toml" ]; then
  CURRENT_VERSION="$(grep -m1 '^version' core/pyproject.toml | cut -d'"' -f2 2>/dev/null || echo '1.0.0')"
fi

# ==============================================================================
# 1. Pre-flight Safety Checks
# ==============================================================================
log "Starting pre-flight checks on branch '$TARGET_BRANCH'..."
write_status "checking" "preflight" "Running pre-flight checks..." "" "" "" ""

# Check 1: Disk space
FREE_KB=$(df -k "$REPO_DIR" | awk 'NR==2 {print $4}')
if [ "$FREE_KB" -lt "$MIN_FREE_KB" ]; then
  log "ERROR: Insufficient disk space ($FREE_KB KB free, need $MIN_FREE_KB KB)"
  write_status "failed" "preflight" "Storage low" "ERR_DISK_SPACE" "Device requires at least 500 MB free space to update" "" ""
  exit 1
fi

# Check 2: Internet / GitHub connectivity
if ! curl -sf --connect-timeout 6 -o /dev/null https://github.com 2>/dev/null; then
  log "ERROR: Cannot reach github.com"
  write_status "failed" "preflight" "No internet connection" "ERR_NETWORK_UNREACHABLE" "Could not connect to github.com" "" ""
  exit 1
fi

# Check 3: Public GitHub Repository Access
if ! git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
  log "WARNING: origin remote check failed, testing direct public repository..."
  if ! git ls-remote --exit-code "$PUBLIC_REPO_URL" HEAD >/dev/null 2>&1; then
    log "ERROR: Cannot reach public repository at $PUBLIC_REPO_URL"
    write_status "failed" "preflight" "Repository unreachable" "ERR_REPO_UNREACHABLE" "Could not reach public GitHub repository" "" ""
    exit 1
  fi
fi

# Check 4: Working tree cleanliness (only required when applying updates)
if [ "${1:-}" != "--check-only" ] && [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  log "ERROR: Working tree is dirty"
  write_status "failed" "preflight" "Local changes detected" "ERR_DIRTY_TREE" "Uncommitted local changes exist in repository. Stash or commit before updating." "" ""
  exit 1
fi

# ==============================================================================
# 2. Check for Updates
# ==============================================================================
log "Fetching updates from origin/$TARGET_BRANCH..."
git fetch origin "$TARGET_BRANCH" 2>/dev/null || git fetch "$PUBLIC_REPO_URL" "$TARGET_BRANCH"

REMOTE_COMMIT="$(git rev-parse --short "origin/$TARGET_BRANCH" 2>/dev/null || git rev-parse --short FETCH_HEAD 2>/dev/null || echo '')"
if [ -z "$REMOTE_COMMIT" ]; then
  log "ERROR: Remote branch '$TARGET_BRANCH' not found"
  write_status "failed" "fetch" "Branch not found" "ERR_BRANCH_NOT_FOUND" "Remote branch $TARGET_BRANCH could not be found" "" ""
  exit 1
fi

if [ "$CURRENT_COMMIT" = "$REMOTE_COMMIT" ]; then
  log "Already up to date at commit $CURRENT_COMMIT."
  write_status "idle" "done" "Display is up to date" "" "" "$CURRENT_VERSION" "$CURRENT_COMMIT"
  exit 0
fi

# If invoked with --check-only, stop here
if [ "${1:-}" = "--check-only" ]; then
  log "Update available: $CURRENT_COMMIT -> $REMOTE_COMMIT"
  write_status "idle" "available" "Update available ($REMOTE_COMMIT)" "" "" "$CURRENT_VERSION" "$REMOTE_COMMIT"
  exit 0
fi

# ==============================================================================
# 3. Apply Update
# ==============================================================================
ROLLBACK_COMMIT="$CURRENT_COMMIT"
log "Updating from $ROLLBACK_COMMIT to $REMOTE_COMMIT..."
write_status "updating" "fetching" "Downloading update..." "" "" "" "$REMOTE_COMMIT"

# Switch and reset working tree to target commit
git checkout -B "$TARGET_BRANCH" "origin/$TARGET_BRANCH" 2>/dev/null || git reset --hard FETCH_HEAD

TARGET_VERSION="$CURRENT_VERSION"
if [ -f "core/pyproject.toml" ]; then
  TARGET_VERSION="$(grep -m1 '^version' core/pyproject.toml | cut -d'"' -f2 2>/dev/null || echo "$CURRENT_VERSION")"
fi

# ==============================================================================
# 4. Compile Web Assets
# ==============================================================================
log "Building web client..."
write_status "updating" "building_web" "Compiling display assets..." "" "" "$TARGET_VERSION" "$REMOTE_COMMIT"

build_ok=1
cd "$REPO_DIR/web"
if command -v pnpm >/dev/null 2>&1; then
  pnpm run build || build_ok=0
elif command -v corepack >/dev/null 2>&1; then
  corepack pnpm run build || build_ok=0
else
  npm run build || build_ok=0
fi

if [ "$build_ok" -ne 1 ]; then
  log "ERROR: Web build failed. Rolling back to $ROLLBACK_COMMIT..."
  cd "$REPO_DIR"
  git reset --hard "$ROLLBACK_COMMIT"
  write_status "failed" "building_web" "Build failed" "ERR_BUILD_FAILED" "Display assets failed to compile. Reverted to previous stable version." "$CURRENT_VERSION" "$ROLLBACK_COMMIT"
  exit 1
fi

# Stage webroot into python package
cd "$REPO_DIR"
dest="core/src/pinedaview/webroot"
rm -rf "$dest"
cp -r web/dist "$dest"

# Update package in /opt/pinedaview if installed
if [ -d /opt/pinedaview/venv ]; then
  for p in /opt/pinedaview/venv/lib/python*/site-packages/pinedaview; do
    if [ -d "$p" ]; then
      log "Updating package files in $p"
      cp -r core/src/pinedaview/* "$p/" 2>/dev/null || true
    fi
  done
fi

# ==============================================================================
# 5. Service Restart & Health Verification
# ==============================================================================
log "Restarting pinedaview.service..."
write_status "updating" "restarting" "Restarting display service..." "" "" "$TARGET_VERSION" "$REMOTE_COMMIT"

SVC_NAME="pinedaview.service"
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet pinedaview.service 2>/dev/null; then
    systemctl restart pinedaview.service || true
  elif systemctl is-active --quiet pineda-web.service 2>/dev/null; then
    SVC_NAME="pineda-web.service"
    systemctl restart pineda-web.service || true
  fi
fi

# Verify health
log "Verifying server health at $HEALTH_URL..."
healthy=0
for i in $(seq 1 30); do
  if curl -sf -m 2 "$HEALTH_URL" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done

if [ "$healthy" -eq 1 ]; then
  log "Update successful! New version: $TARGET_VERSION ($REMOTE_COMMIT)"
  write_status "success" "done" "Updated successfully" "" "" "$TARGET_VERSION" "$REMOTE_COMMIT"

  # Trigger kiosk reload if kiosk service or script is available
  if [ -f "$REPO_DIR/scripts/reload-kiosk.sh" ]; then
    bash "$REPO_DIR/scripts/reload-kiosk.sh" 2>/dev/null || true
  elif command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet pinedaview-kiosk.service 2>/dev/null; then
    systemctl restart pinedaview-kiosk.service 2>/dev/null || true
  fi
  exit 0
else
  log "ERROR: Health check failed after update. Rolling back to $ROLLBACK_COMMIT..."
  git reset --hard "$ROLLBACK_COMMIT"

  # Re-build previous webroot
  cd "$REPO_DIR/web"
  if command -v pnpm >/dev/null 2>&1; then
    pnpm run build || true
  elif command -v corepack >/dev/null 2>&1; then
    corepack pnpm run build || true
  fi
  cd "$REPO_DIR"
  rm -rf "$dest"
  cp -r web/dist "$dest" 2>/dev/null || true

  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$SVC_NAME" 2>/dev/null; then
    systemctl restart "$SVC_NAME" || true
  fi

  write_status "failed" "restarting" "Server failed to start" "ERR_HEALTHCHECK_TIMEOUT" "Server startup health check failed. Reverted to previous release." "$CURRENT_VERSION" "$ROLLBACK_COMMIT"
  exit 1
fi
