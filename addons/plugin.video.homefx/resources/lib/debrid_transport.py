"""Fixed-host HTTPS transport, not connected to the current Kodi preview.

Socket operations share an elapsed deadline; cancellation is checked between I/O
operations. Platform DNS resolution is not interruptible by Python socket timeouts,
so DNS duration remains an operating-system limit. No proxies, redirects, retries,
or credential logging are used. Tests inject connections and never contact Real-Debrid.
"""
import http.client
import io
import json
import math
import re
import ssl
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from .debrid_client import DebridError, Response, validate_url
from .debrid_auth import GRANT_TYPE


class TransportError(Exception):
    """Fixed non-sensitive failure codes; request details must never be included."""


def _text(value, limit):
    return (isinstance(value, str) and 0 < len(value) <= limit
            and all(32 < ord(char) < 127 for char in value))


def _close(resource):
    try:
        resource.close()
        return True
    except Exception:
        # Cleanup failures must not replace the sanitized request outcome.
        return False


class _Deadline:
    def __init__(self, timeout, total, clock, cancelled):
        self.timeout, self.clock, self.cancelled = timeout, clock, cancelled
        self.last = clock()
        if type(self.last) not in (int, float) or not 0 <= self.last <= 10 ** 12:
            raise TransportError("transport_failed")
        self.expires = self.last + total

    def remaining(self):
        if self.cancelled():
            raise TransportError("cancelled")
        now = self.clock()
        if type(now) not in (int, float) or not self.last <= now <= 10 ** 12:
            raise TransportError("transport_failed")
        self.last = now
        remaining = self.expires - now
        if remaining <= 0:
            raise TransportError("timeout")
        return min(self.timeout, remaining)


class _Reader(io.RawIOBase):
    def __init__(self, sock, deadline):
        super().__init__()
        self.sock, self.deadline = sock, deadline
        self.raw = sock.makefile("rb", buffering=0)

    def close(self):
        try:
            self.raw.close()
        finally:
            super().close()

    def readable(self):
        return True

    def readinto(self, buffer):
        self.sock.settimeout(self.deadline.remaining())
        count = self.raw.readinto(buffer)
        self.deadline.remaining()
        return count


class _DeadlineSocket:
    """Enforce the shared budget on each socket receive, including header lines."""
    def __init__(self, sock, deadline):
        self._sock, self._deadline = sock, deadline

    def makefile(self, mode, *args, **kwargs):
        if mode != "rb":
            raise TransportError("transport_failed")
        return io.BufferedReader(_Reader(self._sock, self._deadline))

    def sendall(self, data):
        self._sock.settimeout(self._deadline.remaining())
        self._sock.sendall(data)
        self._deadline.remaining()

    def __getattr__(self, name):
        return getattr(self._sock, name)


def _json_body(raw):
    # Bound nesting before json.loads so deeply nested input cannot exhaust its stack.
    text = raw.decode("utf-8", errors="strict")
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > 32:
                raise TransportError("invalid_json")
        elif char in "]}":
            depth -= 1
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise TransportError("invalid_json")
            result[key] = value
        return result
    def number(value):
        if len(value) > 128:
            raise TransportError("invalid_json")
        result = float(value) if any(c in value for c in ".eE") else int(value)
        if isinstance(result, float) and not math.isfinite(result):
            raise TransportError("invalid_json")
        return result
    def reject_constant(value):
        raise TransportError("invalid_json")
    result = json.loads(text, object_pairs_hook=pairs, parse_int=number,
                        parse_float=number, parse_constant=reject_constant)
    if not isinstance(result, (dict, list)):
        raise TransportError("invalid_json")
    return result


