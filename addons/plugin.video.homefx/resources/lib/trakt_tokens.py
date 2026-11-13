"""Private-profile token persistence with durable, single-use refresh claims.

This is not a vault: code running as the Kodi user and profile backups can read
credentials. Disconnect clears active records, not forensic SQLite/backup copies.
Filesystem checks assume ancestors are not concurrently replaced by another
process with the same permissions. A future live integration must also offer
service-side revocation guidance.
"""
from contextlib import closing
from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid

from .trakt_auth import AuthError, TokenSet, _number


_MAX_GENERATION = 2 ** 63 - 1


@dataclass(frozen=True, repr=False)
class Snapshot:
    state: str
    generation: int
    tokens: object = field(repr=False)

    def __repr__(self):
        return "Snapshot(state={!r}, generation={!r}, tokens=<redacted>)".format(
            self.state, self.generation)


@dataclass(frozen=True, repr=False)
class RefreshClaim:
    owner: str = field(repr=False)
    generation: int
    tokens: TokenSet = field(repr=False)

    def __repr__(self):
        return "RefreshClaim(<redacted>)"


def _generation(value, optional=False):
    if optional and value is None:
        return
    if type(value) is not int or not 0 <= value <= _MAX_GENERATION:
        raise AuthError("invalid_store_configuration")


def _tokens(tokens):
    try:
        if not isinstance(tokens, TokenSet):
            raise ValueError()
        TokenSet(tokens.access_token, tokens.refresh_token, tokens.expires_at)
    except (AuthError, AttributeError, TypeError, ValueError, OverflowError):
        raise AuthError("invalid_token_response") from None


