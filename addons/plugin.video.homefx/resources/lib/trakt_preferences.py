"""Private list selections and widget key; no tokens, titles or history are saved.

Trakt's settings contract identifies user.ids.uuid as globally unique and suitable
for local identification. Treat it as an opaque bounded identifier, not a slug or
an assumed RFC UUID format. Account hashes are namespaces, not anonymization.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .trakt_auth import AuthError


class PreferencesError(AuthError):
    """Fixed error categories with no account, list or filesystem details."""


_MAX_INTEGER = 2 ** 63 - 1
_MAX_FILE_BYTES = 1024 * 1024


def _integer(value):
    return type(value) is int and 0 <= value <= _MAX_INTEGER


def account_uuid(settings):
    user = settings.get('user') if isinstance(settings, dict) else None
    ids = user.get('ids') if isinstance(user, dict) else None
    value = ids.get('uuid') if isinstance(ids, dict) else None
    _account_key(value)
    return value


def _account_key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise PreferencesError('invalid_account_identity')
    return hashlib.sha256(('homefx-trakt-account:' + value).encode('ascii')).hexdigest()


def _selection(keys):
    if (not isinstance(keys, (list, tuple)) or len(keys) > 100 or
            any(not isinstance(key, str) or not re.fullmatch(r'trakt-list:[1-9][0-9]{0,19}', key)
                for key in keys) or len(set(keys)) != len(keys)):
        raise PreferencesError('invalid_selection')
    return list(keys)


class AccountPreferences:
    """Explicitly opened POSIX profile storage; bounded to eight saved accounts.

    Save replaces one ordered selection atomically; an optional epoch rejects
    writes loaded before a clear. Clear increments the durable epoch in the same
    transaction that deletes selections. The oldest saved account is
    evicted on the ninth account. Disconnect should call clear_all: the complete
    local profile's choices are forgotten, even before identity has been fetched.
    File permissions do not protect against code running as Kodi or profile backups.
    Path checks reject unsafe existing files; another process running as Kodi can
    still replace paths concurrently.
    """
    def __init__(self, profile_directory):
        if os.name != 'posix' or not hasattr(os, 'fchmod'):
            raise PreferencesError('preferences_platform_unsupported')
        self._directory = Path(profile_directory).absolute() / 'trakt'
        self._path = self._directory / 'preferences.sqlite3'
        try:
            self._safe_paths(private=False, missing=True)
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._safe_paths(private=False, missing=True)
            os.chmod(str(self._directory), 0o700)
            flags = os.O_RDWR | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
            try:
                descriptor = os.open(str(self._path), flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                descriptor = os.open(str(self._path), flags)
                created = False
            try:
                self._file_info(os.fstat(descriptor), private=False)
                if not created and os.fstat(descriptor).st_size == 0:
                    raise OSError()
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            self._transaction(lambda conn: self._initialize(conn, created), validate=False)
        except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
            raise PreferencesError('preferences_unavailable') from None

    def __repr__(self):
        return 'AccountPreferences(<private profile>)'

    @staticmethod
    def _initialize(conn, created):
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2, 3):
            raise PreferencesError('preferences_version_unsupported')
        if created:
            conn.execute('CREATE TABLE selections ('
                         'account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
        AccountPreferences._table(conn, 'selections')
        AccountPreferences._rows(conn)
        if version < 2:
            state = conn.execute("SELECT 1 FROM sqlite_master WHERE name='preference_state'").fetchone()
            if state is None:
                conn.execute('CREATE TABLE preference_state ('
                             'id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL CHECK(epoch>=0))')
                conn.execute('INSERT INTO preference_state(id,epoch) VALUES(1,0)')
        AccountPreferences._table(conn, 'preference_state')
        AccountPreferences._epoch(conn)
        if version < 3:
            existing = conn.execute("SELECT 1 FROM sqlite_master WHERE name='widget_identity'").fetchone()
            if existing is not None:
                raise PreferencesError('preferences_invalid')
            conn.execute('CREATE TABLE widget_identity ('
                         'id INTEGER PRIMARY KEY CHECK(id=1), secret BLOB NOT NULL)')
            conn.execute('INSERT INTO widget_identity(id,secret) VALUES(1,?)', (os.urandom(32),))
        AccountPreferences._table(conn, 'widget_identity')
        AccountPreferences._widget_key(conn)
        conn.execute('PRAGMA user_version=3')

    @staticmethod
    def _table(conn, name):
        expected = {
            'selections': [('account', 'TEXT', 0, 1), ('selected', 'TEXT', 1, 0),
                           ('revision', 'INTEGER', 1, 0)],
            'preference_state': [('id', 'INTEGER', 0, 1), ('epoch', 'INTEGER', 1, 0)],
            'widget_identity': [('id', 'INTEGER', 0, 1), ('secret', 'BLOB', 1, 0)],
        }
        columns = conn.execute('PRAGMA table_info(' + name + ')').fetchall()
        shape = [(row[1], row[2].upper(), row[3], row[5]) for row in columns]
        table = conn.execute('SELECT type FROM sqlite_master WHERE name=?', (name,)).fetchone()
        if table != ('table',) or shape != expected[name]:
            raise PreferencesError('preferences_invalid')

    @staticmethod
    def _widget_key(conn):
        rows = conn.execute('SELECT id,secret FROM widget_identity LIMIT 2').fetchall()
        if (len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] != 1
                or type(rows[0][1]) is not bytes or len(rows[0][1]) != 32):
            raise PreferencesError('preferences_invalid')
        return rows[0][1]

    @staticmethod
    def _reference(secret, domain, account, epoch, key, kind=None, ident=None):
        # Canonical framing and domain separation; locators are not authorization.
        payload = json.dumps([domain, account, epoch, key, kind, ident],
                             separators=(',', ':'), ensure_ascii=True).encode('ascii')
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()

    def widget_snapshot(self, uuid):
        """Read current selections, clear epoch and opaque refs in one transaction."""
        account = _account_key(uuid)
        def read(conn):
            epoch = self._epoch(conn)
            selected = self._rows(conn).get(account, ([], 0))[0]
            secret = self._widget_key(conn)
            refs = [self._reference(secret, 'homefx-widget-list-v1', account, epoch, key)
                    for key in selected]
            return epoch, selected, refs
        return self._transaction(read)

    def widget_item_refs(self, uuid, key, identities, expected_epoch):
        """Return opaque item locators only within a currently selected list."""
        account = _account_key(uuid)
        _selection([key])
        if (not _integer(expected_epoch) or not isinstance(identities, (list, tuple))
                or len(identities) > 10000 or any(
                    not isinstance(pair, (list, tuple)) or len(pair) != 2
                    or pair[0] not in ('movie', 'show') or type(pair[1]) is not int
                    or not 1 <= pair[1] <= _MAX_INTEGER for pair in identities)):
            raise PreferencesError('invalid_widget_reference')
        def read(conn):
            epoch = self._epoch(conn)
            selected = self._rows(conn).get(account, ([], 0))[0]
            if epoch != expected_epoch or key not in selected:
                raise PreferencesError('preferences_changed')
            secret = self._widget_key(conn)
            return [self._reference(secret, 'homefx-widget-item-v1', account, epoch,
                                    key, kind, ident) for kind, ident in identities]
        return self._transaction(read)

    @staticmethod
    def _widget_feed(feed):
        if type(feed) is not str or feed not in {'continue', 'calendar'}:
            raise PreferencesError('invalid_widget_reference')
        return feed

    def widget_feed_snapshot(self, uuid, feed='continue'):
        """Read a restart-stable account feed locator without storing history."""
        account = _account_key(uuid)
        feed = self._widget_feed(feed)
        def read(conn):
            epoch = self._epoch(conn)
            secret = self._widget_key(conn)
            return epoch, self._reference(secret, 'homefx-widget-feed-v1', account, epoch, feed)
        return self._transaction(read)

    def widget_feed_item_refs(self, uuid, feed, identities, expected_epoch):
        """Derive bounded locators; callers must recheck current feed membership."""
        account = _account_key(uuid)
        feed = self._widget_feed(feed)
        limit = 1000 if feed == 'calendar' else 50
        kinds = ('episode',) if feed == 'calendar' else ('movie', 'episode')
        if (not _integer(expected_epoch) or type(identities) not in (list, tuple)
                or len(identities) > limit or any(
                    type(pair) not in (list, tuple) or len(pair) != 2
                    or type(pair[0]) is not str or pair[0] not in kinds
                    or type(pair[1]) is not int or not 1 <= pair[1] <= _MAX_INTEGER
                    for pair in identities)):
            raise PreferencesError('invalid_widget_reference')
        if len({tuple(pair) for pair in identities}) != len(identities):
            raise PreferencesError('invalid_widget_reference')
        def read(conn):
            epoch = self._epoch(conn)
            if epoch != expected_epoch:
                raise PreferencesError('preferences_changed')
            secret = self._widget_key(conn)
            return [self._reference(secret, 'homefx-widget-feed-item-v1', account, epoch,
                                    feed, kind, ident) for kind, ident in identities]
        return self._transaction(read)

    @staticmethod
    def _epoch(conn):
        rows = conn.execute('SELECT id,epoch FROM preference_state LIMIT 2').fetchall()
        if len(rows) != 1 or type(rows[0][0]) is not int or rows[0][0] != 1 or not _integer(rows[0][1]):
            raise PreferencesError('preferences_invalid')
        return rows[0][1]

    @staticmethod
    def _rows(conn):
        rows = conn.execute('SELECT account,selected,revision FROM selections LIMIT 9').fetchall()
        if len(rows) > 8:
            raise PreferencesError('preferences_invalid')
        result = {}
        for account, selected, revision in rows:
            if (not isinstance(account, str) or not re.fullmatch(r'[a-f0-9]{64}', account)
                    or account in result or not isinstance(selected, str) or len(selected) > 4096
                    or not _integer(revision)):
                raise PreferencesError('preferences_invalid')
            try:
                result[account] = (_selection(json.loads(selected)), revision)
            except (ValueError, TypeError, RecursionError, PreferencesError):
                raise PreferencesError('preferences_invalid') from None
        return result

    @staticmethod
    def _file_info(info, private, allow_unlinked=False):
        if (not stat.S_ISREG(info.st_mode)
                or info.st_nlink not in ((0, 1) if allow_unlinked else (1,))
                or info.st_size > _MAX_FILE_BYTES
                or (private and stat.S_IMODE(info.st_mode) & 0o077)):
            raise OSError()

    def _safe_file(self, path, private, missing, transient=False):
        try:
            before = path.lstat()
        except FileNotFoundError:
            if missing:
                return
            raise
        self._file_info(before, private, allow_unlinked=transient)
        try:
            descriptor = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
        except FileNotFoundError:
            if missing:
                return
            raise
        try:
            info = os.fstat(descriptor)
            # SQLite can unlink an open sidecar or recreate its path on commit.
            # Validate the opened file itself; only the mandatory database needs
            # a stable inode and exactly one link across this inspection.
            self._file_info(info, private, allow_unlinked=transient)
            # Without no-follow support, retain the conservative identity guard.
            stable_identity = not transient or not getattr(os, 'O_NOFOLLOW', 0)
            if stable_identity and (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino):
                raise OSError()
        finally:
            os.close(descriptor)

    def _safe_paths(self, private=True, missing=False):
        for path in (self._directory,) + tuple(self._directory.parents):
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(info.st_mode):
                raise OSError()
            if path == self._directory and private and stat.S_IMODE(info.st_mode) & 0o077:
                raise OSError()
        self._safe_file(self._path, private, missing)
        for suffix in ('-journal', '-wal', '-shm'):
            self._safe_file(Path(str(self._path) + suffix), private=True, missing=True, transient=True)

    def _connect(self):
        self._safe_paths()
        conn = sqlite3.connect(self._path.as_uri() + '?mode=rw', timeout=2, uri=True)
        try:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('PRAGMA secure_delete=ON')
            conn.execute('PRAGMA journal_mode=DELETE')
            conn.execute('PRAGMA max_page_count=256')
            return conn
        except sqlite3.Error:
            conn.close()
            raise

    def _transaction(self, action, validate=True):
        conn = None
        try:
            conn = self._connect()
            conn.execute('BEGIN IMMEDIATE')
            if validate:
                if conn.execute('PRAGMA user_version').fetchone()[0] != 3:
                    raise PreferencesError('preferences_version_unsupported')
                self._table(conn, 'selections')
                self._table(conn, 'preference_state')
                self._table(conn, 'widget_identity')
                self._widget_key(conn)
                self._epoch(conn)
                self._rows(conn)
            value = action(conn)
            conn.commit()
            return value
        except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError):
            raise PreferencesError('preferences_unavailable') from None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    raise PreferencesError('preferences_unavailable') from None

    def snapshot(self, uuid):
        """Read clear epoch and ordered selection in one transaction."""
        account = _account_key(uuid)
        def read(conn):
            epoch = self._epoch(conn)
            return epoch, self._rows(conn).get(account, ([], 0))[0]
        return self._transaction(read)

    def load(self, uuid):
        return self.snapshot(uuid)[1]

    def save(self, uuid, keys, expected_epoch=None, expected_keys=None):
        """Atomically reject a stale clear epoch or ordered selection snapshot."""
        if expected_epoch is not None and not _integer(expected_epoch):
            raise PreferencesError('invalid_preference_epoch')
        account = _account_key(uuid)
        selected = json.dumps(_selection(keys), separators=(',', ':'))
        expected = None if expected_keys is None else _selection(expected_keys)
        def write(conn):
            if expected_epoch is not None and self._epoch(conn) != expected_epoch:
                return False
            rows = self._rows(conn)
            if expected is not None and rows.get(account, ([], 0))[0] != expected:
                return False
            revision = max((row[1] for row in rows.values()), default=0)
            if revision == _MAX_INTEGER:
                raise PreferencesError('preferences_revision_exhausted')
            revision += 1
            conn.execute('INSERT OR REPLACE INTO selections(account,selected,revision) VALUES(?,?,?)',
                         (account, selected, revision))
            conn.execute('DELETE FROM selections WHERE account NOT IN '
                         '(SELECT account FROM selections ORDER BY revision DESC LIMIT 8)')
            return True
        return self._transaction(write)

    def clear(self, uuid):
        account = _account_key(uuid)
        def clear_account(conn):
            self._advance_epoch(conn)
            conn.execute('DELETE FROM selections WHERE account=?', (account,))
        self._transaction(clear_account)

    def clear_all(self):
        def clear_profile(conn):
            self._advance_epoch(conn)
            conn.execute('DELETE FROM selections')
        self._transaction(clear_profile)

    @staticmethod
    def _advance_epoch(conn):
        epoch = AccountPreferences._epoch(conn)
        if epoch == _MAX_INTEGER:
            raise PreferencesError('preferences_epoch_exhausted')
        conn.execute('UPDATE preference_state SET epoch=? WHERE id=1', (epoch + 1,))