class Transport:
    """Inactive fixed-host adapter; construction/import performs no network I/O.

    connection_factory is trusted test code, never configuration from a user or
    service response. DNS duration is OS-bound; socket reads share an elapsed
    deadline. The caller must coordinate cross-invocation service rate limits.
    """
    def __init__(self, timeout=10, total_timeout=30, max_bytes=2 * 1024 * 1024,
                 cancelled=lambda: False, clock=time.monotonic,
                 connection_factory=http.client.HTTPSConnection):
        for value in (timeout, total_timeout):
            if type(value) not in (int, float) or not 0 < value <= 60:
                raise TransportError("invalid_configuration")
        if (type(max_bytes) is not int or not 1024 <= max_bytes <= 8 * 1024 * 1024
                or not all(callable(x) for x in (cancelled, clock, connection_factory))):
            raise TransportError("invalid_configuration")
        self._timeout, self._total, self._max_bytes = timeout, total_timeout, max_bytes
        self._cancelled, self._clock, self._factory = cancelled, clock, connection_factory

    def __repr__(self):
        return "Transport(<fixed HTTPS host>)"

    def oauth_request(self, method, path, parameters):
        contracts = {
            "/oauth/v2/device/code": ("GET", {"client_id", "new_credentials"}),
            "/oauth/v2/device/credentials": ("GET", {"client_id", "code"}),
            "/oauth/v2/token": ("POST", {"client_id", "client_secret", "code", "grant_type"}),
        }
        if (type(path) is not str or path not in contracts
                or method != contracts[path][0] or type(parameters) is not dict
                or set(parameters) != contracts[path][1]
                or any(not _text(value, 4096) for value in parameters.values())
                or len(parameters["client_id"]) > 256
                or (path.endswith("/device/code") and parameters["new_credentials"] != "yes")
                or (path.endswith("/token") and parameters["grant_type"] != GRANT_TYPE)):
            raise TransportError("invalid_request")
        encoded = urlencode(parameters).encode("ascii")
        if len(encoded) > 32768:
            raise TransportError("invalid_request")
        headers = {"Accept": "application/json"}
        if method == "GET":
            return self._request(method, path + "?" + encoded.decode("ascii"), headers, None)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        return self._request(method, path, headers, encoded)

    def api_request(self, method, path, headers, body=None):
        if type(method) is not str or method not in {"GET", "POST"}:
            raise TransportError("invalid_request")
        required = {"Authorization"} if method == "GET" else {"Authorization", "Content-Type"}
        if (type(headers) is not dict or set(headers) != required
                or not isinstance(headers["Authorization"], str)
                or not headers["Authorization"].startswith("Bearer ")
                or not _text(headers["Authorization"][7:], 4096)
                or (method == "POST" and headers["Content-Type"] != "application/x-www-form-urlencoded")):
            raise TransportError("invalid_request")
        self._api_path(path, method)
        payload = None
        if method == "GET":
            if body is not None:
                raise TransportError("invalid_request")
        else:
            if type(body) is not dict or set(body) != {"link"}:
                raise TransportError("invalid_request")
            try:
                link = validate_url(body["link"])
            except DebridError:
                raise TransportError("invalid_request") from None
            payload = urlencode({"link": link}).encode("ascii")
            if len(payload) > 32768:
                raise TransportError("invalid_request")
        outbound = dict(headers)
        outbound["Accept"] = "application/json"
        return self._request(method, path, outbound, payload)

    @staticmethod
    def _api_path(path, method):
        if not _text(path, 2048) or any(c in path for c in "%\\#"):
            raise TransportError("invalid_request")
        try:
            parsed = urlsplit(path)
        except ValueError:
            raise TransportError("invalid_request") from None
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise TransportError("invalid_request")
        if method == "POST":
            if path != "/rest/1.0/unrestrict/link":
                raise TransportError("invalid_request")
            return
        if path == "/rest/1.0/user":
            return
        if parsed.path != "/rest/1.0/downloads":
            raise TransportError("invalid_request")
        try:
            query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True,
                              max_num_fields=2)
        except ValueError:
            raise TransportError("invalid_request") from None
        if len(query) != 2 or set(k for k, v in query) != {"page", "limit"}:
            raise TransportError("invalid_request")
        for key, value in query:
            if not re.fullmatch(r"[1-9][0-9]{0,2}", value) or int(value) > 100:
                raise TransportError("invalid_request")

    def _request(self, method, path, headers, body):
        connection = response = None
        try:
            deadline = _Deadline(self._timeout, self._total, self._clock, self._cancelled)
            context = ssl.create_default_context()
            connection = self._factory("api.real-debrid.com", port=443,
                                       timeout=deadline.remaining(), context=context)
            connection.connect()
            deadline.remaining()
            connection.sock = _DeadlineSocket(connection.sock, deadline)
            connection.auto_open = False
            connection.request(method, path, body=body, headers=headers)
            deadline.remaining()
            response = connection.getresponse()
            deadline.remaining()
            if type(response.status) is not int or not 100 <= response.status <= 599:
                raise TransportError("invalid_response")
            raw_headers = response.getheaders()
            if len(raw_headers) > 64 or sum(len(k) + len(v) for k, v in raw_headers) > 16384:
                raise TransportError("invalid_response")
            safe, content_type, length, encoding, transfer = {}, None, None, None, None
            seen = set()
            for key, value in raw_headers:
                if (not isinstance(key, str) or not isinstance(value, str)
                        or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", key)
                        or len(value) > 8192 or any(ord(c) < 32 or ord(c) > 126 for c in value)):
                    raise TransportError("invalid_response")
                key = key.lower()
                if key in {"content-type", "content-length", "content-encoding", "transfer-encoding",
                           "retry-after", "x-total-count"}:
                    if key in seen or len(value) > 256:
                        raise TransportError("invalid_response")
                    seen.add(key)
                    if key == "content-type":
                        content_type = value
                    elif key == "content-length":
                        if not re.fullmatch(r"[0-9]{1,12}", value):
                            raise TransportError("invalid_response")
                        length = int(value)
                    elif key == "content-encoding":
                        encoding = value
                    elif key == "transfer-encoding":
                        transfer = value.lower()
                    else:
                        safe[key] = value
            if 300 <= response.status < 400:
                raise TransportError("redirect_refused")
            if transfer not in (None, "chunked") or (transfer is not None and length is not None):
                raise TransportError("invalid_response")
            if encoding not in (None, "identity"):
                raise TransportError("invalid_response")
            if length is not None and length > self._max_bytes:
                raise TransportError("response_too_large")
            json_content = (content_type is not None and
                            content_type.split(";", 1)[0].strip().lower() == "application/json")
            if not json_content:
                if response.status != 200:
                    return Response(response.status, safe, {})
                raise TransportError("invalid_response")
            chunks, size = [], 0
            while True:
                deadline.remaining()
                chunk = response.read(min(16384, self._max_bytes + 1 - size))
                deadline.remaining()
                if not chunk:
                    break
                size += len(chunk)
                if size > self._max_bytes:
                    raise TransportError("response_too_large")
                chunks.append(chunk)
            if length is not None and length != size:
                raise TransportError("invalid_response")
            if size == 0 and response.status != 200:
                return Response(response.status, safe, {})
            try:
                decoded = _json_body(b"".join(chunks))
            except Exception:
                raise TransportError("invalid_json") from None
            deadline.remaining()
            return Response(response.status, safe, decoded)
        except TransportError as exc:
            allowed = {"cancelled", "timeout", "invalid_response", "redirect_refused",
                       "response_too_large", "invalid_json", "transport_failed"}
            code = str(exc) if str(exc) in allowed else "transport_failed"
            raise TransportError(code) from None
        except TimeoutError:
            raise TransportError("timeout") from None
        except Exception:
            raise TransportError("transport_failed") from None
        finally:
            for resource in (response, connection):
                if resource is not None:
                    _close(resource)
