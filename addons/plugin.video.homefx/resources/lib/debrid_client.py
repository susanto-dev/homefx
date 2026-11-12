"""Inactive Real-Debrid contracts using injected, bounded HTTPS requests.

Requests must bind relative paths to API_HOST, reject redirects, verify TLS and
bound response bytes/time. No transport, storage or Kodi player is constructed.
Download URLs are private bearer capabilities; never log, persist or share them.
Official contract: https://api.real-debrid.com/ (reviewed 2026-11-12).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import ipaddress
import re
from urllib.parse import unquote, urlencode, urlsplit

API_HOST = "https://api.real-debrid.com"
PREFIX = "/rest/1.0"


class DebridError(Exception):
    def __init__(self, kind, status=None, retry_after=None):
        self.kind, self.status, self.retry_after = kind, status, retry_after
        super().__init__("Debrid request failed: " + kind)


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict = field(default_factory=dict, repr=False)
    body: object = field(default=None, repr=False)


@dataclass(frozen=True, repr=False)
class Download:
    id: str
    url: str
    filename: str
    filesize: int

    def __repr__(self):
        return "Download(<private link>)"


@dataclass(frozen=True, repr=False)
class Account:
    type: str
    premium_seconds: int
    expiration: str

    def __repr__(self):
        return "Account(<private entitlement>)"


def validate_url(value):
    """Conservative syntax only; no DNS lookup or assertion of access rights.

    A future player transport must independently constrain resolved destinations
    and redirects. DNS names here do not prove that their resolved IP is public.
    """
    if not isinstance(value, str) or not 1 <= len(value) <= 8192:
        raise DebridError("invalid_url")
    decoded = value
    for _ in range(4):
        if any(ord(c) <= 32 or ord(c) == 127 or c in "|\\" for c in decoded):
            raise DebridError("invalid_url")
        newer = unquote(decoded)
        if newer == decoded:
            break
        decoded = newer
    else:
        raise DebridError("invalid_url")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (parts.scheme != "https" or not host or parts.username is not None
                or parts.password is not None or parts.fragment or parts.port not in (None, 443)):
            raise ValueError()
        if "%" in parts.netloc or host.endswith("."):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            labels = host.lower().split(".")
            if (len(host) > 253 or len(labels) < 2 or labels[-1].isdigit() or labels[-1] in {"local", "localhost", "internal", "lan"}
                    or all(c in "0123456789." for c in host)
                    or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                               for label in labels)):
                raise ValueError()
        else:
            if not address.is_global:
                raise ValueError()
    except (ValueError, UnicodeError):
        raise DebridError("invalid_url") from None
    return value


def _text(value, maximum):
    return (isinstance(value, str) and 1 <= len(value) <= maximum
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))


def _retry(headers):
    raw = headers.get("retry-after", "")
    if type(raw) not in (str, int) or len(str(raw)) > 128:
        return 60
    try:
        seconds = int(raw)
    except (ValueError, TypeError):
        try:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                return 60
            seconds = int((when - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 60
    return max(1, min(3600, seconds))


def _download(body):
    if (not isinstance(body, dict) or not _text(body.get("id"), 128)
            or not _text(body.get("filename"), 1024)
            or type(body.get("filesize")) is not int or not 0 <= body["filesize"] <= 2**63 - 1):
        raise DebridError("invalid_response")
    return Download(body["id"], validate_url(body.get("download")),
                    body["filename"], body["filesize"])


class Client:
    def __init__(self, request, access_token, page_size=100, max_pages=20, max_items=2000):
        if (not _text(access_token, 4096)
                or any(ord(c) < 33 or ord(c) > 126 for c in access_token)):
            raise DebridError("invalid_credentials")
        if (type(page_size) is not int or not 1 <= page_size <= 100
                or type(max_pages) is not int or not 1 <= max_pages <= 100
                or type(max_items) is not int or not 1 <= max_items <= 10000):
            raise DebridError("invalid_bounds")
        self._request, self._token = request, access_token
        self.page_size, self.max_pages, self.max_items = page_size, max_pages, max_items

    def __repr__(self):
        return "Client(<private credentials>)"

    def _call(self, method, path, body=None):
        headers = {"Authorization": "Bearer " + self._token}
        if method == "POST":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            response = self._request(method, PREFIX + path, headers, body)
        except Exception:
            raise DebridError("uncertain" if method == "POST" else "transport") from None
        if (type(getattr(response, "status", None)) is not int
                or not isinstance(getattr(response, "headers", None), dict)
                or not hasattr(response, "body")):
            raise DebridError("uncertain" if method == "POST" else "invalid_response")
        status = response.status
        normalized = {}
        for key, value in response.headers.items():
            if not isinstance(key, str) or key.lower() in normalized:
                raise DebridError("uncertain" if method == "POST" else "invalid_response")
            normalized[key.lower()] = value
        if status == 429:
            raise DebridError("rate_limit", status, _retry(normalized))
        if status in (401, 403):
            raise DebridError("reauthenticate" if status == 401 else "permission", status)
        if status != 200:
            kind = "uncertain" if method == "POST" and status >= 500 else "service"
            raise DebridError(kind, status)
        return response.body, normalized

    def account(self):
        body, _ = self._call("GET", "/user")
        if (not isinstance(body, dict) or type(body.get("type")) is not str
                or body["type"] not in {"premium", "free"}
                or type(body.get("premium")) is not int or not 0 <= body["premium"] <= 2**63 - 1
                or not _text(body.get("expiration"), 64)):
            raise DebridError("invalid_response")
        try:
            expiration = datetime.fromisoformat(body["expiration"].replace("Z", "+00:00"))
            if expiration.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise DebridError("invalid_response") from None
        return Account(body["type"], body["premium"], expiration.isoformat())

    def downloads(self):
        """Bounded complete traversal, not an atomic server snapshot or catalogue.

        Missing/changing totals and duplicate IDs fail rather than silently
        returning a truncated list. A same-size server reorder cannot be detected.
        """
        result, seen, total = [], set(), None
        for page in range(1, self.max_pages + 1):
            body, headers = self._call("GET", "/downloads?" + urlencode(
                {"page": page, "limit": self.page_size}))
            raw = headers.get("x-total-count")
            if (type(raw) not in (str, int) or not re.fullmatch(r"[0-9]{1,8}", str(raw))
                    or not isinstance(body, list) or len(body) > self.page_size):
                raise DebridError("invalid_pagination")
            count = int(raw)
            if count > self.max_items or count > self.page_size * self.max_pages:
                raise DebridError("result_limit")
            if total is not None and count != total:
                raise DebridError("changed_results")
            total = count
            if len(body) != min(self.page_size, total - len(result)):
                raise DebridError("invalid_pagination")
            for item in body:
                entry = _download(item)
                if entry.id in seen:
                    raise DebridError("changed_results")
                seen.add(entry.id)
                result.append(entry)
            if len(result) == total:
                return tuple(result)
        raise DebridError("result_limit")

    def unrestrict(self, link):
        """One explicit link-resolution attempt; no retry, remote traffic or discovery."""
        link = validate_url(link)
        body, _ = self._call("POST", "/unrestrict/link", {"link": link})
        try:
            # Alternative/multi-link responses require an explicit selection contract.
            if isinstance(body, dict) and body.get("alternative"):
                raise DebridError("selection_required")
            return _download(body)
        except DebridError:
            # A successful response may already represent a server-side operation.
            raise DebridError("uncertain") from None
