# Security policy

## Supported versions

The latest `1.x` release gets security fixes. Older tags do not.

## Reporting a vulnerability

Report privately — **do not open a public issue**:

- GitHub → **Security → Report a vulnerability** on this repo, or
- email the address on the maintainer's GitHub profile.

Include the affected version (`GET /api/health` → `app_version`), the impact, and
minimal reproduction steps. A full working exploit is not needed and is
discouraged.

Expect an acknowledgement within a week and a fix or mitigation plan before any
coordinated public disclosure.

## Threat model

PinedaView is a **LAN appliance**. It assumes the local network is
semi-trusted and ships two optional gates:

| Setting | Effect |
|---|---|
| `api.write_token` | every `POST` / `PUT` / `PATCH` / `DELETE` (incl. `/api/ingest`) needs `Authorization: Bearer …`. One deliberate exception: `POST /api/photos` stays open so a house guest can scan the photo card's QR and drop a photo in — rotating and deleting photos still needs the token. |
| `api.admin_token` | the **admin surface** — `/api/config`, `/api/secrets`, `/api/control`, `/api/setup`, `/api/profiles`, `/api/devices`, card settings — needs the bearer token, on reads too. The public surface (view, stream, health, metrics, themes, photo GET, card list) stays open. |

Set `admin_token` on any network where untrusted devices or people are present.

**Never reachable from outside the LAN.** Exposing pinedaview to the internet
(a tunnel, port-forward or public reverse proxy) is unsupported, with or
without tokens. `pinedaview-guard.service` enforces this on native installs:
`:8090` answers only loopback, wg0 and private addresses, and tunnel
processes such as cloudflared can't connect to it at all. See
[OPERATIONS.md → Keeping it on the LAN](docs/OPERATIONS.md#keeping-it-on-the-lan).
Outbound data fetches are unaffected.

**Secrets** (API keys) are encrypted at rest with a machine-local key
(`secrets.key`, `chmod 600`) and are never included in any API response or view
model — only their names are listed.

## What's audited

`pnpm audit` (high and up) and `pip-audit` run in CI on every push and pull
request. Dependency versions are pinned; the lockfiles are committed.
