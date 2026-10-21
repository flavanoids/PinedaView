# Documentation Synchronization & Maintenance Rule

## Purpose
Enforces that documentation across the `PinedaDisplay_Web` repository always remains strictly aligned with the codebase.

## Trigger & Scope
Always active whenever code or configuration files in the workspace are modified, added, removed, or refactored.

## Requirements
Whenever a commit or code modification touches a codebase component, you **MUST** update the corresponding documentation files in the same turn:

1. **API Endpoints (`core/src/pinedaview/api.py`)**
   - Update [`docs/API.md`](../../docs/API.md) with new/updated routes, methods, request bodies, and responses.
   - Regenerate OpenAPI schema in [`packages/protocol/openapi.json`](../../packages/protocol/openapi.json) and compile TypeScript client.
   - Record in [`CHANGELOG.md`](../../CHANGELOG.md) under `[Unreleased]`.

2. **Configuration & Defaults (`core/src/pinedaview/config.py`)**
   - Update [`docs/INSTALL.md`](../../docs/INSTALL.md) Configuration Reference table.
   - Update [`core/config.example.toml`](../../core/config.example.toml) with commented or active settings.
   - Update [`README.md`](../../README.md) if defaults change.

3. **Cards & Providers (`core/src/pinedaview/cards/`, `providers/`, `web/src/cards/`)**
   - Update [`README.md`](../../README.md) (`### Built-in cards` list).
   - Update [`docs/CARD_MANIFEST.md`](../../docs/CARD_MANIFEST.md) if manifest requirements or `disabled_cards` change.
   - Update [`docs/CARD_SDK.md`](../../docs/CARD_SDK.md), [`cards/README.md`](../../cards/README.md), and [`core/README.md`](../../core/README.md).

4. **Data Stores (`core/src/pinedaview/stores.py`)**
   - Update [`core/README.md`](../../core/README.md) stores list.
   - Update [`docs/API.md`](../../docs/API.md) store ingestion and debug route documentation.

5. **Themes & Appearance (`core/src/pinedaview/themes.py`)**
   - Update [`core/config.example.toml`](../../core/config.example.toml) and [`README.md`](../../README.md).

6. **Web Client Architecture (`web/src/`)**
   - Update [`web/README.md`](../../web/README.md) source layout table.
   - Update [`docs/ACCESSIBILITY.md`](../../docs/ACCESSIBILITY.md) if UI interactions or accessibility modes change.

7. **Packaging & Deployment Scripts (`packaging/`, `scripts/`)**
   - Update [`docs/INSTALL.md`](../../docs/INSTALL.md) and [`docs/OPERATIONS.md`](../../docs/OPERATIONS.md).

8. **Architecture Decisions & Deprecations**
   - Record an Architecture Decision Record (ADR) in [`docs/DECISIONS.md`](../../docs/DECISIONS.md).

9. **Security & Permissions**
   - Update [`SECURITY.md`](../../SECURITY.md) and [`docs/API.md`](../../docs/API.md).
