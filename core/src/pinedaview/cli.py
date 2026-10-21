# SPDX-License-Identifier: Apache-2.0
"""Command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Any

from pinedaview import __version__
from pinedaview.config import Settings, load_settings
from pinedaview.logging_config import configure_logging
from pinedaview.service import run_api

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pineda-web", description="PinedaDisplay Web server.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("serve", "run the API server"), ("dev", "serve + watch cards/")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--config", type=Path, metavar="PATH", help="path to a TOML config file")
        cmd.add_argument("--location", metavar="PLACE", help="override the weather location")
        cmd.add_argument("--host", metavar="ADDR", help="bind address")
        cmd.add_argument("--port", type=int, metavar="PORT", help="bind port")
        cmd.add_argument("--log-level", metavar="LEVEL", help="DEBUG, INFO, WARNING, …")
        cmd.add_argument("--log-json", action="store_true", help="emit structured JSON logs")
    token = sub.add_parser("mcp-token", help="make a bearer token for an MCP client")
    token.add_argument("client", help='the client\'s name, e.g. "antigua"')
    token.add_argument(
        "--scopes",
        default="display:read,display:write,system,camera:view",
        help="comma-separated (default: all)",
    )
    return parser


def _mcp_token(client: str, scopes: str) -> int:
    from pinedaview.mcp_server import new_token

    token, digest = new_token()
    listed = ", ".join(f'"{s.strip()}"' for s in scopes.split(",") if s.strip())
    print(f"Token for {client} (shown once; give it to the client):\n\n  {token}\n")
    print("Add to the server's config.toml:\n")
    print(f'[mcp.clients.{client}]\ntoken_sha256 = "{digest}"\nscopes = [{listed}]')
    return 0


def _overrides(args: argparse.Namespace) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if args.location:
        out["location"] = {"query": args.location}
    api: dict[str, Any] = {}
    if args.host:
        api["host"] = args.host
    if args.port is not None:
        api["port"] = args.port
    if api:
        out["api"] = api
    if args.log_level:
        out["log_level"] = args.log_level
    if args.log_json:
        out["log_json"] = True
    return out


def _settings_for(args: argparse.Namespace) -> Settings:
    return load_settings(args.config, overrides=_overrides(args))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "mcp-token":
        return _mcp_token(args.client, args.scopes)
    settings = _settings_for(args)
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    if args.command in ("serve", "dev"):
        try:
            asyncio.run(run_api(settings, watch=args.command == "dev"))
        except KeyboardInterrupt:  # pragma: no cover
            logger.info("interrupted")
        return 0

    return 2  # pragma: no cover - argparse guarantees a known command


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
