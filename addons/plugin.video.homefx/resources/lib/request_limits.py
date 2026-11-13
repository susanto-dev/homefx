"""Inactive private cross-invocation request limits; no account data or network I/O.

Real-Debrid permits at most 250 issued attempts per rolling 60 seconds per local
profile here. Trakt has no guessed numeric quota: only validated 429 cooldowns are
shared. Different devices/profiles are not coordinated. This database is not a
security boundary against other code running as Kodi or restored profile backups.
"""
from contextlib import closing
from email.utils import parsedate_to_datetime
import math
import os
from pathlib import Path
import sqlite3
import stat
import time

PROVIDERS = ("trakt", "realdebrid")
MAX_ATTEMPTS = 250
WINDOW = 60
MAX_WAIT = 3600
MAX_DEADLINE = 10 ** 12
MAX_CLOCK = MAX_DEADLINE - MAX_WAIT


class LimitError(Exception):
    """A fixed category without request, account or filesystem details."""


def _number(value, maximum=10 ** 12):
    return (type(value) in (int, float) and 0 <= value <= maximum
            and math.isfinite(value))


def _retry_after(headers, now):
    # A malformed or missing Retry-After never removes the default cooldown.
    values = [value for key, value in headers.items()
              if isinstance(key, str) and key.lower() == "retry-after"]
    if len(values) != 1:
        return 60
    raw = values[0]
    if type(raw) not in (str, int):
        return 60
    if type(raw) is str:
        token = raw.strip()
        digits = token[1:] if token.startswith(("+", "-")) else token
        if len(digits) > 15 and digits.isascii() and digits.isdecimal():
            # Saturate huge valid durations without converting unbounded integers.
            return 1 if token.startswith("-") else MAX_DEADLINE - now
        if len(raw) > 128:
            return 60
    try:
        delay = int(raw)
    except (ValueError, TypeError, OverflowError):
        try:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                return 60
            delay = when.timestamp() - now
            if not math.isfinite(delay):
                return 60
        except (ValueError, TypeError, OverflowError, IndexError, OSError):
            return 60
    return max(1, min(MAX_DEADLINE - now, math.ceil(delay)))


class RequestLimits:
    """Atomic reservations and 429 cooldowns, scoped to a provider and local profile.

    reserve() returns 0 for a newly counted attempt or a positive wait in seconds.
    Reserve immediately before network I/O; failed issued attempts still count.
    Blocked calls do not add attempts or extend cooldowns. observe() records only
    429 responses. This helper never sleeps, queues work, retries or opens a socket.
    There is intentionally no account-based reset or credential association.
    """
    def __init__(self, profile_directory, provider, clock=time.time):
        if (type(provider) is not str or provider not in PROVIDERS or not callable(clock)):
            raise LimitError("invalid_limit_configuration")
        if os.name != "posix" or not hasattr(os, "fchmod"):
            raise LimitError("limit_store_platform_unsupported")
        self.provider, self._clock = provider, clock
        self._directory = Path(profile_directory).absolute() / "limits"
        self._path = self._directory / "requests.sqlite3"
        try:
            self._safe_paths()
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._safe_paths()
            os.chmod(str(self._directory), 0o700)
            exists = self._path.exists()
            flags = os.O_CREAT | os.O_RDWR | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(str(self._path), flags, 0o600)
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise OSError()
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            with closing(self._connect()) as connection:
                if not exists:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("CREATE TABLE state (provider TEXT PRIMARY KEY, "
                                       "cooldown REAL NOT NULL, last REAL NOT NULL)")
                    connection.execute("CREATE TABLE issued (provider TEXT NOT NULL, stamp REAL NOT NULL)")
                    connection.executemany("INSERT INTO state VALUES (?,0,0)",
                                           [(name,) for name in PROVIDERS])
                    connection.commit()
                self._read(connection)
        except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
            raise LimitError("limit_store_unavailable") from None

    def __repr__(self):
        return "RequestLimits(provider={!r}, private state)".format(self.provider)

    def _safe_paths(self):
        if any(path.is_symlink() for path in (self._directory,) + tuple(self._directory.parents)):
            raise OSError()
        if self._directory.exists() and not self._directory.is_dir():
            raise OSError()
        for path in (self._path,) + tuple(Path(str(self._path) + suffix)
                                         for suffix in ("-journal", "-wal", "-shm")):
            if path.is_symlink():
                raise OSError()
            if path.exists():
                info = path.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise OSError()

    def _connect(self):
        self._safe_paths()
        connection = sqlite3.connect(str(self._path), timeout=2)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA journal_mode=DELETE")
            return connection
        except sqlite3.Error:
            connection.close()
            raise

    @staticmethod
    def _read(connection):
        rows = connection.execute("SELECT provider,cooldown,last FROM state LIMIT 3").fetchall()
        if len(rows) != len(PROVIDERS) or {row[0] for row in rows} != set(PROVIDERS):
            raise LimitError("limit_store_invalid")
        states = {}
        for provider, cooldown, last in rows:
            if not _number(cooldown, MAX_DEADLINE) or not _number(last, MAX_CLOCK):
                raise LimitError("limit_store_invalid")
            states[provider] = (cooldown, last)
        issued = connection.execute("SELECT provider,stamp FROM issued LIMIT 251").fetchall()
        if len(issued) > MAX_ATTEMPTS or any(
                provider != "realdebrid" or not _number(stamp, MAX_CLOCK)
                or stamp > states["realdebrid"][1] for provider, stamp in issued):
            raise LimitError("limit_store_invalid")
        return states, [stamp for _, stamp in issued]

    def _transaction(self, operation):
        connection = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            # Read time only after acquiring the serialization lock, so waiting
            # callers do not manufacture a backwards-clock event from old readings.
            try:
                now = self._clock()
            except Exception:
                raise LimitError("invalid_limit_clock") from None
            if not _number(now, MAX_CLOCK):
                raise LimitError("invalid_limit_clock")
            states, issued = self._read(connection)
            cooldown, last = states[self.provider]
            if now < last:
                raise LimitError("invalid_limit_clock")
            result = operation(connection, now, cooldown, issued)
            connection.execute("UPDATE state SET last=? WHERE provider=?", (now, self.provider))
            connection.commit()
            return result
        except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
            raise LimitError("limit_store_unavailable") from None
        finally:
            if connection is not None:
                connection.close()  # Any failed transaction is rolled back.

    def reserve(self):
        def reserve(connection, now, cooldown, issued):
            wait = max(0, cooldown - now)
            if self.provider == "realdebrid":
                connection.execute("DELETE FROM issued WHERE stamp<=?", (now - WINDOW,))
                remaining = [stamp for stamp in issued if stamp > now - WINDOW]
                if len(remaining) >= MAX_ATTEMPTS:
                    wait = max(wait, min(remaining) + WINDOW - now)
                if wait <= 0:
                    connection.execute("INSERT INTO issued VALUES (?,?)", (self.provider, now))
            return max(1, min(MAX_WAIT, math.ceil(wait))) if wait > 0 else 0
        return self._transaction(reserve)

    def observe(self, status, headers):
        if type(status) is not int or not 100 <= status <= 599 or not isinstance(headers, dict):
            raise LimitError("invalid_limit_response")
        if status != 429:
            return

        def observe(connection, now, cooldown, issued):
            deadline = max(cooldown, now + _retry_after(headers, now))
            connection.execute("UPDATE state SET cooldown=? WHERE provider=?", (deadline, self.provider))
        self._transaction(observe)
