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

    Save replaces one ordered selection atomically. The oldest saved account is
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
        if version not in (0, 1):
            raise PreferencesError('preferences_version_unsupported')
        conn.execute('CREATE TABLE IF NOT EXISTS selections ('
                     'account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
        conn.execute('PRAGMA user_version=1')

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

    def load(self, uuid):
        account = _account_key(uuid)
        def read(conn):
            row = conn.execute('SELECT selected FROM selections WHERE account=?', (account,)).fetchone()
            if row is None:
                return []
            if not isinstance(row[0], str) or len(row[0]) > 4096:
                raise PreferencesError('preferences_invalid')
            try:
                return _selection(json.loads(row[0]))
            except (ValueError, TypeError, RecursionError, PreferencesError):
                raise PreferencesError('preferences_invalid') from None
        return self._transaction(read)

    def save(self, uuid, keys):
        account = _account_key(uuid)
        selected = json.dumps(_selection(keys), separators=(',', ':'))
        def write(conn):
            revision = conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM selections').fetchone()[0]
            conn.execute('INSERT OR REPLACE INTO selections(account,selected,revision) VALUES(?,?,?)',
                         (account, selected, revision))
            conn.execute('DELETE FROM selections WHERE account NOT IN '
                         '(SELECT account FROM selections ORDER BY revision DESC LIMIT 8)')
        self._transaction(write)

    def clear(self, uuid):
        account = _account_key(uuid)
        self._transaction(lambda conn: conn.execute('DELETE FROM selections WHERE account=?', (account,)))

    def clear_all(self):
        self._transaction(lambda conn: conn.execute('DELETE FROM selections'))
