"""Inactive explicit service assembly; importing this module opens no storage/network."""
from dataclasses import dataclass, field
import http.client
import math
from pathlib import Path
import re
import stat
import time
from urllib.parse import urlsplit

from . import debrid_auth, debrid_session, debrid_store, debrid_transport
from . import trakt_auth, trakt_library, trakt_preferences, trakt_session, trakt_tokens, trakt_transport
from .request_limits import RequestLimits


class SetupError(ValueError):
    """Fixed setup categories without profile paths, identity values or raw errors."""


@dataclass(frozen=True, repr=False)
class TraktRuntime:
    session: object = field(repr=False)
    library: object = field(repr=False)

    def __repr__(self):
        return "TraktRuntime(<private account assembly>)"

    def disconnect(self, expected_generation=None):
        return self.library.disconnect(expected_generation=expected_generation)


@dataclass(frozen=True, repr=False)
class DebridRuntime:
    session: object = field(repr=False)

    def __repr__(self):
        return "DebridRuntime(<private account assembly>)"

    def disconnect(self, expected_generation=None):
        return self.session.disconnect(expected_generation=expected_generation)


def _redirect(value):
    # Validate syntax, not registration. Registered URN/custom schemes can be
    # legitimate; no callback server or default redirect is invented here.
    if (type(value) is not str or not trakt_auth._text(value, 2048)
            or "\\" in value or re.search(r"%(?![0-9A-Fa-f]{2})", value)):
        return False
    try:
        parsed = urlsplit(value)
        if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*", parsed.scheme)
                or parsed.fragment or parsed.username is not None or parsed.password is not None
                or not (parsed.netloc or parsed.path)):
            return False
        if parsed.scheme in {"https", "http"}:
            if not parsed.hostname:
                return False
            parsed.port  # Reject malformed numeric ports without opening the URI.
        return True
    except ValueError:
        return False


def _number(value, minimum=0, maximum=10 ** 12 - 3600):
    return type(value) in (int, float) and minimum <= value <= maximum and math.isfinite(value)


def _profile(profile, provider):
    if not isinstance(profile, (str, Path)) or not str(profile) or "\0" in str(profile):
        raise SetupError("invalid_runtime_configuration")
    path = Path(profile)
    if not path.is_absolute() or path == path.parent or ".." in path.parts:
        raise SetupError("invalid_runtime_configuration")
    # Existing files are checked before any component constructor can create a
    # directory or open SQLite. Parents must remain quiescent during assembly.
    paths = [path, path / provider, path / "limits"]
    if any(part.is_symlink() for target in paths for part in (target,) + tuple(target.parents)):
        raise SetupError("invalid_runtime_profile")
    if any(target.exists() and not target.is_dir() for target in paths):
        raise SetupError("invalid_runtime_profile")
    files = [path / "limits" / "requests.sqlite3"]
    files += ([path / "trakt" / name for name in ("tokens.sqlite3", "preferences.sqlite3")]
              if provider == "trakt" else [path / "realdebrid" / "credentials.sqlite3"])
    for database in files:
        for suffix in ("", "-journal", "-wal", "-shm"):
            target = Path(str(database) + suffix)
            try:
                info = target.lstat()
            except FileNotFoundError:
                continue  # Initial database creation and transient sidecar removal.
            links = (0, 1) if suffix else (1,)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink not in links:
                raise SetupError("invalid_runtime_profile")
    return path


def _preflight(profile, provider, clock, monotonic, cancelled, connection_factory):
    if not all(callable(callback) for callback in (clock, monotonic, cancelled, connection_factory)):
        raise SetupError("invalid_runtime_configuration")
    try:
        wall, elapsed, stopped = clock(), monotonic(), cancelled()
        if (not _number(wall, 1, 10 ** 12 - 366 * 86400)
                or not _number(elapsed) or type(stopped) is not bool):
            raise SetupError("invalid_runtime_configuration")
        if stopped:
            raise SetupError("runtime_cancelled")
        return _profile(profile, provider)
    except SetupError:
        raise
    except Exception:
        raise SetupError("invalid_runtime_configuration") from None


def build_trakt(profile, client_id, redirect_uri, *, clock=time.time,
                monotonic=time.monotonic, cancelled=lambda: False,
                connection_factory=http.client.HTTPSConnection):
    """Explicitly open local stores and assemble read-only services, never sign in.

    Callbacks are trusted bounded code, not settings or service responses. The public Preview
    menu does not invoke this factory; the explicit Development video candidate does. A failure may leave empty private stores, but never
    causes login, refresh, network access or cleanup of unrelated profile files.
    """
    if type(client_id) is not str or not trakt_auth._text(client_id, 256) or not _redirect(redirect_uri):
        raise SetupError("invalid_runtime_configuration")
    path = _preflight(profile, "trakt", clock, monotonic, cancelled, connection_factory)
    try:
        limits = RequestLimits(path, "trakt", clock=clock)
        transport = trakt_transport.Transport(cancelled=cancelled, clock=monotonic,
            connection_factory=connection_factory, rate_limits=limits)
        store = trakt_tokens.TokenStore(path, clock=clock)
        preferences = trakt_preferences.AccountPreferences(path)
        session = trakt_session.Session(store, transport.oauth_request, transport.api_request,
            client_id, redirect_uri, clock=clock, monotonic=monotonic)
        library = trakt_library.Library(session, preferences=preferences,
                                      cache=trakt_library.MemoryCache(clock=monotonic))
        return TraktRuntime(session, library)
    except Exception:
        raise SetupError("runtime_setup_failed") from None


def build_debrid(profile, public_client_id, *, clock=time.time,
                 monotonic=time.monotonic, cancelled=lambda: False,
                 connection_factory=http.client.HTTPSConnection, pending_response=None):
    """Assemble provider storage/session with a mandatory shared request budget.

    No default pending-authorization classifier is guessed. The optional callable
    is trusted, separately verified code; it is not a setting or activation flag.
    """
    if (not debrid_auth._text(public_client_id, 256)
            or (pending_response is not None and not callable(pending_response))):
        raise SetupError("invalid_runtime_configuration")
    path = _preflight(profile, "realdebrid", clock, monotonic, cancelled, connection_factory)
    try:
        limits = RequestLimits(path, "realdebrid", clock=clock)
        transport = debrid_transport.Transport(cancelled=cancelled, clock=monotonic,
            connection_factory=connection_factory, rate_limits=limits)
        store = debrid_store.CredentialStore(path, clock=clock)
        session = debrid_session.Session(store, transport.oauth_request, transport.api_request,
            public_client_id, clock=clock, monotonic=monotonic, pending_response=pending_response)
        return DebridRuntime(session)
    except Exception:
        raise SetupError("runtime_setup_failed") from None
