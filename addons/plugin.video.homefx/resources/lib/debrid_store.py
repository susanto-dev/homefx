"""Private provider credentials and durable refresh ownership, inactive in Kodi.

This is not encryption or a vault. Code running as the Kodi user and profile
backups can read secrets; local disconnect is not remote revocation or forensic
erasure. Filesystem checks reject unsafe existing paths, but cannot protect from
another process with the same filesystem permissions replacing paths concurrently.
"""
from contextlib import closing
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid

from .debrid_auth import AuthError, Credentials, Tokens


@dataclass(frozen=True, repr=False)
class Snapshot:
    state: str
    generation: int
    credentials: object = field(repr=False)
    tokens: object = field(repr=False)

    def __repr__(self):
        return "Snapshot(state={!r}, generation={!r}, credentials=<redacted>)".format(
            self.state, self.generation)


@dataclass(frozen=True, repr=False)
class RefreshClaim:
    owner: str = field(repr=False)
    generation: int
    credentials: Credentials = field(repr=False)
    tokens: Tokens = field(repr=False)

    def __repr__(self):
        return "RefreshClaim(<redacted>)"


def _number(value, low, high):
    return (type(value) in (int, float) and low <= value <= high
            and math.isfinite(value))


def _generation(value, optional=False):
    if optional and value is None:
        return
    if type(value) is not int or not 0 <= value <= 2 ** 63 - 1:
        raise AuthError("invalid_store_configuration")


def _material(credentials, tokens):
    if not isinstance(credentials, Credentials) or not isinstance(tokens, Tokens):
        raise AuthError("invalid_store_credentials")
    # Revalidate even objects supplied by other application code.
    Credentials(credentials.client_id, credentials.client_secret)
    Tokens(tokens.access_token, tokens.refresh_token, tokens.expires_at)


