# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import base64
from datetime import datetime

from pinedaview.airplay_bridge import (
    ParsedItem,
    TrackState,
    apply_item,
    iter_items,
)


def _item(kind: str, code: str, data: bytes = b"") -> str:
    type_hex = format(int.from_bytes(kind.encode("ascii"), "big"), "x")
    code_hex = format(int.from_bytes(code.encode("ascii"), "big"), "x")
    body = f"<item><type>{type_hex}</type><code>{code_hex}</code><length>{len(data)}</length>"
    if data:
        b64 = base64.b64encode(data).decode("ascii")
        body += f'\n<data encoding="base64">\n{b64}\n</data>'
    return body + "</item>\n"


# ── wire format ──────────────────────────────────────────────────────────────


def test_iter_items_parses_type_and_code() -> None:
    items, rest = iter_items(_item("core", "asal", b"Nevermind"))
    assert rest == ""
    assert items == [ParsedItem("core", "asal", b"Nevermind")]


def test_iter_items_parses_empty_payload_item() -> None:
    items, rest = iter_items(_item("ssnc", "pend"))
    assert items == [ParsedItem("ssnc", "pend", b"")]
    assert rest == ""


def test_iter_items_handles_multiple_items_in_one_read() -> None:
    buf = _item("ssnc", "pbeg") + _item("core", "minm", b"Track Title")
    items, rest = iter_items(buf)
    assert [(i.kind, i.code) for i in items] == [("ssnc", "pbeg"), ("core", "minm")]
    assert rest == ""


def test_iter_items_leaves_a_partial_trailing_item_for_next_read() -> None:
    whole = _item("core", "asar", b"Nirvana")
    split = len(whole) - 5
    items, rest = iter_items(whole[:split])
    assert items == []
    assert rest == whole[:split]
    # feeding the remainder completes it
    items, rest = iter_items(rest + whole[split:])
    assert items == [ParsedItem("core", "asar", b"Nirvana")]
    assert rest == ""


# ── progress → duration_s / started_at ───────────────────────────────────────


def test_prgr_yields_duration_and_started_at_anchor() -> None:
    state = TrackState()
    # 44100 samples/sec: a 3-minute track, 30s in.
    start, end = 1_000_000, 1_000_000 + 180 * 44100
    current = start + 30 * 44100
    item = ParsedItem("ssnc", "prgr", f"{start}/{current}/{end}".encode())

    payload = apply_item(item, state, now=1_700_000_000.0)

    assert payload is not None
    assert payload["duration_s"] == 180.0
    # started_at should be ~30s before `now`
    started = datetime.fromisoformat(str(payload["started_at"]))
    assert abs(started.timestamp() - (1_700_000_000.0 - 30)) < 1
    assert state.duration_s == 180.0


def test_prgr_with_malformed_payload_is_ignored() -> None:
    state = TrackState()
    assert apply_item(ParsedItem("ssnc", "prgr", b"not-numbers"), state) is None
    assert apply_item(ParsedItem("ssnc", "prgr", b"1/2"), state) is None  # wrong arity
    assert apply_item(ParsedItem("ssnc", "prgr", b"100/50/100"), state) is None  # end<=start
    assert state.duration_s is None


def test_pend_clears_state_and_emits_nothing() -> None:
    state = TrackState(duration_s=180.0, started_at="2026-01-01T00:00:00+00:00")
    payload = apply_item(ParsedItem("ssnc", "pend", b""), state)
    assert payload is None
    assert state.duration_s is None
    assert state.started_at is None


def test_pbeg_and_pfls_drop_the_stale_anchor() -> None:
    for code in ("pbeg", "pfls"):
        state = TrackState(duration_s=180.0, started_at="2026-01-01T00:00:00+00:00")
        assert apply_item(ParsedItem("ssnc", code, b""), state) is None
        assert state.duration_s is None
        assert state.started_at is None


def test_unrelated_items_are_ignored() -> None:
    state = TrackState()
    assert apply_item(ParsedItem("core", "asgn", b"Rock"), state) is None
    assert apply_item(ParsedItem("ssnc", "clip", b""), state) is None
