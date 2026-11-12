"""Inactive Real-Debrid open-source device grant with injected callbacks only.

Contract source: https://api.real-debrid.com/ (open-source and refresh workflows).
request(method, relative_path, parameters) returns an object with status/body.
GET parameters belong in the query; POST parameters are form encoded. A future
adapter must use AUTH_HOST, verified TLS, bounded responses/timeouts, no redirects,
and no logging of URLs, bodies or credentials. There is no live adapter or store.

The documentation does not identify the pending credentials error precisely.
Errors fail closed unless a separately verified pending_response classifier is
injected. No production classifier is provided. Token exchanges are never retried.
"""
from dataclasses import dataclass, field
import math
import time

AUTH_HOST = "https://api.real-debrid.com"
GRANT_TYPE = "http://oauth.net/grant_type/device/1.0"
VERIFY_URL = "https://real-debrid.com/device"


class AuthError(Exception):
    """Fixed error category; never response text, request data or credentials."""


def _text(value, maximum=4096):
    return (type(value) is str and 0 < len(value) <= maximum
            and all(32 < ord(char) < 127 for char in value))


def _number(value, minimum, maximum):
    return (type(value) in (int, float) and minimum <= value <= maximum
            and math.isfinite(value))


@dataclass(frozen=True, repr=False)
class Credentials:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)

    def __post_init__(self):
        if not _text(self.client_id, 256) or not _text(self.client_secret):
            raise AuthError("invalid_credentials")

    def __repr__(self):
        return "Credentials(<redacted>)"


@dataclass(frozen=True, repr=False)
class Tokens:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float

    def __post_init__(self):
        if (not _text(self.access_token) or not _text(self.refresh_token)
                or not _number(self.expires_at, 1, 10 ** 12)):
            raise AuthError("invalid_token_response")

    def __repr__(self):
        return "Tokens(<redacted>)"


@dataclass(frozen=True, repr=False)
class Prompt:
    user_code: str = field(repr=False)
    verification_url: str = field(repr=False)
    expires_at: float

    def __repr__(self):
        return "Prompt(<redacted>)"


def _response(request, method, path, parameters):
    try:
        response = request(method, path, parameters)
        status, body = response.status, response.body
    except Exception:
        raise AuthError("transport_error") from None
    if type(status) is not int or not 100 <= status <= 599 or not isinstance(body, dict):
        raise AuthError("invalid_response")
    return response, status, body


def _failure(status):
    return "rate_limited" if status == 429 else "authorization_failed"


def _tokens(body, issued):
    if (body.get("token_type") != "Bearer" or
            not _number(body.get("expires_in"), 1, 366 * 86400)):
        raise AuthError("invalid_token_response")
    return Tokens(body.get("access_token"), body.get("refresh_token"),
                  issued + body["expires_in"])


def _cancelled(callback):
    try:
        return bool(callback())
    except Exception:
        return True


def _wall(clock):
    try:
        now = clock()
    except Exception:
        raise AuthError("invalid_clock") from None
    if not _number(now, 1, 10 ** 12 - 366 * 86400):
        raise AuthError("invalid_clock")
    return now


