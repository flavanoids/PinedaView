# SPDX-License-Identifier: Apache-2.0
"""Google OAuth 2.0 (Authorization Code + PKCE), read-only Calendar scope.

Design notes (see docs/DECISIONS.md for the fuller writeup):

- PKCE means the client secret alone can't replay a stolen auth code, and the
  code is single-use and tied to our redirect URI — so the one hop this flow
  makes over the LAN (the phone bouncing the auth code back to this device)
  carries nothing that's independently useful to an eavesdropper.
- Google requires an HTTPS redirect URI for non-localhost web clients. A LAN
  device has neither, so the registered redirect target is a small static
  "bounce" page (``bounce_url``) that the operator hosts anywhere with HTTPS —
  its only job is forwarding ``?code=&state=`` to this device's own
  ``/api/calendar/oauth/finish`` via a client-side redirect. It never sees a
  token and stores nothing.
- Tokens never touch the bounce page or the browser after that — the code is
  exchanged for tokens server-to-server, straight to Google over HTTPS.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import httpx

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"

SCOPE = "https://www.googleapis.com/auth/calendar.readonly openid email"

# How long a pairing attempt (QR scan → consent → bounce back) stays valid.
_PENDING_TTL_S = 600


class OAuthError(RuntimeError):
    """The exchange, refresh, or revoke call failed."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass
class PendingAuth:
    """One in-flight connect attempt, keyed by its ``state`` nonce.

    Kept in memory only — a self-hosted single-process server, and a
    half-finished pairing attempt isn't worth surviving a restart for.
    """

    code_verifier: str
    created_at: float = field(default_factory=time.monotonic)

    @property
    def expired(self) -> bool:
        return time.monotonic() - self.created_at > _PENDING_TTL_S


class PendingAuthStore:
    """In-memory nonce → :class:`PendingAuth`, with lazy expiry sweeps."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingAuth] = {}

    def create(self) -> tuple[str, str]:
        """Returns ``(nonce, code_verifier)`` and remembers the pairing."""
        self._sweep()
        nonce = _b64url(secrets.token_bytes(24))
        verifier = _b64url(secrets.token_bytes(32))
        self._pending[nonce] = PendingAuth(code_verifier=verifier)
        return nonce, verifier

    def pop(self, nonce: str) -> PendingAuth | None:
        pending = self._pending.pop(nonce, None)
        if pending is None or pending.expired:
            return None
        return pending

    def _sweep(self) -> None:
        expired = [k for k, v in self._pending.items() if v.expired]
        for key in expired:
            self._pending.pop(key, None)


def encode_state(*, nonce: str, return_url: str) -> str:
    """Pack the pairing nonce and this device's own callback URL into the one
    field Google round-trips verbatim. This is what lets the bounce page stay
    completely generic — it never needs to know which device is asking, it
    just reads ``return_url`` back out of the state it was handed and forwards
    the browser there. CSRF protection comes from ``nonce`` only existing in
    :class:`PendingAuthStore` for one pairing attempt; ``return_url`` isn't a
    secret, just routing."""
    payload = json.dumps({"n": nonce, "r": return_url}, separators=(",", ":"))
    return _b64url(payload.encode("utf-8"))


def decode_state(state: str) -> tuple[str, str]:
    """Returns ``(nonce, return_url)``. Raises :class:`OAuthError` on garbage
    input — a forged or truncated ``state`` is just a failed connect, not a
    reason to crash the handler."""
    try:
        padded = state + "=" * (-len(state) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        return str(payload["n"]), str(payload["r"])
    except (ValueError, KeyError, TypeError) as exc:
        raise OAuthError(f"unreadable state: {exc}") from exc


def build_authorize_url(
    *, client_id: str, redirect_uri: str, state: str, code_verifier: str
) -> str:
    challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # guarantees a refresh_token even on a repeat connect
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{_AUTH_URL}?{urllib.parse.urlencode(params)}"


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float
    """Monotonic-ish wall clock (``time.time()``) the access token expires at."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenSet:
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=(str(data["refresh_token"]) if data.get("refresh_token") else None),
            expires_at=float(data["expires_at"]),
        )

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # refresh a minute early


async def exchange_code(
    client: httpx.AsyncClient,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> TokenSet:
    try:
        response = await client.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(f"token exchange failed: {exc}") from exc
    return _token_set_from_payload(payload)


async def refresh_access_token(
    client: httpx.AsyncClient, *, client_id: str, client_secret: str, refresh_token: str
) -> TokenSet:
    try:
        response = await client.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(f"token refresh failed: {exc}") from exc
    token = _token_set_from_payload(payload)
    # Google omits refresh_token on a refresh response — carry the old one forward.
    return (
        token
        if token.refresh_token
        else TokenSet(
            access_token=token.access_token,
            refresh_token=refresh_token,
            expires_at=token.expires_at,
        )
    )


def _token_set_from_payload(payload: dict[str, Any]) -> TokenSet:
    if "access_token" not in payload:
        raise OAuthError(f"unexpected token response: {payload}")
    return TokenSet(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_at=time.time() + float(payload.get("expires_in", 3600)),
    )


async def ensure_fresh(
    client: httpx.AsyncClient, *, account: dict[str, Any], client_id: str, client_secret: str
) -> TokenSet:
    """The account's tokens, refreshed if the access token has expired.

    Callers persist the result themselves — merge ``TokenSet.as_dict()`` into
    the stored account and write it back — since where "persist" means
    differs between a provider poll (``ctx.set_secret``) and a request
    handler (``runtime.secrets.set``)."""
    tokens = TokenSet.from_dict(account)
    if not tokens.expired:
        return tokens
    return await refresh_access_token(
        client,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=tokens.refresh_token or "",
    )


async def revoke(client: httpx.AsyncClient, *, token: str) -> None:
    """Best-effort — a dead/expired token 400s, which we don't care about; the
    caller is deleting local state regardless."""
    with contextlib.suppress(httpx.HTTPError):
        await client.post(_REVOKE_URL, params={"token": token})


async def fetch_userinfo(client: httpx.AsyncClient, *, access_token: str) -> dict[str, Any]:
    try:
        response = await client.get(
            _USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(f"userinfo failed: {exc}") from exc


async def fetch_calendar_list(
    client: httpx.AsyncClient, *, access_token: str
) -> list[dict[str, Any]]:
    """All calendars visible to the account — owned, shared, and subscribed."""
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        while True:
            params = {"maxResults": "250"}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(_CALENDAR_LIST_URL, headers=headers, params=params)
            response.raise_for_status()
            payload = response.json()
            items.extend(payload.get("items", []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(f"calendar list failed: {exc}") from exc
    return items
