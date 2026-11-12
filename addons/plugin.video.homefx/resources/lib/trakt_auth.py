"""Inactive OAuth foundations: callers inject transport; this module makes no I/O.

A future transport must bind relative OAuth paths to AUTH_HOST, verify TLS, bound
response sizes/timeouts, disable redirects, and never log request/response bodies.
"""
from dataclasses import dataclass, field
import math
import time
from urllib.parse import urlsplit

AUTH_HOST = "https://auth.trakt.tv"


class AuthError(Exception):
    """A fixed, non-sensitive error code suitable for presentation or diagnostics."""


def _text(value, maximum=4096):
    return (isinstance(value, str) and 0 < len(value) <= maximum
            and all(32 < ord(char) < 127 for char in value))


def _number(value, minimum, maximum):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and minimum <= value <= maximum and math.isfinite(value))


@dataclass(frozen=True, repr=False)
class TokenSet:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float

    def __post_init__(self):
        if (not _text(self.access_token) or not _text(self.refresh_token)
                or not _number(self.expires_at, 1, 10 ** 12)):
            raise AuthError("invalid_token_response")

    def __repr__(self):
        return "TokenSet(<redacted>)"

    @classmethod
    def from_response(cls, body):
        if not isinstance(body, dict):
            raise AuthError("invalid_token_response")
        created = body.get("created_at")
        expires = body.get("expires_in")
        if (body.get("token_type") != "bearer"
                or not _number(created, 1, 10 ** 12)
                or not _number(expires, 1, 366 * 86400)):
            raise AuthError("invalid_token_response")
        return cls(body.get("access_token"), body.get("refresh_token"), created + expires)


@dataclass(frozen=True, repr=False)
class DevicePrompt:
    user_code: str = field(repr=False)
    verification_url: str = field(repr=False)
    expires_at: float

    def __repr__(self):
        return "DevicePrompt(<redacted>)"


class DeviceLogin:
    """One device-code attempt. Poll at next_poll; terminal states never retry.

    Clock must be monotonic. The caller owns scheduling/UI cancellation. A new
    instance is required to retry a terminal attempt. No credentials are logged.
    """
    TERMINAL = frozenset(("authorized", "cancelled", "expired", "denied",
                          "used", "invalid", "failed"))

    def __init__(self, request, client_id, clock=time.monotonic):
        if not _text(client_id, 256):
            raise AuthError("invalid_client_identity")
        self._request = request
        self._client_id = client_id
        self._clock = clock
        self._code = None
        self.state = "new"
        self.prompt = None
        self.tokens = None
        self.next_poll = None
        self._interval = None

    def __repr__(self):
        return "DeviceLogin(state={!r})".format(self.state)

    def _finish(self, state):
        self.state = state
        self._code = None
        self.prompt = None
        self.next_poll = None
        return state

    def begin(self):
        if self.state != "new":
            raise AuthError("login_already_started")
        # A timeout may consume a code issuance; do not repeat automatically.
        self.state = "requesting"
        try:
            response = self._request("POST", "/oauth/device/code",
                                     {"client_id": self._client_id})
            if self.state == "cancelled":
                return None
            body = response.body
            if response.status != 200 or not isinstance(body, dict):
                raise AuthError("device_code_failed")
            interval, expires = body.get("interval"), body.get("expires_in")
            code, user = body.get("device_code"), body.get("user_code")
            url = body.get("verification_url")
            if (not _number(interval, 1, 3600) or not _number(expires, 1, 86400)
                    or not _text(code) or not _text(user, 128) or not _text(url, 2048)):
                raise AuthError("invalid_device_response")
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname != "trakt.tv"
                    or parsed.username or parsed.password or parsed.port not in (None, 443)
                    or parsed.fragment):
                raise AuthError("invalid_device_response")
            now = self._clock()
            self.prompt = DevicePrompt(user, url, now + expires)
            self._code = code
            self._interval = interval
            self.next_poll = now + interval
            self.state = "pending"
            return self.prompt
        except Exception:
            if self.state == "cancelled":
                return None
            self._finish("failed")
            raise AuthError("device_code_failed") from None

    def cancel(self):
        if self.state not in self.TERMINAL:
            self._finish("cancelled")
        return self.state

    def poll(self):
        if self.state in self.TERMINAL:
            return self.state
        if self.state == "new":
            raise AuthError("login_not_started")
        now = self._clock()
        if now >= self.prompt.expires_at:
            return self._finish("expired")
        if now < self.next_poll:
            return self.state
        try:
            response = self._request("POST", "/oauth/device/token",
                                     {"client_id": self._client_id, "code": self._code})
            if self.state in self.TERMINAL:
                return self.state
            # A response received after local expiry cannot complete this attempt.
            now = self._clock()
            if now >= self.prompt.expires_at:
                return self._finish("expired")
            if response.status == 200:
                self.tokens = TokenSet.from_response(response.body)
                return self._finish("authorized")
            terminal = {404: "invalid", 409: "used", 410: "expired", 418: "denied"}
            if response.status in terminal:
                return self._finish(terminal[response.status])
            if response.status == 400:
                self.next_poll = now + self._interval
                return self.state
            if response.status == 429:
                # Invalid/missing Retry-After falls back to slower polling.
                delay = self._interval + 5
                for key, value in response.headers.items():
                    if key.lower() == "retry-after":
                        try:
                            numeric = float(value)
                            if math.isfinite(numeric) and numeric >= 0:
                                delay = max(delay, numeric)
                        except (ValueError, TypeError):
                            pass
                self._interval = min(max(delay, self._interval + 5), 86400)
                self.next_poll = now + self._interval
                return self.state
            return self._finish("failed")
        except Exception:
            # Transport exceptions may contain secrets, URLs or bodies.
            if self.state in self.TERMINAL:
                return self.state
            return self._finish("failed")


def refresh_tokens(store, request, client_id, redirect_uri, expected_generation):
    """Refresh once, or return None if another invocation won the claim.

    All transport/status/parse failures consume the claim and require login. The
    caller must supply the application's registered redirect URI; no default is
    invented. A transport must enforce a timeout shorter than the store claim TTL.
    """
    if not _text(client_id, 256) or not _text(redirect_uri, 2048):
        raise AuthError("invalid_client_identity")
    claim = store.claim_refresh(expected_generation)
    if claim is None:
        return None
    try:
        response = request("POST", "/oauth/token", {
            "client_id": client_id, "redirect_uri": redirect_uri,
            "grant_type": "refresh_token", "refresh_token": claim.tokens.refresh_token})
        if response.status != 200:
            raise AuthError("reauthentication_required")
        tokens = TokenSet.from_response(response.body)
        if tokens.refresh_token == claim.tokens.refresh_token:
            raise AuthError("reauthentication_required")
        if not store.complete_refresh(claim, tokens):
            raise AuthError("reauthentication_required")
        return tokens
    except Exception:
        try:
            store.fail_refresh(claim)
        finally:
            raise AuthError("reauthentication_required") from None