class TokenStore:
    """Each instance opens short transactions; claims survive process death.

    A competing refresh returns busy (None), never a token to retry. An abandoned
    claim expires into reauthentication; it is never reclaimed with the old token.
    Private file permissions require POSIX (Android/Linux/macOS). Other hosts
    fail closed. SQLite must exist in the target interpreter (device test pending).
    """
    def __init__(self, profile_directory, clock=time.time, claim_ttl=120):
        if os.name != "posix" or not hasattr(os, "fchmod"):
            raise AuthError("token_store_platform_unsupported")
        if not callable(clock) or not _number(claim_ttl, 1, 600):
            raise AuthError("invalid_store_configuration")
        self._clock, self._ttl = clock, claim_ttl
        self._now()
        try:
            self._directory = Path(profile_directory).absolute() / "trakt"
            self._path = self._directory / "tokens.sqlite3"
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
                self._schema(conn)
                self._row(conn)  # Validate existing records without changing them.
        except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
            raise AuthError("token_store_unavailable") from None

    @staticmethod
    def _initialize(conn):
        conn.execute("CREATE TABLE credential ("
                     "id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL, "
                     "state TEXT NOT NULL, owner TEXT, deadline REAL, "
                     "access TEXT, refresh TEXT, expires REAL)")
        conn.execute("INSERT INTO credential(id,generation,state) VALUES(1,0,'disconnected')")
        conn.commit()

    def __repr__(self):
        return "TokenStore(<private profile>)"

    def _now(self):
        try:
            value = self._clock()
            if not _number(value, 0, 10 ** 12 - 600):
                raise ValueError()
            return value
        except Exception:
            raise AuthError("invalid_store_clock") from None

    def _safe_paths(self, require_file=False):
        for path in (self._directory,) + tuple(self._directory.parents):
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(info.st_mode):
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
                    ("deadline", "REAL", 0, None, 0), ("access", "TEXT", 0, None, 0),
                    ("refresh", "TEXT", 0, None, 0), ("expires", "REAL", 0, None, 0)]
        if [row[1:] for row in conn.execute("PRAGMA table_info(credential)")] != expected:
            raise AuthError("token_store_invalid")

    def _transaction(self, operation):
        conn = None
        try:
            self._now()  # Reject invalid clocks before opening storage.
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            now = self._now()  # Lock contention must not extend a refresh deadline.
            self._schema(conn)
            result = operation(conn, now)
            conn.commit()
            return result
        except (sqlite3.Error, OSError, ValueError, TypeError, OverflowError):
            raise AuthError("token_store_unavailable") from None
        finally:
            if conn is not None:
                conn.close()  # Rolls back failed transactions, including validation failures.

    @staticmethod
    def _row(conn, now=None):
        rows = conn.execute("SELECT id,generation,state,owner,deadline,access,refresh,expires "
                            "FROM credential LIMIT 2").fetchall()
        try:
            if len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] != 1:
                raise ValueError()
            row = rows[0][1:]
            _generation(row[0])
            if row[1] not in ("ready", "refreshing", "disconnected", "reauth"):
                raise ValueError()
            if row[1] == "ready":
                if row[2] is not None or row[3] is not None:
                    raise ValueError()
                TokenSet(row[4], row[5], row[6])
            else:
                if any(value is not None for value in row[4:]):
                    raise ValueError()
                if row[1] == "refreshing":
                    if (type(row[2]) is not str or not re.fullmatch(r"[a-f0-9]{32}", row[2])
                            or not _number(row[3], 0, 10 ** 12)):
                        raise ValueError()
                    if now is not None and row[3] <= now:
                        conn.execute("UPDATE credential SET state='reauth',owner=NULL,deadline=NULL WHERE id=1")
                        row = (row[0], "reauth", None, None, None, None, None)
                elif row[2] is not None or row[3] is not None:
                    raise ValueError()
            return row
        except (AuthError, ValueError, TypeError, OverflowError):
            raise AuthError("token_store_invalid") from None

    @staticmethod
    def _advance(row):
        if row[0] == _MAX_GENERATION:
            raise AuthError("token_store_generation_exhausted")

    @staticmethod
    def _claim(claim):
        try:
            if (not isinstance(claim, RefreshClaim) or type(claim.owner) is not str
                    or not re.fullmatch(r"[a-f0-9]{32}", claim.owner)):
                raise ValueError()
            _generation(claim.generation)
            _tokens(claim.tokens)
        except (AuthError, AttributeError, ValueError, TypeError, OverflowError):
            raise AuthError("invalid_store_claim") from None

    def snapshot(self):
        def read(conn, now):
            row = self._row(conn, now)
            tokens = TokenSet(row[4], row[5], row[6]) if row[1] == "ready" else None
            return Snapshot(row[1], row[0], tokens)
        return self._transaction(read)

    def install(self, tokens, expected_generation=None):
        """Replace tokens, optionally only if a login still owns this generation."""
        _tokens(tokens)
        _generation(expected_generation, optional=True)
        def write(conn, now):
            row = self._row(conn)
            if expected_generation is not None and row[0] != expected_generation:
                return False
            self._advance(row)
            conn.execute("UPDATE credential SET generation=generation+1,state='ready',"
                         "owner=NULL,deadline=NULL,access=?,refresh=?,expires=? WHERE id=1",
                         (tokens.access_token, tokens.refresh_token, tokens.expires_at))
            return True
        return self._transaction(write)

    def disconnect(self, expected_generation=None):
        """Clear local credentials; conditional callers cannot erase a newer login."""
        _generation(expected_generation, optional=True)
        def clear(conn, now):
            row = self._row(conn)
            if expected_generation is not None and row[0] != expected_generation:
                return False
            self._advance(row)
            conn.execute("UPDATE credential SET generation=generation+1,state='disconnected',"
                         "owner=NULL,deadline=NULL,access=NULL,refresh=NULL,expires=NULL WHERE id=1")
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
            tokens = TokenSet(row[4], row[5], row[6])
            conn.execute("UPDATE credential SET state='refreshing',owner=?,deadline=?,"
                         "access=NULL,refresh=NULL,expires=NULL WHERE id=1", (owner, now + self._ttl))
            return RefreshClaim(owner, row[0], tokens)
        return self._transaction(claim)

    def complete_refresh(self, claim, tokens):
        self._claim(claim)
        _tokens(tokens)
        def complete(conn, now):
            row = self._row(conn, now)
            if (row[0], row[1], row[2]) != (claim.generation, "refreshing", claim.owner):
                return False
            self._advance(row)
            conn.execute("UPDATE credential SET generation=generation+1,state='ready',"
                         "owner=NULL,deadline=NULL,access=?,refresh=?,expires=? WHERE id=1",
                         (tokens.access_token, tokens.refresh_token, tokens.expires_at))
            return True
        return self._transaction(complete)

    def fail_refresh(self, claim):
        self._claim(claim)
        def fail(conn, now):
            row = self._row(conn)
            if (row[0], row[1], row[2]) == (claim.generation, "refreshing", claim.owner):
                conn.execute("UPDATE credential SET state='reauth',owner=NULL,deadline=NULL,"
                             "access=NULL,refresh=NULL,expires=NULL WHERE id=1")
        self._transaction(fail)
