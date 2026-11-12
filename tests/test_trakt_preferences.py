"""Private preference tests use temporary profiles and fabricated account IDs."""
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest

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
        import hashlib
        with tempfile.TemporaryDirectory() as profile:
            root = Path(profile) / 'trakt'
            root.mkdir()
            path = root / 'preferences.sqlite3'
            key = hashlib.sha256(b'homefx-trakt-account:synthetic-a').hexdigest()
            with sqlite3.connect(str(path)) as conn:
                conn.execute('CREATE TABLE selections (account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
                conn.execute('INSERT INTO selections VALUES(?,?,?)', (key, '["trakt-list:1"]', 1))
                conn.execute('PRAGMA user_version=1')
            migrated = AccountPreferences(profile)
            self.assertEqual(migrated.snapshot('synthetic-a'), (0, ['trakt-list:1']))
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
