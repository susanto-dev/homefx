"""Private-profile token persistence with durable, single-use refresh claims.

This is not a vault: code running as the Kodi user and profile backups can read
credentials. Disconnect clears active records, not forensic SQLite/backup copies.
A future live integration must also offer service-side revocation guidance.
"""
from contextlib import closing
from dataclasses import dataclass, field
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .trakt_auth import AuthError, TokenSet, _number


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
        if not _number(claim_ttl, 1, 600):
            raise AuthError("invalid_store_configuration")
        self._clock = clock
        self._ttl = claim_ttl
        self._directory = Path(profile_directory) / "trakt"
        self._path = self._directory / "tokens.sqlite3"
        try:
            if self._directory.is_symlink():
                raise OSError("unsafe directory")
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(str(self._directory), 0o700)
            if self._path.is_symlink():
                raise OSError("unsafe file")
            flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(str(self._path), flags, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            with closing(self._connect()) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS credential ("
                             "id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL, "
                             "state TEXT NOT NULL, owner TEXT, deadline REAL, "
                             "access TEXT, refresh TEXT, expires REAL)")
                conn.execute("INSERT OR IGNORE INTO credential(id,generation,state) "
                             "VALUES(1,0,'disconnected')")
                conn.commit()
        except (OSError, sqlite3.Error):
            raise AuthError("token_store_unavailable") from None

    def __repr__(self):
        return "TokenStore(<private profile>)"

    def _connect(self):
        conn = sqlite3.connect(str(self._path), timeout=2)
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA secure_delete=ON")
        return conn

    def _transaction(self, operation):
        conn = None
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            result = operation(conn)
            conn.commit()
            return result
        except (sqlite3.Error, OSError):
            if conn is not None:
                conn.rollback()
            raise AuthError("token_store_unavailable") from None
        finally:
            if conn is not None:
                conn.close()

    def _expire(self, conn):
        conn.execute("UPDATE credential SET state='reauth',owner=NULL,deadline=NULL,"
                     "access=NULL,refresh=NULL,expires=NULL WHERE id=1 "
                     "AND state='refreshing' AND deadline<=?", (self._clock(),))

    def snapshot(self):
        def read(conn):
            self._expire(conn)
            row = conn.execute("SELECT generation,state,access,refresh,expires "
                               "FROM credential WHERE id=1").fetchone()
            tokens = TokenSet(row[2], row[3], row[4]) if row[1] == "ready" else None
            return Snapshot(row[1], row[0], tokens)
        return self._transaction(read)

    def install(self, tokens, expected_generation=None):
        """Replace tokens, optionally only if a login still owns this generation."""
        if not isinstance(tokens, TokenSet):
            raise AuthError("invalid_token_response")
        if expected_generation is not None and (type(expected_generation) is not int or
                                                expected_generation < 0):
            raise AuthError("invalid_store_configuration")
        def write(conn):
            query = ("UPDATE credential SET generation=generation+1,state='ready',"
                     "owner=NULL,deadline=NULL,access=?,refresh=?,expires=? WHERE id=1")
            parameters = (tokens.access_token, tokens.refresh_token, tokens.expires_at)
            if expected_generation is not None:
                query += " AND generation=?"
                parameters += (expected_generation,)
            return conn.execute(query, parameters).rowcount == 1
        return self._transaction(write)

    def disconnect(self, expected_generation=None):
        """Clear local credentials; conditional callers cannot erase a newer login."""
        if expected_generation is not None and (type(expected_generation) is not int or
                                                expected_generation < 0):
            raise AuthError("invalid_store_configuration")
        def clear(conn):
            query = ("UPDATE credential SET generation=generation+1,state='disconnected',"
                     "owner=NULL,deadline=NULL,access=NULL,refresh=NULL,expires=NULL WHERE id=1")
            parameters = ()
            if expected_generation is not None:
                query += " AND generation=?"
                parameters = (expected_generation,)
            return conn.execute(query, parameters).rowcount == 1
        return self._transaction(clear)

    def claim_refresh(self, expected_generation):
        def claim(conn):
            self._expire(conn)
            row = conn.execute("SELECT generation,state,access,refresh,expires "
                               "FROM credential WHERE id=1").fetchone()
            if row[0] != expected_generation or row[1] != "ready":
                return None
            tokens = TokenSet(row[2], row[3], row[4])
            owner = uuid.uuid4().hex
            conn.execute("UPDATE credential SET state='refreshing',owner=?,deadline=?,"
                         "access=NULL,refresh=NULL,expires=NULL WHERE id=1",
                         (owner, self._clock() + self._ttl))
            return RefreshClaim(owner, row[0], tokens)
        return self._transaction(claim)

    def complete_refresh(self, claim, tokens):
        if not isinstance(tokens, TokenSet):
            raise AuthError("invalid_token_response")
        def complete(conn):
            self._expire(conn)
            cursor = conn.execute("UPDATE credential SET generation=generation+1,state='ready',"
                                  "owner=NULL,deadline=NULL,access=?,refresh=?,expires=? "
                                  "WHERE id=1 AND state='refreshing' AND owner=? AND generation=?",
                                  (tokens.access_token, tokens.refresh_token, tokens.expires_at,
                                   claim.owner, claim.generation))
            return cursor.rowcount == 1
        return self._transaction(complete)

    def fail_refresh(self, claim):
        def fail(conn):
            conn.execute("UPDATE credential SET state='reauth',owner=NULL,deadline=NULL,"
                         "access=NULL,refresh=NULL,expires=NULL WHERE id=1 "
                         "AND state='refreshing' AND owner=? AND generation=?",
                         (claim.owner, claim.generation))
        self._transaction(fail)
