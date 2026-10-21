#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Keep the standby pineda-web's state the same as the primary's, both ways.
# Run on the primary every minute (packaging/pineda-standby-sync.timer):
#   sync-standby.sh /var/lib/pineda-web root@192.0.2.16
#
# - Primary up: push its state (photos with their metadata and display
#   copies, themes, custom themes, card settings, layouts, keys, the
#   database) to the standby, and restart the standby's pineda-web when
#   anything that matters changed. It loads most of this at startup, and a
#   database swapped under a running server isn't seen.
# - Something was saved on the standby (it touches standby-changed, see
#   pinedaview.standby): pull its state here first and restart this
#   pineda-web, so changes made during an outage carry over instead of being
#   overwritten. A pull that would delete more than $MAX_DELETES files is
#   refused and logged, not done.
# - Primary down: nothing. The standby may be serving; its changes come back
#   on the first run after the primary returns.
#
# Also copies Antigua's camera snapshots (PINEDA_CAMS_DIR) so the standby's
# home-cams card has the latest photos.
set -eu

state="${1:?usage: $0 <primary state dir> <user@standby> [standby state dir]}"
standby="${2:?usage: $0 <primary state dir> <user@standby> [standby state dir]}"
dest="${3:-/var/lib/pineda-web}"
owner="${PINEDA_STANDBY_OWNER:-pineda:pineda}"
local_url="${PINEDA_LOCAL_URL:-http://127.0.0.1:8090}"
cams="${PINEDA_CAMS_DIR:-}"
work="${PINEDA_SYNC_DIR:-/var/lib/pineda-standby-sync}"
MAX_DELETES="${PINEDA_MAX_DELETES:-25}"
flag=standby-changed

mkdir -p "$work"
exec 9>"$work/lock"
flock -n 9 || exit 0   # the last run is still going

log() { echo "sync-standby: $*"; }
on_standby() { ssh -o BatchMode=yes -o ConnectTimeout=5 "$standby" "$@"; }

# A consistent copy of a live database, and a digest of what's in it minus
# the screen's last_seen (it changes every few seconds and isn't state).
snapshot_py='import sqlite3, sys; s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close()'
digest() {
    python3 - "$1" <<'PY'
import hashlib, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
h = hashlib.sha256()
for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    cols = [c[1] for c in db.execute(f"PRAGMA table_info({table})") if c[1] != "last_seen"]
    for row in db.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY rowid"):
        h.update(repr(row).encode())
print(h.hexdigest())
PY
}
# mcp_audit.db is each server's own record of the MCP calls it served, and it
# changes on every call: copying it restarted the standby every minute.
excludes="--exclude connections.json --exclude pineda.db --exclude pineda.db-wal --exclude pineda.db-shm --exclude mcp_audit.db --exclude mcp_audit.db-wal --exclude mcp_audit.db-shm --exclude $flag --exclude $flag.syncing"

snap="$(mktemp -d)"
trap 'rm -rf "$snap"' EXIT

# ── pull: changes saved on the standby come back first ──────────────────
if on_standby "test -e $dest/$flag"; then
    log "the standby has changes; pulling them back"
    on_standby "mv $dest/$flag $dest/$flag.syncing"
    # shellcheck disable=SC2086
    deletes=$(rsync -an --delete --itemize-changes $excludes "$standby:$dest/" "$state/" \
        | grep -c '^\*deleting' || true)
    if [ "$deletes" -gt "$MAX_DELETES" ]; then
        log "REFUSED: pulling would delete $deletes files here (limit $MAX_DELETES). Check the standby."
        on_standby "mv $dest/$flag.syncing $dest/$flag"
        exit 1
    fi
    on_standby "python3 -c '$snapshot_py' $dest/pineda.db /tmp/pineda-pull.db"
    rsync -a "$standby:/tmp/pineda-pull.db" "$snap/pineda.db"
    on_standby "rm -f /tmp/pineda-pull.db"
    systemctl stop pineda-web
    # shellcheck disable=SC2086
    rsync -a --delete --chown="$owner" $excludes "$standby:$dest/" "$state/"
    install -o "${owner%%:*}" -g "${owner##*:}" -m 644 "$snap/pineda.db" "$state/pineda.db"
    rm -f "$state/pineda.db-wal" "$state/pineda.db-shm"
    systemctl start pineda-web
    on_standby "rm -f $dest/$flag.syncing"
    digest "$state/pineda.db" > "$work/db.digest"
    log "pulled ($deletes deleted here); this pineda-web restarted"
    exit 0
fi

# ── push: only while this box is the one serving ────────────────────────
if ! curl -sf -m 3 -o /dev/null "$local_url/api/health"; then
    log "pineda-web here isn't answering; leaving the standby alone"
    exit 0
fi

if [ -n "$cams" ] && [ -d "$cams" ]; then
    on_standby "mkdir -p $cams"
    rsync -a --chmod=D755,F644 "$cams/" "$standby:$cams/"
fi

# shellcheck disable=SC2086
changed=$(rsync -a --delete --chown="$owner" --itemize-changes $excludes "$state/" "$standby:$dest/" \
    | grep -v -e ' affirmation_history.json$' -e '^\.d' || true)

python3 -c "$snapshot_py" "$state/pineda.db" "$snap/pineda.db"
new_digest=$(digest "$snap/pineda.db")
old_digest=$(cat "$work/db.digest" 2>/dev/null || true)

if [ "$new_digest" != "$old_digest" ]; then
    rsync -a --chown="$owner" "$snap/pineda.db" "$standby:/tmp/pineda-push.db"
    on_standby "systemctl stop pineda-web && install -o ${owner%%:*} -g ${owner##*:} -m 644 \
        /tmp/pineda-push.db $dest/pineda.db && rm -f /tmp/pineda-push.db $dest/pineda.db-wal \
        $dest/pineda.db-shm && systemctl start pineda-web"
    echo "$new_digest" > "$work/db.digest"
    log "pushed the database${changed:+ and files}; standby restarted"
elif [ -n "$changed" ]; then
    on_standby "systemctl restart pineda-web"
    log "pushed files; standby restarted: $(echo "$changed" | wc -l) change(s)"
fi
