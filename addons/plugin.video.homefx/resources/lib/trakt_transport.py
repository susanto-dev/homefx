"""Fixed-host HTTPS transport, not connected to the current Kodi preview.

Socket operations share an elapsed deadline; cancellation is checked between I/O
operations. Platform DNS resolution is not interruptible by Python socket timeouts,
so DNS duration remains an operating-system limit. No proxies, redirects, retries,
or credential logging are used. Tests inject connections and never contact Trakt.
"""
import http.client
import io
import json
import math
import re
import ssl
import time
from urllib.parse import parse_qsl, urlsplit

from .trakt_client import Response


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
        self.expires = clock() + total

    def remaining(self):
        if self.cancelled():
            raise TransportError("cancelled")
        remaining = self.expires - self.clock()
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
    """Explicitly constructed transport; importing the module performs no I/O.

    connection_factory is a test seam with HTTPSConnection's signature. Production
    callers must use the default; custom factories are trusted code, not input.
    The default total budget is shorter than the token store's refresh-claim TTL.
    """
    def __init__(self, timeout=10, total_timeout=30, max_bytes=2 * 1024 * 1024,
                 cancelled=lambda: False, clock=time.monotonic,
                 connection_factory=http.client.HTTPSConnection):
        for value in (timeout, total_timeout):
            if (type(value) not in (int, float) or not 0 < value <= 60
                    or not math.isfinite(value)):
                raise TransportError("invalid_configuration")
        if (type(max_bytes) is not int or not 1024 <= max_bytes <= 8 * 1024 * 1024
                or not callable(cancelled) or not callable(clock)
                or not callable(connection_factory)):
            raise TransportError("invalid_configuration")
        self._timeout, self._total, self._max_bytes = timeout, total_timeout, max_bytes
        self._cancelled, self._clock, self._factory = cancelled, clock, connection_factory

    def __repr__(self):
        return "Transport(<fixed HTTPS hosts>)"

    def oauth_request(self, method, path, body):
        fields = {
            "/oauth/device/code": {"client_id"},
            "/oauth/device/token": {"client_id", "code"},
            "/oauth/token": {"client_id", "redirect_uri", "grant_type", "refresh_token"},
        }
        if (method != "POST" or not isinstance(path, str) or path not in fields
                or not isinstance(body, dict) or set(body) != fields[path]
                or any(not _text(value, 4096) for value in body.values())
                or (path == "/oauth/token" and body["grant_type"] != "refresh_token")):
            raise TransportError("invalid_request")
        payload = json.dumps(body, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        return self._request("auth.trakt.tv", method, path,
                             {"Content-Type": "application/json", "Accept": "application/json"}, payload)

    def api_request(self, method, path, headers, body=None):
        self._api_path(path)
        required = {"Authorization", "trakt-api-key", "trakt-api-version", "Content-Type"}
        if (method != "GET" or body is not None or not isinstance(headers, dict)
                or set(headers) != required
                or any(not _text(v, 4096) for k, v in headers.items() if k != "Authorization")
                or not isinstance(headers["Authorization"], str)
                or not headers["Authorization"].startswith("Bearer ")
                or not _text(headers["Authorization"][7:], 4096)
                or len(headers["Authorization"]) <= len("Bearer ")
                or headers["trakt-api-version"] != "2"
                or headers["Content-Type"] != "application/json"):
            raise TransportError("invalid_request")
        # Authorization intentionally contains one space; its token must not.
        outbound = dict(headers)
        outbound["Accept"] = "application/json"
        return self._request("api.trakt.tv", method, path, outbound, None)

    @staticmethod
    def _api_path(path):
        if not _text(path, 2048) or not path.startswith("/") or path.startswith("//") or any(c in path for c in "%\\#"):
            raise TransportError("invalid_request")
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or parsed.fragment:
            raise TransportError("invalid_request")
        slug = r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}"
        allowed = (r"/users/me/lists", r"/users/likes/lists", r"/users/settings",
                   r"/users/" + slug + r"/lists/" + slug + r"/items",
                   r"/sync/playback", r"/shows/[1-9][0-9]{0,19}/progress/watched",
                   r"/shows/[1-9][0-9]{0,19}/seasons/[0-9]{1,5}")
        if not any(re.fullmatch(pattern, parsed.path) for pattern in allowed):
            raise TransportError("invalid_request")
        try:
            query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=6)
        except ValueError:
            raise TransportError("invalid_request") from None
        if len(dict(query)) != len(query):
            raise TransportError("invalid_request")
        for key, value in query:
            if key in {"page", "limit"}:
                valid = bool(re.fullmatch(r"[1-9][0-9]{0,2}", value)) and int(value) <= 100
            else:
                valid = (key, value) in {("extended", "full"), ("hidden", "false"), ("specials", "false")}
            if not valid:
                raise TransportError("invalid_request")

    def _request(self, host, method, path, headers, body):
        connection = response = None
        try:
            deadline = _Deadline(self._timeout, self._total, self._clock, self._cancelled)
            context = ssl.create_default_context()
            connection = self._factory(host, port=443, timeout=deadline.remaining(), context=context)
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
            safe, content_type, length, encoding = {}, None, None, None
            seen = set()
            for key, value in raw_headers:
                key = key.lower()
                if key in {"content-type", "content-length", "content-encoding", "retry-after",
                           "x-pagination-page", "x-pagination-page-count", "x-pagination-limit"}:
                    if key in seen or not isinstance(value, str) or len(value) > 256 or any(
                            ord(c) < 32 or ord(c) > 126 for c in value):
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
                    else:
                        safe[key] = value
            if 300 <= response.status < 400:
                raise TransportError("redirect_refused")
            if response.status != 200:
                return Response(response.status, safe, None)
            if (content_type is None or content_type.split(";", 1)[0].strip().lower() != "application/json"
                    or encoding not in (None, "identity")):
                raise TransportError("invalid_response")
            if length is not None and length > self._max_bytes:
                raise TransportError("response_too_large")
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
