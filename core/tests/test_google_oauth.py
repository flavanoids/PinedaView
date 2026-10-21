# SPDX-License-Identifier: Apache-2.0
"""google_oauth: the parts that don't need a network — PKCE, state packing,
and token bookkeeping."""

from __future__ import annotations

import time

import pytest

from pinedaview import google_oauth


def test_state_round_trips_nonce_and_return_url() -> None:
    state = google_oauth.encode_state(nonce="abc123", return_url="http://10.0.0.5:8090/x")
    nonce, return_url = google_oauth.decode_state(state)
    assert nonce == "abc123"
    assert return_url == "http://10.0.0.5:8090/x"


def test_decode_state_rejects_garbage() -> None:
    with pytest.raises(google_oauth.OAuthError):
        google_oauth.decode_state("not-valid-base64!!!")


def test_authorize_url_carries_pkce_and_state() -> None:
    url = google_oauth.build_authorize_url(
        client_id="client-1",
        redirect_uri="https://bounce.example/cb",
        state="the-state",
        code_verifier="verifier-value",
    )
    assert "client_id=client-1" in url
    assert "redirect_uri=https%3A%2F%2Fbounce.example%2Fcb" in url
    assert "state=the-state" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "access_type=offline" in url


def test_pending_auth_store_round_trips_and_expires() -> None:
    store = google_oauth.PendingAuthStore()
    nonce, verifier = store.create()
    pending = store.pop(nonce)
    assert pending is not None
    assert pending.code_verifier == verifier
    # popped once — a replayed callback shouldn't find it again.
    assert store.pop(nonce) is None


def test_token_set_expired_flag() -> None:
    fresh = google_oauth.TokenSet(
        access_token="a", refresh_token="r", expires_at=time.time() + 3600
    )
    stale = google_oauth.TokenSet(access_token="a", refresh_token="r", expires_at=time.time() - 1)
    assert not fresh.expired
    assert stale.expired


def test_token_set_dict_round_trip() -> None:
    original = google_oauth.TokenSet(access_token="a", refresh_token="r", expires_at=123.0)
    restored = google_oauth.TokenSet.from_dict(original.as_dict())
    assert restored == original