class DeviceLogin:
    """Single attempt; caller schedules poll at next_poll and owns UI cancellation.

    pending_response is an optional injected classifier for 400/403 credentials
    responses only. It must be verified independently before any live integration.
    Credentials and tokens become visible together only after successful exchange.
    No durable generation/account race or secure storage is implemented here.
    """
    def __init__(self, request, client_id, clock=time.monotonic,
                 wall_clock=time.time, pending_response=None):
        if not _text(client_id, 256):
            raise AuthError("invalid_client_id")
        self._request, self._client_id = request, client_id
        self._clock, self._wall = clock, wall_clock
        self._pending_response = pending_response
        self.state = "new"
        self.prompt = self.next_poll = self.credentials = self.tokens = None
        self._code = self._interval = self._last = None
        self._polling = False

    def __repr__(self):
        return "DeviceLogin(<private attempt>)"

    def _now(self):
        try:
            value = self._clock()
        except Exception:
            raise AuthError("invalid_clock") from None
        if not _number(value, 0, 10 ** 12) or (self._last is not None and value < self._last):
            raise AuthError("invalid_clock")
        self._last = value
        return value

    def _finish(self, state):
        self.state = state
        self._code = self._interval = self.prompt = self.next_poll = None
        if state != "authorized":
            self.credentials = self.tokens = None
        return state

    def cancel(self):
        return self._finish("cancelled")

    def _stopped(self, cancelled):
        requested = _cancelled(cancelled)
        if self.state == "cancelled" or requested:
            return self._finish("cancelled")
        if self.prompt is not None and self._now() >= self.prompt.expires_at:
            return self._finish("expired")
        return None

    def begin(self, cancelled=lambda: False):
        if self.state != "new":
            raise AuthError("attempt_already_started")
        self.state = "issuing"
        try:
            started = self._now()
            if self._stopped(cancelled):
                return None
            _, status, body = _response(self._request, "GET", "/oauth/v2/device/code",
                {"client_id": self._client_id, "new_credentials": "yes"})
            if self._stopped(cancelled):
                return None
            if status != 200:
                raise AuthError(_failure(status))
            if (not _text(body.get("device_code")) or not _text(body.get("user_code"), 128)
                    or body.get("verification_url") != VERIFY_URL
                    or not _number(body.get("interval"), 1, 60)
                    or not _number(body.get("expires_in"), 1, 3600)):
                raise AuthError("invalid_device_response")
            self._code, self._interval = body["device_code"], body["interval"]
            self.prompt = Prompt(body["user_code"], VERIFY_URL, started + body["expires_in"])
            if self._stopped(cancelled):
                return None
            self.next_poll = self._now() + self._interval
            self.state = "pending"
            return self.prompt
        except AuthError:
            self._finish("failed")
            raise

    def poll(self, cancelled=lambda: False):
        # Guard before clocks/cancellation callbacks: either may pump the UI and
        # reenter poll while state still says pending. Nested calls observe only.
        if self._polling:
            return self.state
        self._polling = True
        try:
            if self.state != "pending":
                return self.state
            try:
                if self._stopped(cancelled):
                    return self.state
                if self._now() < self.next_poll:
                    return self.state
                # Reentrant calls during either request cannot initiate another exchange.
                self.state = "checking"
                response, status, body = _response(self._request, "GET", "/oauth/v2/device/credentials",
                    {"client_id": self._client_id, "code": self._code})
                if self._stopped(cancelled):
                    return self.state
                if status != 200:
                    pending = False
                    if status in (400, 403) and self._pending_response is not None:
                        try:
                            pending = self._pending_response(response) is True
                        except Exception:
                            raise AuthError("invalid_pending_response") from None
                    if self._stopped(cancelled):
                        return self.state
                    if pending:
                        self.state = "pending"
                        self.next_poll = self._now() + self._interval
                        return self.state
                    raise AuthError(_failure(status))
                credentials = Credentials(body.get("client_id"), body.get("client_secret"))
                self.state = "exchanging"
                issued = _wall(self._wall)
                if self._stopped(cancelled):
                    return self.state
                _, status, body = _response(self._request, "POST", "/oauth/v2/token", {
                    "client_id": credentials.client_id, "client_secret": credentials.client_secret,
                    "code": self._code, "grant_type": GRANT_TYPE})
                if self._stopped(cancelled):
                    return self.state
                if status != 200:
                    raise AuthError(_failure(status))
                tokens = _tokens(body, issued)
                self.credentials, self.tokens = credentials, tokens
                return self._finish("authorized")
            except AuthError:
                self._finish("failed")
                raise
        finally:
            self._polling = False


def refresh(request, credentials, refresh_token, clock=time.time, cancelled=lambda: False):
    """One injected exchange, with no retry or persistence.

    Caller must establish durable exclusive refresh/account ownership before using
    this with a live store. A lost response requires explicit recovery, not replay.
    """
    if not isinstance(credentials, Credentials) or not _text(refresh_token):
        raise AuthError("invalid_refresh_input")
    if _cancelled(cancelled):
        raise AuthError("cancelled")
    issued = _wall(clock)
    _, status, body = _response(request, "POST", "/oauth/v2/token", {
        "client_id": credentials.client_id, "client_secret": credentials.client_secret,
        "code": refresh_token, "grant_type": GRANT_TYPE})
    if _cancelled(cancelled):
        raise AuthError("cancelled")
    if status != 200:
        raise AuthError(_failure(status))
    return _tokens(body, issued)
