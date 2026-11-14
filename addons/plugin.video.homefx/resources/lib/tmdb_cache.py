"""Inactive private, bounded TMDB artwork-path cache; no image bytes or account data.

Explicit refresh is separate from cache-only reads. Parent paths must be quiescent;
permissions do not defend against other code running as Kodi or copied backups.
"""
from contextlib import contextmanager
import math
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import time

from .storage_probe import _safe_profile
from .tmdb_artwork import Artwork, ArtworkError, key

FRESH = 7 * 86400
NEGATIVE = 86400
MAX_AGE = 30 * 86400
MAX_ROWS = 1000
MAX_BYTES = 1024 * 1024
LEASE = 15
APPLICATION = 0x48465854


def _time(value):
    if type(value) not in (int, float) or not 1 <= value <= 10**12 or not math.isfinite(value):
        raise ArtworkError()
    return float(value)


def _keys(values):
    if type(values) not in (list, tuple) or len(values) > 2000:
        raise ArtworkError()
    result = []
    for value in values:
        if type(value) not in (list, tuple) or len(value) != 3:
            raise ArtworkError()
        result.append(key(*value))
    return list(dict.fromkeys(result))


class ArtworkCache:
    """At most 1 MiB database plus a bounded rollback journal, and 1,000 rows.

    One short-lived network lease per local cache prevents concurrent rows from
    multiplying requests. Network never runs under a database lock. No background
    worker, periodic timer, image download or global Kodi texture-cache deletion.
    """
    def __init__(self, profile, *, clock=time.time):
        if not callable(clock) or os.name != 'posix' or not hasattr(os, 'fchmod'):
            raise ArtworkError()
        self._clock = clock
        try:
            self._directory = _safe_profile(profile) / 'tmdb-artwork'
            _safe_profile(self._directory)
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            _safe_profile(self._directory)
            os.chmod(self._directory, 0o700)
            self._path = self._directory / 'paths.sqlite3'
            self._paths(missing=True)
            try:
                fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_RDWR
                             | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            except FileExistsError:
                pass
            else:
                try:
                    os.fchmod(fd, 0o600)
                finally:
                    os.close(fd)
            with self._transaction(initialize=True):
                pass
        except Exception:
            raise ArtworkError() from None

    def __repr__(self):
        return 'ArtworkCache(<private local cache>)'

    def _paths(self, missing=False):
        _safe_profile(self._directory)
        if stat.S_IMODE(self._directory.lstat().st_mode) != 0o700:
            raise ArtworkError()
        for suffix in ('-journal', '-wal', '-shm', ''):
            path = Path(str(self._path) + suffix)
            try:
                info = path.lstat()
            except FileNotFoundError:
                if suffix or missing:
                    continue
                raise
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink not in ((0, 1) if suffix else (1,))
                    or stat.S_IMODE(info.st_mode) & 0o077 or suffix in ('-wal', '-shm')
                    or info.st_size > MAX_BYTES + (65536 if suffix else 0)):
                raise ArtworkError()

    @contextmanager
    def _transaction(self, initialize=False):
        conn = None
        try:
            self._paths()
            conn = sqlite3.connect(self._path.as_uri() + '?mode=rw', uri=True, timeout=0.1)
            conn.execute('PRAGMA trusted_schema=OFF')
            conn.execute('PRAGMA cache_size=-128')
            conn.execute('PRAGMA mmap_size=0')
            conn.execute('PRAGMA secure_delete=ON')
            conn.execute('PRAGMA synchronous=FULL')
            if conn.execute('PRAGMA page_size').fetchone() != (4096,):
                raise ArtworkError()
            conn.execute('PRAGMA max_page_count=256')
            if conn.execute('PRAGMA journal_mode').fetchone() != ('delete',):
                raise ArtworkError()
            conn.execute('BEGIN IMMEDIATE')
            self._paths()
            app = conn.execute('PRAGMA application_id').fetchone()[0]
            tables = conn.execute("SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
            if initialize and app == 0 and not tables:
                conn.execute('CREATE TABLE artwork (kind TEXT, ident INTEGER, language TEXT, '
                    'poster TEXT, backdrop TEXT, checked REAL, touched REAL, lease TEXT, until REAL, '
                    'PRIMARY KEY(kind,ident,language))')
                conn.execute('CREATE TABLE control (id INTEGER PRIMARY KEY, cooldown REAL, last REAL)')
                conn.execute('INSERT INTO control VALUES(1,0,0)')
                conn.execute('PRAGMA application_id=' + str(APPLICATION))
                conn.execute('PRAGMA user_version=1')
            elif (app != APPLICATION or conn.execute('PRAGMA user_version').fetchone() != (1,)
                    or sorted(tables) != [('artwork', 'table'), ('control', 'table')]):
                raise ArtworkError()
            if conn.execute('SELECT count(*) FROM artwork').fetchone()[0] > MAX_ROWS:
                raise ArtworkError()
            now = _time(self._clock())
            controls = conn.execute('SELECT id,cooldown,last FROM control LIMIT 2').fetchall()
            if (len(controls) != 1 or controls[0][0] != 1 or any(
                    type(v) not in (int, float) or not 0 <= v <= 10**12
                    or not math.isfinite(v) for v in controls[0][1:])):
                raise ArtworkError()
            _, cooldown, last = controls[0]
            if now < last:
                conn.execute('DELETE FROM artwork')
                cooldown = min(10**12, now + max(60, cooldown - last))
            conn.execute('UPDATE control SET cooldown=?,last=? WHERE id=1', (cooldown, now))
            # A rollback or expired entry cannot resurrect through an old network lease.
            conn.execute('DELETE FROM artwork WHERE (checked>0 AND checked<=?) OR checked>? '
                         'OR (checked=0 AND touched<=?)',
                         (now - MAX_AGE, now, now - MAX_AGE))
            yield conn, now
            conn.commit()
        except Exception:
            if conn is not None:
                conn.rollback()
            raise ArtworkError() from None
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _entry(row, now):
        if row is None:
            return None
        poster, backdrop, checked = row[:3]
        if type(checked) not in (int, float) or checked <= 0 or checked > now:
            return None
        artwork = Artwork(poster, backdrop, now - checked >= FRESH)
        if now - checked >= MAX_AGE or (poster is backdrop is None):
            return None
        return artwork

    def read_many(self, lookups):
        """One bounded transaction, no network; stale paths remain marked, not refreshed."""
        lookups = _keys(lookups)
        result = {}
        with self._transaction() as (conn, now):
            for lookup in lookups:
                row = conn.execute('SELECT poster,backdrop,checked FROM artwork WHERE '
                                   'kind=? AND ident=? AND language=?', lookup).fetchone()
                value = self._entry(row, now)
                if value is not None:
                    result[lookup] = value
                    conn.execute('UPDATE artwork SET touched=? WHERE kind=? AND ident=? AND language=?',
                                 (now,) + lookup)
        return result

    def clear(self):
        """Forget only this cache; outstanding fetches cannot repopulate cleared rows."""
        with self._transaction() as (conn, _):
            conn.execute('DELETE FROM artwork')

    def _eligible(self, lookups):
        # One transaction for the common all-fresh case, rather than one fsync
        # per title. Claims still recheck freshness/limits after this snapshot.
        result = []
        with self._transaction() as (conn, now):
            if conn.execute('SELECT cooldown FROM control').fetchone()[0] > now:
                return result
            if conn.execute("SELECT 1 FROM artwork WHERE lease<>'' AND until>? LIMIT 1", (now,)).fetchone():
                return result
            for lookup in lookups:
                row = conn.execute('SELECT poster,backdrop,checked FROM artwork WHERE '
                                   'kind=? AND ident=? AND language=?', lookup).fetchone()
                if row is not None:
                    self._entry(row, now)
                    poster, backdrop, checked = row
                    ttl = NEGATIVE if poster is backdrop is None else FRESH
                    if type(checked) in (int, float) and checked > 0 and now - checked < ttl:
                        continue
                result.append(lookup)
        return result

    def _claim(self, lookup):
        with self._transaction() as (conn, now):
            if conn.execute('SELECT cooldown FROM control').fetchone()[0] > now:
                return None
            if conn.execute("SELECT 1 FROM artwork WHERE lease<>'' AND until>? LIMIT 1", (now,)).fetchone():
                return None
            row = conn.execute('SELECT poster,backdrop,checked FROM artwork WHERE '
                               'kind=? AND ident=? AND language=?', lookup).fetchone()
            if row is not None:
                poster, backdrop, checked = row
                self._entry(row, now)
                ttl = NEGATIVE if poster is backdrop is None else FRESH
                if type(checked) in (int, float) and checked > 0 and now - checked < ttl:
                    return None
            if row is None:
                conn.execute('DELETE FROM artwork WHERE rowid IN (SELECT rowid FROM artwork '
                             'ORDER BY touched DESC,rowid DESC LIMIT -1 OFFSET ?)', (MAX_ROWS - 1,))
                conn.execute('INSERT INTO artwork VALUES(?,?,?,NULL,NULL,0,?,\'\',0)', lookup + (now,))
            claim = secrets.token_hex(16)
            conn.execute('UPDATE artwork SET lease=?,until=?,touched=? WHERE kind=? AND ident=? AND language=?',
                         (claim, now + LEASE, now) + lookup)
            return claim

    def _finish(self, lookup, claim, value, error):
        with self._transaction() as (conn, now):
            row = conn.execute('SELECT lease,until FROM artwork WHERE kind=? AND ident=? AND language=?', lookup).fetchone()
            # Server-wide outcomes outlive a request's content lease. Even a
            # late 429 must prevent an immediate retry; a shorter later wait
            # must not shorten a cooldown already observed by another caller.
            if error is not None and error.category in ('limited', 'unauthorized'):
                conn.execute('UPDATE control SET cooldown=MAX(cooldown,?) WHERE id=1',
                             (min(10**12, now + error.wait),))
                if error.category == 'unauthorized':
                    conn.execute('DELETE FROM artwork')
                    return False
            if row is None or row[0] != claim or row[1] <= now:
                return False
            if error is not None:
                conn.execute("UPDATE artwork SET lease='',until=0 WHERE kind=? AND ident=? AND language=?", lookup)
                if error.category not in ('cancelled', 'limited'):
                    conn.execute('UPDATE control SET cooldown=MAX(cooldown,?) WHERE id=1', (min(10**12, now + error.wait),))
                return False
            conn.execute("UPDATE artwork SET poster=?,backdrop=?,checked=?,touched=?,lease='',until=0 "
                         'WHERE kind=? AND ident=? AND language=?', (value.poster, value.backdrop, now, now) + lookup)
            return True

    def refresh(self, lookups, fetch, *, cancelled=lambda: False, limit=20):
        """Explicit finite warm-up. Return counts only; no implicit widget network work.

        fetch is a trusted bounded callback, normally Client.fetch (5s request
        budget, except OS DNS). This method has no daemon and no automatic retry.
        A caller must recheck its account/view guard before using returned paths.
        """
        lookups = _keys(lookups)
        if not callable(fetch) or not callable(cancelled) or type(limit) is not int or not 1 <= limit <= 20:
            raise ArtworkError()
        attempted = stored = 0
        if cancelled():
            return {'attempted': 0, 'stored': 0}
        for lookup in self._eligible(lookups):
            if cancelled() or attempted >= limit:
                break
            claim = self._claim(lookup)
            if claim is None:
                # A peer changed freshness or the global lease/cooldown after
                # eligibility. Stop rather than write once per remaining title.
                break
            attempted += 1
            value = error = None
            try:
                if cancelled():
                    raise ArtworkError('cancelled')
                value = fetch(lookup)
                if type(value) is not Artwork or value.stale:
                    raise ArtworkError()
                if cancelled():
                    raise ArtworkError('cancelled')
            except ArtworkError as failure:
                error = failure
            except Exception:
                error = ArtworkError()
            stored += int(self._finish(lookup, claim, value, error))
            if error is not None:
                break
        return {'attempted': attempted, 'stored': stored}
