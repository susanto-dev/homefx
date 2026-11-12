"""Private list selections only; no tokens, titles, settings or history are saved.

Trakt's settings contract identifies user.ids.uuid as globally unique and suitable
for local identification. Treat it as an opaque bounded identifier, not a slug or
an assumed RFC UUID format. Account hashes are namespaces, not anonymization.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from .trakt_auth import AuthError


class PreferencesError(AuthError):
    """Fixed error categories with no account, list or filesystem details."""


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
    """
    def __init__(self, profile_directory):
        if os.name != 'posix' or not hasattr(os, 'fchmod'):
            raise PreferencesError('preferences_platform_unsupported')
        self._directory = Path(profile_directory) / 'trakt'
        self._path = self._directory / 'preferences.sqlite3'
        try:
            if self._directory.is_symlink():
                raise OSError()
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(str(self._directory), 0o700)
            if self._path.is_symlink() or (self._path.exists() and self._path.stat().st_size > 1024 * 1024):
                raise OSError()
            descriptor = os.open(str(self._path), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            try:
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            self._transaction(self._initialize)
        except (OSError, sqlite3.Error):
            raise PreferencesError('preferences_unavailable') from None

    def __repr__(self):
        return 'AccountPreferences(<private profile>)'

    @staticmethod
    def _initialize(conn):
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2):
            raise PreferencesError('preferences_version_unsupported')
        conn.execute('CREATE TABLE IF NOT EXISTS selections ('
                     'account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
        if version < 2:
            conn.execute('CREATE TABLE IF NOT EXISTS preference_state ('
                         'id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL CHECK(epoch>=0))')
            conn.execute('INSERT OR IGNORE INTO preference_state(id,epoch) VALUES(1,0)')
        AccountPreferences._epoch(conn)
        conn.execute('PRAGMA user_version=2')

    @staticmethod
    def _epoch(conn):
        row = conn.execute('SELECT epoch FROM preference_state WHERE id=1').fetchone()
        if row is None or type(row[0]) is not int or row[0] < 0:
            raise PreferencesError('preferences_invalid')
        return row[0]

    def _transaction(self, action):
        conn = None
        try:
            if self._directory.is_symlink() or self._path.is_symlink():
                raise OSError()
            conn = sqlite3.connect(str(self._path), timeout=2)
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('PRAGMA secure_delete=ON')
            conn.execute('PRAGMA max_page_count=256')
            conn.execute('BEGIN IMMEDIATE')
            value = action(conn)
            conn.commit()
            return value
        except (OSError, sqlite3.Error):
            raise PreferencesError('preferences_unavailable') from None
        finally:
            if conn is not None:
                conn.close()

    def snapshot(self, uuid):
        """Read clear epoch and ordered selection in one transaction."""
        account = _account_key(uuid)
        def read(conn):
            epoch = self._epoch(conn)
            row = conn.execute('SELECT selected FROM selections WHERE account=?', (account,)).fetchone()
            if row is None:
                return epoch, []
            if not isinstance(row[0], str) or len(row[0]) > 4096:
                raise PreferencesError('preferences_invalid')
            try:
                return epoch, _selection(json.loads(row[0]))
            except (ValueError, TypeError, RecursionError, PreferencesError):
                raise PreferencesError('preferences_invalid') from None
        return self._transaction(read)

    def load(self, uuid):
        return self.snapshot(uuid)[1]

    def save(self, uuid, keys, expected_epoch=None):
        """Return False without writing if a clear invalidated the caller's epoch."""
        if expected_epoch is not None and (type(expected_epoch) is not int or expected_epoch < 0):
            raise PreferencesError('invalid_preference_epoch')
        account = _account_key(uuid)
        selected = json.dumps(_selection(keys), separators=(',', ':'))
        def write(conn):
            if expected_epoch is not None and self._epoch(conn) != expected_epoch:
                return False
            revision = conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM selections').fetchone()[0]
            conn.execute('INSERT OR REPLACE INTO selections(account,selected,revision) VALUES(?,?,?)',
                         (account, selected, revision))
            conn.execute('DELETE FROM selections WHERE account NOT IN '
                         '(SELECT account FROM selections ORDER BY revision DESC LIMIT 8)')
            return True
        return self._transaction(write)

    def clear(self, uuid):
        account = _account_key(uuid)
        def clear_account(conn):
            conn.execute('UPDATE preference_state SET epoch=epoch+1 WHERE id=1')
            self._epoch(conn)
            conn.execute('DELETE FROM selections WHERE account=?', (account,))
        self._transaction(clear_account)

    def clear_all(self):
        def clear_profile(conn):
            conn.execute('UPDATE preference_state SET epoch=epoch+1 WHERE id=1')
            self._epoch(conn)
            conn.execute('DELETE FROM selections')
        self._transaction(clear_profile)
