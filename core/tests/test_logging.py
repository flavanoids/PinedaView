# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import logging
import sys

import pytest

from pinedaview.logging_config import JsonFormatter, configure_logging


def test_json_formatter_emits_parseable_lines() -> None:
    record = logging.makeLogRecord(
        {"name": "x", "levelname": "INFO", "msg": "hello %s", "args": ("world",)}
    )
    record.provider = "weather"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["msg"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["provider"] == "weather"


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    assert "ValueError: boom" in json.loads(JsonFormatter().format(record))["exc"]


@pytest.mark.parametrize("as_json", [True, False])
def test_configure_logging_installs_one_handler(as_json: bool) -> None:
    configure_logging(level="DEBUG", json_output=as_json)
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert root.level == logging.DEBUG


def test_configure_logging_quiets_httpx_when_not_debug() -> None:
    configure_logging(level="INFO")
    assert logging.getLogger("httpx").level == logging.WARNING


def test_access_log_filter_drops_health_200() -> None:
    from pinedaview.logging_config import AccessLogFilter

    filt = AccessLogFilter()
    rec_suppress = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '192.0.2.161:1234 - "GET /api/health HTTP/1.1" 200', (), None
    )
    rec_keep_500 = logging.LogRecord(
        "uvicorn.access", logging.WARNING, "", 0, '192.0.2.161:1234 - "GET /api/health HTTP/1.1" 500', (), None
    )
    rec_keep_other = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '192.0.2.161:1234 - "GET /api/status HTTP/1.1" 200', (), None
    )
    assert not filt.filter(rec_suppress)
    assert filt.filter(rec_keep_500)
    assert filt.filter(rec_keep_other)

