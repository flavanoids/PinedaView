# AI Agent Guidelines & Documentation Maintenance Rules

This file defines mandatory rules and protocols for all AI coding assistants (including Antigravity, Claude, Gemini, Cursor, Copilot, etc.) working on the `PinedaDisplay_Web` repository.

---

## 1. Golden Rule: Documentation Must Match Codebase

Whenever you modify any code in this repository, you **MUST** update the associated documentation in the same commit / response. Do not leave documentation updates as a follow-up task or assume another contributor will update them.

### Codebase-to-Documentation Mapping Matrix

When you modify files matching a pattern in the left column, you must verify and update the corresponding documentation files in the right column:

| Modified Codebase Paths | Mandatory Documentation Updates |
|---|---|
| `core/src/pinedaview/api.py`, routes, or endpoints | - [`docs/API.md`](docs/API.md) (update endpoint tables, request/response descriptions)<br>- [`packages/protocol/openapi.json`](packages/protocol/openapi.json) (regenerate schema if routes/models change)<br>- [`CHANGELOG.md`](CHANGELOG.md) (record under `[Unreleased]`) |
| `core/src/pinedaview/config.py` (settings, defaults) | - [`core/config.example.toml`](core/config.example.toml) (add/update commented or default options)<br>- [`docs/INSTALL.md`](docs/INSTALL.md) (update Configuration Reference table)<br>- [`README.md`](README.md) (if default theme or core parameters change)<br>- [`CHANGELOG.md`](CHANGELOG.md) |
| `core/src/pinedaview/cards/`, `core/src/pinedaview/providers/`, `web/src/cards/` | - [`README.md`](README.md) (keep `### Built-in cards` list accurate)<br>- [`docs/CARD_MANIFEST.md`](docs/CARD_MANIFEST.md) (if manifest schema, needs, or `disabled_cards` change)<br>- [`docs/CARD_SDK.md`](docs/CARD_SDK.md) (if provider interface or SDK patterns change)<br>- [`cards/README.md`](cards/README.md)<br>- [`core/README.md`](core/README.md) (stores list)<br>- [`CHANGELOG.md`](CHANGELOG.md) |
| `core/src/pinedaview/stores.py` (stores, caching, data retention) | - [`core/README.md`](core/README.md) (update stores list)<br>- [`docs/API.md`](docs/API.md) (store ingestion & debugging endpoints)<br>- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) (metrics & store health checks) |
| `core/src/pinedaview/themes.py` (palettes, surfaces) | - [`core/config.example.toml`](core/config.example.toml) (list valid theme choices)<br>- [`README.md`](README.md)<br>- [`CHANGELOG.md`](CHANGELOG.md) |
| `web/src/lib/`, `web/src/components/`, `web/src/layouts/` | - [`web/README.md`](web/README.md) (update `## Layout of the source` table)<br>- [`docs/ACCESSIBILITY.md`](docs/ACCESSIBILITY.md) (if keyboard, modal, or contrast behavior changes)<br>- [`CHANGELOG.md`](CHANGELOG.md) |
| `packaging/`, `scripts/` (systemd units, failover, install scripts) | - [`docs/INSTALL.md`](docs/INSTALL.md) (installation instructions & units)<br>- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) (production ops, kiosk controls, failover setup)<br>- [`CHANGELOG.md`](CHANGELOG.md) |
| Security, auth gates (`api.write_token`, `api.admin_token`, secrets) | - [`SECURITY.md`](SECURITY.md) (threat model & token access rules)<br>- [`docs/API.md`](docs/API.md) (auth headers & endpoint protections) |
| Architectural choices, trade-offs, card retirement, dependencies | - [`docs/DECISIONS.md`](docs/DECISIONS.md) (add a new ADR: `## NNNN — Title · Date · Status`)<br>- [`CHANGELOG.md`](CHANGELOG.md) |
| Any user-facing feature, bug fix, or breaking change | - [`CHANGELOG.md`](CHANGELOG.md) (add an entry under `## [Unreleased]`) |

---

## 2. Standing Quality Bar

Before completing any task, ensure that the standing quality gate passes:
- **SPDX Headers:** All source files (`.py`, `.ts`, `.svelte`, `.mjs`) must include `# SPDX-License-Identifier: Apache-2.0` or `// SPDX-License-Identifier: Apache-2.0`. Verify with `pnpm run check:spdx`.
- **Python Quality Gate:**
  ```bash
  cd core && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
  ```
- **Web Quality Gate:**
  ```bash
  cd web && pnpm exec eslint . && pnpm exec prettier --check . && pnpm exec svelte-check && pnpm exec vitest run
  ```
- **Aggregate Check:**
  ```bash
  pnpm -w run check
  ```

---

## 3. Commit Convention & Attribution

- Follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `build:`, `ci:`.
- Commit messages must include co-authorship attribution:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
