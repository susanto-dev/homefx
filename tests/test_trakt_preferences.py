"""Private preference tests use temporary profiles and fabricated account IDs."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError, account_uuid


def save_selection(profile, ident):
    AccountPreferences(profile).save('synthetic-account-' + str(ident), ['trakt-list:' + str(ident)])


class PreferencesTests(unittest.TestCase):
    def test_identity_requires_uuid_not_mutable_slug(self):
        self.assertEqual(account_uuid({'user': {'ids': {'uuid': 'opaque_Account-1', 'slug': 'name'}}}),
                         'opaque_Account-1')
        for value in ({}, {'user': {'ids': {'slug': 'name'}}}, {'user': {'ids': {'uuid': None}}},
                      {'user': {'ids': {'uuid': ''}}}, {'user': {'ids': {'uuid': 'private\nvalue'}}},
                      {'user': {'ids': {'uuid': 'x' * 129}}}):
            with self.subTest(value_type=type(value).__name__), self.assertRaisesRegex(
                    PreferencesError, '^invalid_account_identity$'):
                account_uuid(value)

    def test_ordered_selections_survive_reopen_without_settings_or_tokens(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            self.assertEqual(store.load('synthetic-a'), [])
            store.save('synthetic-a', ['trakt-list:21', 'trakt-list:3'])
            store.save('synthetic-b', ['trakt-list:4'])
            reopened = AccountPreferences(profile)
            self.assertEqual(reopened.load('synthetic-a'), ['trakt-list:21', 'trakt-list:3'])
            self.assertEqual(reopened.load('synthetic-b'), ['trakt-list:4'])
            store.clear('synthetic-a')
            self.assertEqual(reopened.load('synthetic-a'), [])
            self.assertEqual(reopened.load('synthetic-b'), ['trakt-list:4'])
            store.clear_all()
            self.assertEqual(reopened.load('synthetic-b'), [])
            raw = (Path(profile) / 'trakt/preferences.sqlite3').read_bytes()
            self.assertNotIn(b'synthetic-a', raw)
            self.assertNotIn(profile, repr(store))

    def test_invalid_or_oversized_selection_never_replaces_saved_value(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            store.save('synthetic', ['trakt-list:1'])
            for value in (None, ['trakt-list:1'] * 2, ['trakt-list:0'], ['trakt-list:01'],
                          ['trakt-list:1\n'], ['trakt-list:' + '1' * 21],
                          ['trakt-list:' + str(i) for i in range(1, 102)]):
                with self.subTest(value_type=type(value).__name__), self.assertRaisesRegex(
                        PreferencesError, '^invalid_selection$'):
                    store.save('synthetic', value)
                self.assertEqual(store.load('synthetic'), ['trakt-list:1'])

    def test_accounts_bounded_and_atomic_across_processes(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            with ProcessPoolExecutor(max_workers=4) as pool:
                list(pool.map(save_selection, [profile] * 8, range(1, 9)))
            for ident in range(1, 9):
                self.assertEqual(store.load('synthetic-account-' + str(ident)), ['trakt-list:' + str(ident)])
            store.save('ninth', ['trakt-list:99'])
            self.assertEqual(store.load('ninth'), ['trakt-list:99'])
            self.assertEqual(sum(bool(store.load('synthetic-account-' + str(i))) for i in range(1, 9)), 7)

    def test_permissions_symlinks_and_sanitized_corruption(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            directory = Path(profile) / 'trakt'
            path = directory / 'preferences.sqlite3'
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            store.save('synthetic', ['trakt-list:1'])
            with sqlite3.connect(str(path)) as conn:
                conn.execute("UPDATE selections SET selected='not-json-private'")
            with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                store.load('synthetic')
        with tempfile.TemporaryDirectory() as profile:
            root = Path(profile)
            (root / 'target').mkdir()
            (root / 'trakt').symlink_to(root / 'target', target_is_directory=True)
            with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                AccountPreferences(profile)
        with tempfile.TemporaryDirectory() as profile:
            root = Path(profile) / 'trakt'
            root.mkdir()
            (root / 'preferences.sqlite3').write_bytes(b'synthetic-private-invalid-database')
            with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                AccountPreferences(profile)

    def test_unknown_schema_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as profile:
            AccountPreferences(profile)
            path = Path(profile) / 'trakt/preferences.sqlite3'
            with sqlite3.connect(str(path)) as conn:
                conn.execute('PRAGMA user_version=9')
            with self.assertRaisesRegex(PreferencesError, '^preferences_version_unsupported$'):
                AccountPreferences(profile)
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 9)

    def test_clear_epoch_rejects_stale_saves_across_reopened_stores(self):
        with tempfile.TemporaryDirectory() as profile:
            first = AccountPreferences(profile)
            epoch, selected = first.snapshot('synthetic-a')
            self.assertEqual((epoch, selected), (0, []))
            self.assertTrue(first.save('synthetic-a', ['trakt-list:1'], expected_epoch=epoch))
            second = AccountPreferences(profile)
            second.clear_all()
            reopened = AccountPreferences(profile)
            next_epoch, selected = reopened.snapshot('synthetic-a')
            self.assertEqual((next_epoch, selected), (1, []))
            self.assertFalse(first.save('synthetic-a', ['trakt-list:2'], expected_epoch=epoch))
            self.assertEqual(reopened.load('synthetic-a'), [])
            self.assertTrue(first.save('synthetic-a', ['trakt-list:3'], expected_epoch=next_epoch))
            second.clear('synthetic-a')
            self.assertEqual(reopened.snapshot('synthetic-a'), (2, []))
            self.assertFalse(first.save('synthetic-a', ['trakt-list:4'], expected_epoch=next_epoch))
            self.assertTrue(first.save('synthetic-a', ['trakt-list:5']))  # explicit unconditional API
            self.assertEqual(reopened.load('synthetic-a'), ['trakt-list:5'])

    def test_existing_selection_schema_migrates_without_forgetting_choices(self):
        for version in (0, 1):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as profile:
                root = Path(profile) / 'trakt'
                root.mkdir()
                path = root / 'preferences.sqlite3'
                key = hashlib.sha256(b'homefx-trakt-account:synthetic-a').hexdigest()
                with sqlite3.connect(str(path)) as conn:
                    conn.execute('CREATE TABLE selections (account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
                    conn.execute('INSERT INTO selections VALUES(?,?,?)', (key, '["trakt-list:2","trakt-list:1"]', 1))
                    conn.execute('PRAGMA user_version=' + str(version))
                path.chmod(0o644)
                migrated = AccountPreferences(profile)
                self.assertEqual(migrated.snapshot('synthetic-a'), (0, ['trakt-list:2', 'trakt-list:1']))
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(AccountPreferences(profile).load('synthetic-a'), ['trakt-list:2', 'trakt-list:1'])
                migrated.clear_all()
                self.assertEqual(AccountPreferences(profile).snapshot('synthetic-a'), (1, []))

    def test_corrupt_epoch_is_not_reset_by_constructor(self):
        with tempfile.TemporaryDirectory() as profile:
            AccountPreferences(profile)
            path = Path(profile) / 'trakt/preferences.sqlite3'
            with sqlite3.connect(str(path)) as conn:
                conn.execute('DELETE FROM preference_state')
            with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                AccountPreferences(profile)

    def test_existing_empty_database_and_missing_schema_are_not_initialized(self):
        for kind in ('empty', 'missing-selections', 'missing-state'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as profile:
                directory = Path(profile) / 'trakt'
                directory.mkdir()
                path = directory / 'preferences.sqlite3'
                if kind == 'empty':
                    path.touch()
                else:
                    with sqlite3.connect(str(path)) as conn:
                        conn.execute('CREATE TABLE unrelated (value INTEGER)')
                        conn.execute('PRAGMA user_version=2')
                        if kind == 'missing-state':
                            conn.execute('CREATE TABLE selections (account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
                before = path.read_bytes()
                error = 'preferences_unavailable' if kind == 'empty' else 'preferences_invalid'
                with self.assertRaisesRegex(PreferencesError, '^' + error + '$'):
                    AccountPreferences(profile)
                self.assertEqual(path.read_bytes(), before)

    def test_malformed_legacy_selection_rolls_back_migration(self):
        with tempfile.TemporaryDirectory() as profile:
            directory = Path(profile) / 'trakt'
            directory.mkdir()
            path = directory / 'preferences.sqlite3'
            key = hashlib.sha256(b'homefx-trakt-account:synthetic-a').hexdigest()
            with sqlite3.connect(str(path)) as conn:
                conn.execute('CREATE TABLE selections (account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
                conn.execute('INSERT INTO selections VALUES(?,?,?)', (key, 'private-invalid-json', 1))
                conn.execute('PRAGMA user_version=1')
            with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                AccountPreferences(profile)
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 1)
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='preference_state'").fetchone())
                self.assertEqual(conn.execute('SELECT selected FROM selections').fetchone()[0], 'private-invalid-json')

    def test_legacy_state_row_is_not_silently_repaired(self):
        with tempfile.TemporaryDirectory() as profile:
            AccountPreferences(profile)
            path = Path(profile) / 'trakt/preferences.sqlite3'
            with sqlite3.connect(str(path)) as conn:
                conn.execute('DELETE FROM preference_state')
                conn.execute('PRAGMA user_version=1')
            with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                AccountPreferences(profile)
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM preference_state').fetchone()[0], 0)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 1)

    def test_incompatible_table_shapes_are_rejected_before_writes(self):
        shapes = (
            ('selections', 'account TEXT, selected TEXT NOT NULL, revision INTEGER NOT NULL'),
            ('selections', 'account TEXT PRIMARY KEY, selected TEXT, revision INTEGER NOT NULL'),
            ('selections', 'account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision REAL NOT NULL'),
            ('preference_state', 'id INTEGER, epoch INTEGER NOT NULL'),
            ('preference_state', 'id INTEGER PRIMARY KEY, epoch INTEGER'),
        )
        for table, columns in shapes:
            with self.subTest(table=table, columns=columns), tempfile.TemporaryDirectory() as profile:
                store = AccountPreferences(profile)
                path = Path(profile) / 'trakt/preferences.sqlite3'
                with sqlite3.connect(str(path)) as conn:
                    conn.execute('DROP TABLE ' + table)
                    conn.execute('CREATE TABLE ' + table + ' (' + columns + ')')
                    if table == 'preference_state':
                        conn.execute('INSERT INTO preference_state VALUES(1,0)')
                before = path.read_bytes()
                for action in (lambda: AccountPreferences(profile),
                               lambda: store.save('synthetic-a', ['trakt-list:1']), store.clear_all):
                    with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                        action()
                    self.assertEqual(path.read_bytes(), before)

    def test_invalid_persisted_rows_cannot_be_hidden_or_cleared(self):
        corruptions = (
            ('UPDATE selections SET account=?', ('private-account',)),
            ('UPDATE selections SET selected=?', ('["trakt-list:1","trakt-list:1"]',)),
            ('UPDATE selections SET revision=?', (-1,)),
            ('UPDATE selections SET revision=?', (1.5,)),
            ('UPDATE selections SET revision=?', ('9223372036854775808',)),
            ('UPDATE preference_state SET epoch=?', (1.5,)),
            ('UPDATE preference_state SET epoch=?', ('9223372036854775808',)),
            ('DELETE FROM preference_state', ()),
        )
        for query, params in corruptions:
            with self.subTest(query=query, params=params), tempfile.TemporaryDirectory() as profile:
                store = AccountPreferences(profile)
                store.save('synthetic-a', ['trakt-list:1'])
                path = Path(profile) / 'trakt/preferences.sqlite3'
                with sqlite3.connect(str(path)) as conn:
                    conn.execute(query, params)
                before = path.read_bytes()
                for action in (lambda: store.load('synthetic-b'),
                               lambda: store.save('synthetic-b', ['trakt-list:2']),
                               lambda: store.clear('synthetic-b'), store.clear_all,
                               lambda: AccountPreferences(profile)):
                    with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                        action()
                    self.assertEqual(path.read_bytes(), before)

    def test_extra_state_rows_are_invalid(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            path = Path(profile) / 'trakt/preferences.sqlite3'
            with sqlite3.connect(str(path)) as conn:
                conn.execute('DROP TABLE preference_state')
                conn.execute('CREATE TABLE preference_state (id INTEGER PRIMARY KEY, epoch INTEGER NOT NULL)')
                conn.executemany('INSERT INTO preference_state VALUES(?,?)', ((1, 3), (2, 4)))
            with self.assertRaisesRegex(PreferencesError, '^preferences_invalid$'):
                store.clear_all()
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute('SELECT * FROM preference_state').fetchall(), [(1, 3), (2, 4)])

    def test_epoch_and_revision_exhaustion_preserve_integer_state_and_selections(self):
        maximum = 2 ** 63 - 1
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            store.save('synthetic-a', ['trakt-list:2', 'trakt-list:1'])
            path = Path(profile) / 'trakt/preferences.sqlite3'
            with sqlite3.connect(str(path)) as conn:
                conn.execute('UPDATE preference_state SET epoch=?', (maximum - 1,))
            store.clear('synthetic-b')
            self.assertEqual(store.snapshot('synthetic-a'), (maximum, ['trakt-list:2', 'trakt-list:1']))
            for action in (lambda: store.clear('synthetic-a'), store.clear_all):
                with self.assertRaisesRegex(PreferencesError, '^preferences_epoch_exhausted$'):
                    action()
                self.assertEqual(store.snapshot('synthetic-a'), (maximum, ['trakt-list:2', 'trakt-list:1']))
            with sqlite3.connect(str(path)) as conn:
                conn.execute('UPDATE selections SET revision=?', (maximum - 1,))
            self.assertTrue(store.save('synthetic-a', ['trakt-list:3'], expected_epoch=maximum))
            self.assertFalse(store.save('synthetic-a', ['trakt-list:4'], expected_epoch=maximum - 1))
            with self.assertRaisesRegex(PreferencesError, '^preferences_revision_exhausted$'):
                store.save('synthetic-b', ['trakt-list:5'])
            self.assertEqual(store.load('synthetic-a'), ['trakt-list:3'])
            self.assertEqual(store.load('synthetic-b'), [])
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute('SELECT epoch,typeof(epoch) FROM preference_state').fetchone(), (maximum, 'integer'))
                self.assertEqual(conn.execute('SELECT revision,typeof(revision) FROM selections').fetchone(), (maximum, 'integer'))

    def test_expected_epoch_rejects_values_outside_signed_integer_bounds(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            for value in (-1, True, 1.0, '1', 2 ** 63, 10 ** 100):
                with self.subTest(value_type=type(value).__name__), mock.patch.object(store, '_connect') as connect:
                    with self.assertRaisesRegex(PreferencesError, '^invalid_preference_epoch$'):
                        store.save('synthetic-a', ['trakt-list:1'], expected_epoch=value)
                    connect.assert_not_called()

    def test_symlink_ancestor_is_rejected_before_chmod_or_creation(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            target = directory / 'target'
            target.mkdir(mode=0o755)
            target.chmod(0o755)
            (directory / 'alias').symlink_to(target, target_is_directory=True)
            with mock.patch('resources.lib.trakt_preferences.os.chmod') as chmod:
                with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                    AccountPreferences(directory / 'alias' / 'profile')
                chmod.assert_not_called()
            self.assertEqual(list(target.iterdir()), [])
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)

    def test_unsafe_database_and_sidecars_are_rejected_before_permission_changes(self):
        for suffix in ('', '-journal', '-wal', '-shm'):
            for kind in ('symlink', 'hardlink', 'fifo', 'directory', 'oversized'):
                with self.subTest(suffix=suffix, kind=kind), tempfile.TemporaryDirectory() as profile:
                    directory = Path(profile) / 'trakt'
                    directory.mkdir(mode=0o755)
                    directory.chmod(0o755)
                    main = directory / 'preferences.sqlite3'
                    unsafe = Path(str(main) + suffix)
                    target = Path(profile) / 'external'
                    target.write_bytes(b'private-synthetic')
                    target.chmod(0o644)
                    if kind == 'symlink':
                        unsafe.symlink_to(target)
                    elif kind == 'hardlink':
                        os.link(str(target), str(unsafe))
                    elif kind == 'fifo':
                        os.mkfifo(str(unsafe), 0o600)
                    elif kind == 'directory':
                        unsafe.mkdir()
                    else:
                        with unsafe.open('wb') as stream:
                            stream.truncate(1024 * 1024 + 1)
                        unsafe.chmod(0o600)
                    before = target.read_bytes()
                    with mock.patch('resources.lib.trakt_preferences.os.chmod') as chmod:
                        with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                            AccountPreferences(profile)
                        chmod.assert_not_called()
                    self.assertEqual(target.read_bytes(), before)
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
                    self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755)
                    if suffix:
                        self.assertFalse(main.exists())

    def test_each_operation_rechecks_ancestor_and_sidecar_replacements(self):
        for replacement in ('ancestor', 'database', '-journal', '-wal', '-shm'):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as profile:
                store = AccountPreferences(profile)
                store.save('synthetic-a', ['trakt-list:1'])
                directory = Path(profile) / 'trakt'
                main = directory / 'preferences.sqlite3'
                if replacement == 'ancestor':
                    moved = Path(profile) / 'moved'
                    directory.rename(moved)
                    directory.symlink_to(moved, target_is_directory=True)
                    target = moved / 'preferences.sqlite3'
                elif replacement == 'database':
                    target = Path(profile) / 'moved.sqlite3'
                    main.rename(target)
                    os.link(str(target), str(main))
                else:
                    target = Path(profile) / 'external'
                    target.write_bytes(b'synthetic-external')
                    Path(str(main) + replacement).symlink_to(target)
                before = target.read_bytes()
                for action in (lambda: store.snapshot('synthetic-a'),
                               lambda: store.save('synthetic-a', ['trakt-list:2']),
                               lambda: store.clear('synthetic-a'), store.clear_all):
                    with mock.patch('resources.lib.trakt_preferences.sqlite3.connect') as connect:
                        with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                            action()
                        connect.assert_not_called()
                    self.assertEqual(target.read_bytes(), before)

    def test_per_operation_permission_and_size_changes_fail_without_repair(self):
        for replacement in ('directory-mode', 'file-mode', 'sidecar-mode', 'size', 'missing'):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as profile:
                store = AccountPreferences(profile)
                directory = Path(profile) / 'trakt'
                main = directory / 'preferences.sqlite3'
                if replacement == 'directory-mode':
                    directory.chmod(0o755)
                elif replacement == 'file-mode':
                    main.chmod(0o644)
                elif replacement == 'sidecar-mode':
                    sidecar = Path(str(main) + '-journal')
                    sidecar.touch(mode=0o644)
                    sidecar.chmod(0o644)
                elif replacement == 'size':
                    with main.open('r+b') as stream:
                        stream.truncate(1024 * 1024 + 1)
                else:
                    main.unlink()
                with mock.patch('resources.lib.trakt_preferences.sqlite3.connect') as connect:
                    with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                        store.load('synthetic-a')
                    connect.assert_not_called()
                if replacement == 'missing':
                    self.assertFalse(main.exists())
                elif replacement == 'file-mode':
                    self.assertEqual(stat.S_IMODE(main.stat().st_mode), 0o644)

    def test_reopen_accepts_journal_unlinked_by_real_sqlite_commit_after_open(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            store.save('synthetic-a', ['trakt-list:1'])
            main = Path(profile) / 'trakt/preferences.sqlite3'
            journal = Path(str(main) + '-journal')
            writer = sqlite3.connect(str(main))
            self.addCleanup(writer.close)
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE selections SET selected='[\"trakt-list:2\"]'")
            self.assertTrue(journal.is_file())
            real_open = os.open
            opened_links = []

            def commit_after_open(path, flags, *args, **kwargs):
                descriptor = real_open(path, flags, *args, **kwargs)
                if Path(path) == journal:
                    writer.commit()
                    opened_links.append(os.fstat(descriptor).st_nlink)
                    self.assertFalse(journal.exists())
                return descriptor

            with mock.patch('resources.lib.trakt_preferences.os.open', side_effect=commit_after_open):
                reopened = AccountPreferences(profile)
            self.assertEqual(opened_links, [0])
            self.assertEqual(reopened.load('synthetic-a'), ['trakt-list:2'])

    def test_reopen_accepts_journal_unlinked_during_initial_path_inspection(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            store.save('synthetic-a', ['trakt-list:1'])
            main = Path(profile) / 'trakt/preferences.sqlite3'
            journal = Path(str(main) + '-journal')
            writer = sqlite3.connect(str(main))
            self.addCleanup(writer.close)
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE selections SET selected='[\"trakt-list:2\"]'")
            real_lstat = Path.lstat
            inspected = []

            def commit_during_stat(path):
                if path == journal and not inspected:
                    # A kernel path lookup can retain the inode across unlink
                    # before filling stat fields. Supply that real inode's stat.
                    descriptor = os.open(str(journal), os.O_RDONLY)
                    try:
                        writer.commit()
                        info = os.fstat(descriptor)
                    finally:
                        os.close(descriptor)
                    inspected.append(info.st_nlink)
                    return info
                return real_lstat(path)

            with mock.patch.object(Path, 'lstat', commit_during_stat):
                reopened = AccountPreferences(profile)
            self.assertEqual(inspected, [0])
            self.assertFalse(journal.exists())
            self.assertEqual(reopened.load('synthetic-a'), ['trakt-list:2'])

    def test_transient_sidecar_recreation_keeps_descriptor_safety_checks(self):
        for suffix in ('-journal', '-wal', '-shm'):
            for replacement in ('safe', 'no-nofollow', 'symlink', 'hardlink', 'fifo', 'mode', 'size'):
                with self.subTest(suffix=suffix, replacement=replacement), tempfile.TemporaryDirectory() as profile:
                    store = AccountPreferences(profile)
                    main = Path(profile) / 'trakt/preferences.sqlite3'
                    sidecar = Path(str(main) + suffix)
                    sidecar.touch(mode=0o600)
                    original_inode = sidecar.stat().st_ino
                    retired = Path(profile) / 'retired'
                    target = Path(profile) / 'synthetic-external'
                    target.write_bytes(b'synthetic')
                    target.chmod(0o600)
                    real_open = os.open
                    changed = []

                    def replace_before_open(path, flags, *args, **kwargs):
                        if Path(path) == sidecar and not changed:
                            changed.append(True)
                            sidecar.rename(retired)  # Keep old inode allocated deterministically.
                            if replacement == 'symlink':
                                sidecar.symlink_to(target)
                            elif replacement == 'hardlink':
                                os.link(str(target), str(sidecar))
                            elif replacement == 'fifo':
                                os.mkfifo(str(sidecar), 0o600)
                            else:
                                sidecar.touch(mode=0o600)
                                if replacement == 'mode':
                                    sidecar.chmod(0o644)
                                elif replacement == 'size':
                                    with sidecar.open('wb') as stream:
                                        stream.truncate(1024 * 1024 + 1)
                        return real_open(path, flags, *args, **kwargs)

                    nofollow = 0 if replacement == 'no-nofollow' else getattr(os, 'O_NOFOLLOW', 0)
                    with mock.patch('resources.lib.trakt_preferences.os.open', side_effect=replace_before_open), \
                            mock.patch('resources.lib.trakt_preferences.os.O_NOFOLLOW', nofollow, create=True):
                        if replacement == 'safe':
                            store._safe_paths()
                        else:
                            with self.assertRaises(OSError):
                                store._safe_paths()
                    self.assertEqual(changed, [True])
                    self.assertNotEqual(sidecar.lstat().st_ino, original_inode)
                    self.assertEqual(target.read_bytes(), b'synthetic')
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_mandatory_database_unlink_or_replacement_during_open_is_rejected(self):
        for replacement in ('unlink', 'replace'):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as profile:
                store = AccountPreferences(profile)
                main = Path(profile) / 'trakt/preferences.sqlite3'
                retired = Path(profile) / 'retired'
                real_open = os.open
                changed = []

                def change_main(path, flags, *args, **kwargs):
                    if Path(path) == main and not changed:
                        changed.append(True)
                        if replacement == 'replace':
                            main.rename(retired)
                            main.touch(mode=0o600)
                        descriptor = real_open(path, flags, *args, **kwargs)
                        if replacement == 'unlink':
                            main.unlink()
                        return descriptor
                    return real_open(path, flags, *args, **kwargs)

                with mock.patch('resources.lib.trakt_preferences.os.open', side_effect=change_main), \
                        mock.patch('resources.lib.trakt_preferences.sqlite3.connect') as connect:
                    with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                        store.load('synthetic-a')
                    connect.assert_not_called()
                self.assertEqual(changed, [True])
                if replacement == 'unlink':
                    self.assertFalse(main.exists())

    def test_connection_initialization_failure_closes_connection_and_sanitizes_error(self):
        with tempfile.TemporaryDirectory() as profile:
            store = AccountPreferences(profile)
            conn = mock.Mock()
            conn.execute.side_effect = sqlite3.DatabaseError('synthetic-private-path')
            with mock.patch('resources.lib.trakt_preferences.sqlite3.connect', return_value=conn):
                with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                    store.load('synthetic-a')
            conn.close.assert_called_once_with()
