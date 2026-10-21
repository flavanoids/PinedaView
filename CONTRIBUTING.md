# Contributing

This project is built in phases (see [`docs/ROADMAP.md`](docs/ROADMAP.md)). Every
phase ships clean, typed, tested code. There is no "we'll tidy it later" — the
gate below is the definition of done for every task.

## The standing quality gate

No task is complete, and no phase closes, until **all** of this is green in CI on
the phase branch:

### Python (`core/`, `packages/*` that are Python)

| Check | Command | Bar |
|---|---|---|
| Lint | `ruff check .` | zero findings |
| Format | `ruff format --check .` | clean |
| Types | `mypy --strict .` | zero errors |
| Tests | `pytest` | green; **≥ 85 % line coverage** on `core/` |
| Complexity | ruff `C90` | max-complexity **10** |

Ruff rule set: `E W F B C90 SIM UP ARG RUF I PTH RET TID`. Line length 100.
Content files with translated text may be `E501`-exempt, following the base
project's precedent — nothing else.

### Web (`web/`, `packages/*` that are TS)

| Check | Command | Bar |
|---|---|---|
| Lint | `eslint .` | zero findings |
| Format | `prettier --check .` | clean |
| Types | `svelte-check` + `tsc --noEmit` | zero errors |
| Tests | `vitest run` | green |
| Bundle budget | `size-limit` | initial JS ≤ **100 KB** gzipped on the critical path |

### Everything

- `pnpm -w run check` runs the whole gate locally. Do not push without it passing.
- Pre-commit hooks run the fast subset (lint + format + types). CI runs the full
  gate on every push and blocks merge to `main`.
- No new dependency without a line in `docs/DECISIONS.md` saying why.
- Public API and `card.json` schema changes require an updated OpenAPI/JSON-Schema
  file **in the same commit** — the generated TypeScript client must still compile.

### Documentation synchronization (Hard rule for humans & AI coders)

Documentation must never drift from the codebase. Whenever any commit or PR
modifies a part of the codebase, the author (human or AI coder) **must** update
the corresponding documentation files in the same commit:

| If you modify code in... | You must update / verify... |
|---|---|
| `core/src/pinedaview/api.py`, routes, or endpoints | `docs/API.md`, `packages/protocol/openapi.json`, `packages/protocol/src/client.ts`, `CHANGELOG.md` |
| `core/src/pinedaview/config.py` (settings, defaults) | `docs/INSTALL.md` (config table), `core/config.example.toml`, `README.md`, `CHANGELOG.md` |
| `core/src/pinedaview/cards/`, `providers/`, `web/src/cards/` | `README.md` (card list), `docs/CARD_MANIFEST.md`, `docs/CARD_SDK.md`, `cards/README.md`, `core/README.md`, `CHANGELOG.md` |
| `core/src/pinedaview/stores.py` (stores, caching, retention) | `core/README.md` (stores list), `docs/API.md`, `docs/OPERATIONS.md` |
| `core/src/pinedaview/themes.py` (palettes, surfaces) | `core/config.example.toml`, `README.md`, `CHANGELOG.md` |
| `web/src/lib/`, `web/src/components/`, `web/src/layouts/` | `web/README.md` (source layout), `docs/ACCESSIBILITY.md`, `CHANGELOG.md` |
| `packaging/`, `scripts/` (systemd, failover, installs, wrappers) | `docs/INSTALL.md`, `docs/OPERATIONS.md`, `CHANGELOG.md` |
| Security, tokens, auth gates (`api.write_token`, `api.admin_token`) | `SECURITY.md`, `docs/API.md` |
| Architecture decisions, major refactors, component retirements | `docs/DECISIONS.md` (new ADR), `CHANGELOG.md` |
| Any user-facing fix, feature, or breaking change | `CHANGELOG.md` (under `[Unreleased]`) |

## Branch & commit protocol

- One branch per phase: `phase/NN-slug` (e.g. `phase/03-web-shell`).
- **Commit and push to `origin/main` at the end of every phase**, tagged `phaseNN`.
- A phase marked **(short)** in the roadmap may defer its commit and be bundled
  into the next phase's commit — **at most two phases per commit, never more.**
- [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`,
  `chore:`, `docs:`, `test:`, `refactor:`, `build:`, `ci:`.
- Every commit message ends with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
- The phase's `Status` / `Completed` / `Commit` fields in `docs/ROADMAP.md` are
  updated **in that same phase-closing commit**.

## Design principles (non-negotiable)

1. **Data layer and render layer never touch.** The server computes a view model;
   the client renders it. No display logic on the server, no data fetching in a card.
2. **Everything hardcoded in PinedaDisplay becomes a default, a setting, or a
   deletion** — never a constant a user has to edit.
3. **A card is a folder.** Adding a feature is adding a folder, not editing core.
4. **Degrade, don't crash.** Missing key, dead network, old browser, stale data —
   each has a designed fallback state.
5. **One interactive accent, plus ported card identity colors.** `#E7A34A`
   means "touch this" and nothing else uses it for that. Separately, a small
   fixed set of colors carried over from PinedaDisplay's palette
   (`--accent-teal` / `--accent-gold` / `--accent-red`) marks what *kind* of
   card you're looking at — a phrase card's language label, an affirmation's
   quote, a severity tier — the same way a card's own background color is
   fixed rather than theme-driven. These are a closed set ported deliberately
   for parity with the original design, not a general license for cards to
   invent their own saturated colors.