class CredentialStore:
    """Short SQLite transactions; a consumed refresh claim is never reclaimed.

    Claiming clears every secret in the database, returning them only to the claim
    owner in memory. Expired or failed claims require fresh authorization. Separate
    instances coordinate via SQLite, not process-local locks. The Android filesystem
    and embedded SQLite still need device testing before live activation.
    """
    def __init__(self, profile_directory, clock=time.time, claim_ttl=120):
        if os.name != "posix" or not hasattr(os, "fchmod"):
            raise AuthError("credential_store_platform_unsupported")
        if not callable(clock) or not _number(claim_ttl, 1, 600):
            raise AuthError("invalid_store_configuration")
        self._clock, self._ttl = clock, claim_ttl
        self._now()
        try:
            self._directory = Path(profile_directory).absolute() / "realdebrid"
            self._path = self._directory / "credentials.sqlite3"
            self._safe_paths()
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._safe_paths()
            os.chmod(str(self._directory), 0o700)
            flags = os.O_RDWR | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(str(self._path), flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                descriptor = os.open(str(self._path), flags)
                created = False
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise OSError()
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            with closing(self._connect()) as conn:
                if created:
                    self._initialize(conn)
            self.snapshot()  # Reject malformed existing records rather than repairing them.
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise AuthError("credential_store_unavailable") from None

    @staticmethod
    def _initialize(conn):
        conn.execute("CREATE TABLE credential ("
                     "id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL, "
                     "state TEXT NOT NULL, owner TEXT, deadline REAL, client_id TEXT, "
                     "client_secret TEXT, access TEXT, refresh TEXT, expires REAL)")
        conn.execute("INSERT INTO credential(id,generation,state) "
                     "VALUES(1,0,'disconnected')")
        conn.commit()

    def __repr__(self):
        return "CredentialStore(<private provider profile>)"

    def _now(self):
        try:
            value = self._clock()
        except Exception:
            raise AuthError("invalid_store_clock") from None
        if not _number(value, 0, 10 ** 12 - 600):
            raise AuthError("invalid_store_clock")
        return value

    def _safe_paths(self, require_file=False):
        if any(path.is_symlink() for path in (self._directory,) + tuple(self._directory.parents)):
            raise OSError()
        if self._directory.exists() and not self._directory.is_dir():
            raise OSError()
        for path in (self._path,) + tuple(Path(str(self._path) + suffix)
                                         for suffix in ("-journal", "-wal", "-shm")):
            try:
                info = path.lstat()
            except FileNotFoundError:
                if require_file and path == self._path:
                    raise
                continue
            # A normal SQLite commit can unlink a sidecar during stat lookup.
            # The mandatory database must still exist with exactly one link.
            links = (1,) if path == self._path else (0, 1)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink not in links:
                raise OSError()

    def _connect(self):
        self._safe_paths(require_file=True)
        conn = sqlite3.connect(self._path.as_uri() + "?mode=rw", timeout=2, uri=True)
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA secure_delete=ON")
            return conn
        except sqlite3.Error:
            conn.close()
            raise

    @staticmethod
    def _schema(conn):
        expected = [("id", "INTEGER", 0, None, 1), ("generation", "INTEGER", 1, None, 0),
                    ("state", "TEXT", 1, None, 0), ("owner", "TEXT", 0, None, 0),
                    ("deadline", "REAL", 0, None, 0), ("client_id", "TEXT", 0, None, 0),
                    ("client_secret", "TEXT", 0, None, 0), ("access", "TEXT", 0, None, 0),
                    ("refresh", "TEXT", 0, None, 0), ("expires", "REAL", 0, None, 0)]
        if [row[1:] for row in conn.execute("PRAGMA table_info(credential)")] != expected:
            raise AuthError("credential_store_invalid")

    def _transaction(self, operation):
        conn = None
        try:
            self._now()  # Reject invalid clocks before opening storage.
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            now = self._now()  # Waiting for a write lock must not extend a refresh claim.
            self._schema(conn)
            result = operation(conn, now)
            conn.commit()
            return result
        except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
            raise AuthError("credential_store_unavailable") from None
        finally:
            if conn is not None:
                conn.close()  # Rolls back any failed transaction.

    def _row(self, conn, now):
        rows = conn.execute("SELECT id,generation,state,owner,deadline,client_id,"
                            "client_secret,access,refresh,expires FROM credential LIMIT 2").fetchall()
        try:
            if len(rows) != 1 or rows[0][0] != 1:
                raise ValueError()
            row = rows[0][1:]
            _generation(row[0])
            state = row[1]
            if state not in ("ready", "refreshing", "disconnected", "reauth"):
                raise ValueError()
            if state == "ready":
                if row[2] is not None or row[3] is not None:
                    raise ValueError()
                Credentials(row[4], row[5])
                Tokens(row[6], row[7], row[8])
            else:
                if any(value is not None for value in row[4:]):
                    raise ValueError()
                if state == "refreshing":
                    if (type(row[2]) is not str or not re.fullmatch(r"[a-f0-9]{32}", row[2])
                            or not _number(row[3], 0, 10 ** 12)):
                        raise ValueError()
                    if row[3] <= now:
                        conn.execute("UPDATE credential SET state='reauth',owner=NULL,deadline=NULL WHERE id=1")
                        row = (row[0], "reauth", None, None, None, None, None, None, None)
                elif row[2] is not None or row[3] is not None:
                    raise ValueError()
            return row
        except (ValueError, TypeError, AuthError):
            raise AuthError("credential_store_invalid") from None

    @staticmethod
    def _advance(row):
        if row[0] == 2 ** 63 - 1:
            raise AuthError("credential_store_generation_exhausted")

    def snapshot(self):
        def read(conn, now):
            row = self._row(conn, now)
            ready = row[1] == "ready"
            return Snapshot(row[1], row[0], Credentials(row[4], row[5]) if ready else None,
                            Tokens(row[6], row[7], row[8]) if ready else None)
        return self._transaction(read)

    def install(self, credentials, tokens, expected_generation=None):
        _material(credentials, tokens)
        _generation(expected_generation, optional=True)
        def write(conn, now):
            row = self._row(conn, now)
            if expected_generation is not None and row[0] != expected_generation:
                return False
            self._advance(row)
            conn.execute("UPDATE credential SET generation=generation+1,state='ready',owner=NULL,"
                         "deadline=NULL,client_id=?,client_secret=?,access=?,refresh=?,expires=? WHERE id=1",
                         (credentials.client_id, credentials.client_secret, tokens.access_token,
                          tokens.refresh_token, tokens.expires_at))
            return True
        return self._transaction(write)

    def disconnect(self, expected_generation=None):
        _generation(expected_generation, optional=True)
        def clear(conn, now):
            row = self._row(conn, now)
            if expected_generation is not None and row[0] != expected_generation:
                return False
            self._advance(row)
            conn.execute("UPDATE credential SET generation=generation+1,state='disconnected',owner=NULL,"
                         "deadline=NULL,client_id=NULL,client_secret=NULL,access=NULL,refresh=NULL,expires=NULL WHERE id=1")
            return True
        return self._transaction(clear)

    def claim_refresh(self, expected_generation):
        _generation(expected_generation)
        def claim(conn, now):
            row = self._row(conn, now)
            if row[0] != expected_generation or row[1] != "ready":
                return None
            self._advance(row)
            owner = uuid.uuid4().hex
            result = RefreshClaim(owner, row[0], Credentials(row[4], row[5]), Tokens(row[6], row[7], row[8]))
            conn.execute("UPDATE credential SET state='refreshing',owner=?,deadline=?,client_id=NULL,"
                         "client_secret=NULL,access=NULL,refresh=NULL,expires=NULL WHERE id=1",
                         (owner, now + self._ttl))
            return result
        return self._transaction(claim)

    @staticmethod
    def _claim(claim):
        if not isinstance(claim, RefreshClaim) or type(claim.owner) is not str or not re.fullmatch(r"[a-f0-9]{32}", claim.owner):
            raise AuthError("invalid_store_claim")
        _generation(claim.generation)
        _material(claim.credentials, claim.tokens)

    def complete_refresh(self, claim, tokens):
        self._claim(claim)
        _material(claim.credentials, tokens)
        def complete(conn, now):
            row = self._row(conn, now)
            if (row[0], row[1], row[2]) != (claim.generation, "refreshing", claim.owner):
                return False
            self._advance(row)
            conn.execute("UPDATE credential SET generation=generation+1,state='ready',owner=NULL,deadline=NULL,"
                         "client_id=?,client_secret=?,access=?,refresh=?,expires=? WHERE id=1",
                         (claim.credentials.client_id, claim.credentials.client_secret,
                          tokens.access_token, tokens.refresh_token, tokens.expires_at))
            return True
        return self._transaction(complete)

    def fail_refresh(self, claim):
        self._claim(claim)
        def fail(conn, now):
            row = self._row(conn, now)
            if (row[0], row[1], row[2]) != (claim.generation, "refreshing", claim.owner):
                return False
            conn.execute("UPDATE credential SET state='reauth',owner=NULL,deadline=NULL WHERE id=1")
            return True
        return self._transaction(fail)
