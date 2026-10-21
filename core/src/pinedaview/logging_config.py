# SPDX-License-Identifier: Apache-2.0
"""Logging setup — plain text for a terminal, JSON for a service log."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from typing import Any

_RESERVED = frozenset(logging.makeLogRecord({}).__dict__)

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Stamp every record with the current request's correlation id (if any)."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = request_id.get()
        if rid:
            record.req_id = rid
        return True


class AccessLogFilter(logging.Filter):
    """Filter out routine high-frequency health polls (GET /api/health 200) from

    uvicorn access logs to prevent systemd journal and disk overflow. Non-200
    health checks and all other endpoints continue to be logged.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "GET /api/health HTTP" in msg and " 200" in msg:
            return False
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        rid = request_id.get()
        if rid:
            payload["req_id"] = rid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s %(name)s  %(message)s", "%H:%M:%S")
        )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    if level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").addFilter(AccessLogFilter())
