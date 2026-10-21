#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Scaffold a new card folder under cards/.
#   scripts/new-card.sh <card-id> ["Card Name"]
set -euo pipefail

id="${1:-}"
name="${2:-${id}}"
if [[ -z "$id" || ! "$id" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo "usage: scripts/new-card.sh <card-id> [\"Card Name\"]   (id: kebab-case)" >&2
  exit 2
fi

dir="cards/$id"
[[ -e "$dir" ]] && { echo "$dir already exists" >&2; exit 1; }
mkdir -p "$dir"

cat > "$dir/card.json" <<EOF
{
  "id": "$id",
  "name": "$name",
  "version": "0.1.0",
  "description": "",
  "author": "you",
  "needs": [],
  "provides": [],
  "slots": { "min": "small", "ideal": "medium", "max": "hero" },
  "tier": { "min": "lite" }
}
EOF

cat > "$dir/README.md" <<EOF
# $name

Edit \`card.json\`. Add \`"needs"\` (\`location\`, \`network\`, \`secret:<key>\`,
\`photos\`, \`mqtt:<topic>\`, \`provider:<store>\`) — unmet ones grey the card in
the picker instead of crashing it.

- Fetches its own data? Add \`"provider": "your.module:Provider"\` and a
  \`provider.py\` with an \`async def poll(self, ctx)\`.
- Needs a bespoke view? Add a Svelte component to \`web/src/cards/\` and register
  it in \`web/src/cards/index.ts\`. Without one, the Generic fallback renders the
  card's name and store data.

Run \`pineda-web dev\` and the manifest hot-reloads.
See docs/CARD_MANIFEST.md and docs/CARD_SDK.md.
EOF

echo "created $dir"
echo "  restart the server (or run 'pineda-web dev') to pick it up"
