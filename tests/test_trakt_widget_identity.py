"""Opaque widget identities use real private stores and fabricated account reads."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore


def reopen_identity(profile):
    return AccountPreferences(profile).widget_snapshot('synthetic-a')


def legacy_profile(profile, version=2):
    directory = Path(profile) / 'trakt'
    directory.mkdir(mode=0o700)
    path = directory / 'preferences.sqlite3'
    with sqlite3.connect(str(path)) as conn:
        conn.execute('CREATE TABLE selections (account TEXT PRIMARY KEY, selected TEXT NOT NULL, revision INTEGER NOT NULL)')
        if version == 2:
            conn.execute('CREATE TABLE preference_state (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL CHECK(epoch>=0))')
            conn.execute('INSERT INTO preference_state VALUES(1,7)')
        conn.execute('PRAGMA user_version=' + str(version))
    path.chmod(0o600)
    return path


class WidgetMigrationTests(unittest.TestCase):
    def test_legacy_versions_migrate_preserving_choices_and_epoch(self):
        from resources.lib.trakt_preferences import _account_key
        for version in (0, 1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as profile:
                path = legacy_profile(profile, version)
                with sqlite3.connect(str(path)) as conn:
                    conn.execute('INSERT INTO selections VALUES(?,?,?)', (_account_key('synthetic-a'), '["trakt-list:1"]', 4))
                store = AccountPreferences(profile)
                epoch, selected, refs = store.widget_snapshot('synthetic-a')
                self.assertEqual(epoch, 7 if version == 2 else 0)
                self.assertEqual(selected, ['trakt-list:1'])
                self.assertRegex(refs[0], '^[a-f0-9]{64}$')
                self.assertEqual(AccountPreferences(profile).widget_snapshot('synthetic-a'), (epoch, selected, refs))
                with sqlite3.connect(str(path)) as conn:
                    self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 3)
                    self.assertEqual(conn.execute('SELECT revision FROM selections').fetchone()[0], 4)
                    self.assertEqual(conn.execute('SELECT length(secret),typeof(secret) FROM widget_identity').fetchone(), (32, 'blob'))

    def test_concurrent_migration_has_one_durable_key(self):
        with tempfile.TemporaryDirectory() as profile:
            path = legacy_profile(profile)
            from resources.lib.trakt_preferences import _account_key
            with sqlite3.connect(str(path)) as conn:
                conn.execute('INSERT INTO selections VALUES(?,?,?)', (_account_key('synthetic-a'), '["trakt-list:1"]', 4))
            with ProcessPoolExecutor(max_workers=3) as pool:
                results = list(pool.map(reopen_identity, [profile] * 6))
            self.assertTrue(all(value == results[0] for value in results))
            store = AccountPreferences(profile)
            store.save('synthetic-a', ['trakt-list:1'])
            first = store.widget_snapshot('synthetic-a')
            self.assertEqual(reopen_identity(profile), first)

    def test_failed_migration_rolls_back_without_guessing_a_key(self):
        with tempfile.TemporaryDirectory() as profile:
            path = legacy_profile(profile)
            with patch('resources.lib.trakt_preferences.os.urandom', side_effect=OSError('synthetic-private')):
                with self.assertRaises(PreferencesError):
                    AccountPreferences(profile)
            with sqlite3.connect(str(path)) as conn:
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], 2)
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='widget_identity'").fetchone())
                self.assertEqual(conn.execute('SELECT epoch FROM preference_state').fetchone()[0], 7)

    def test_existing_corrupt_key_or_schema_is_not_regenerated(self):
        for mutation in ["DELETE FROM widget_identity", "UPDATE widget_identity SET secret=x'00'",
                         "UPDATE widget_identity SET secret='abcdefghijklmnopqrstuvwxyz123456'",
                         "DROP TABLE widget_identity", "PRAGMA user_version=4"]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as profile:
                store = AccountPreferences(profile)
                path = Path(profile) / 'trakt/preferences.sqlite3'
                with sqlite3.connect(str(path)) as conn:
                    conn.execute(mutation)
                before = path.read_bytes()
                with self.assertRaises(PreferencesError):
                    AccountPreferences(profile)
                with self.assertRaises(PreferencesError):
                    store.widget_snapshot('synthetic-a')
                self.assertEqual(path.read_bytes(), before)

    def test_preexisting_key_on_legacy_schema_is_rejected_not_adopted(self):
        with tempfile.TemporaryDirectory() as profile:
            path = legacy_profile(profile)
            with sqlite3.connect(str(path)) as conn:
                conn.execute('CREATE TABLE widget_identity (id INTEGER PRIMARY KEY, secret BLOB NOT NULL)')
                conn.execute('INSERT INTO widget_identity VALUES(1,?)', (b'x' * 32,))
            before = path.read_bytes()
            with self.assertRaises(PreferencesError):
                AccountPreferences(profile)
            self.assertEqual(path.read_bytes(), before)


class WidgetIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.store = TokenStore(self.profile)
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        self.preferences = AccountPreferences(self.profile)
        self.calls, self.intercept = [], lambda path: None
        self.items = [{'type': 'movie', 'movie': {'ids': {'trakt': 11}, 'title': 'Synthetic movie'}},
                      {'type': 'show', 'show': {'ids': {'trakt': 22}, 'title': 'Synthetic show'}}]
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1', 'trakt-list:2'])

    def reopen(self):
        def api(method, path, headers, body=None):
            self.assertEqual(method, 'GET')
            self.assertIsNone(body)
            self.calls.append(path)
            override = self.intercept(path)
            if override is not None:
                return override
            if path == '/users/settings':
                return Response(200, body={'user': {'ids': {'uuid': 'synthetic-b' if headers['Authorization'].endswith('synthetic-b') else 'synthetic-a'}}})
            if path.startswith('/users/me/lists?'):
                return Response(200, body=[{'ids': {'trakt': 1}, 'name': 'Synthetic personal'}])
            if path.startswith('/users/likes/lists?'):
                return Response(200, body=[{'list': {'ids': {'trakt': 2}, 'name': 'Synthetic liked', 'user': {'ids': {'slug': 'synthetic-owner'}}}}])
            if '/items?' in path:
                return Response(200, body=self.items)
            if path == '/shows/22/seasons?extended=full':
                return Response(200, body=[{'number': 1, 'ids': {'trakt': 221}, 'episode_count': 1}])
            if path == '/shows/22/seasons/1?extended=full':
                return Response(200, body=[{'season': 1, 'number': 1, 'ids': {'trakt': 222}, 'title': 'Synthetic episode', 'first_aired': '2020-01-01T00:00:00Z'}])
            if path.startswith('/shows/22/progress/watched?'):
                return Response(200, body={'seasons': [{'number': 1, 'episodes': [{'number': 1, 'completed': False}]}]})
            if path.startswith('/sync/playback?'):
                return Response(200, body=[])
            self.fail('Unexpected read operation')
        session = Session(TokenStore(self.profile), lambda *args: self.fail('No authorization expected'), api,
                          'synthetic-client', 'https://example.invalid/callback', clock=lambda: 1000)
        return Library(session, preferences=AccountPreferences(self.profile))

    def ref(self, index=0):
        return self.library.widget_sources()['items'][index]['ref']

    def test_stable_reopen_rotation_and_ordering_without_identity_in_ref(self):
        sources = self.library.widget_sources()
        refs = [row['ref'] for row in sources['items']]
        self.assertEqual(len(set(refs)), 2)
        for ref in refs:
            self.assertRegex(ref, '^[a-f0-9]{64}$')
            self.assertNotIn('synthetic', ref)
            self.assertNotIn('trakt-list', ref)
        self.assertEqual([row['ref'] for row in self.reopen().widget_sources()['items']], refs)
        self.store.install(TokenSet('synthetic-a', 'synthetic-new-refresh', 11000))
        self.assertEqual([row['ref'] for row in self.reopen().widget_sources()['items']], refs)
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:2', 'trakt-list:1'])
        self.assertEqual([row['ref'] for row in self.library.widget_sources()['items']], refs[::-1])

    def test_account_switch_shared_list_cannot_rebind_locator(self):
        ref = self.ref()
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        other_ref = self.ref()
        self.assertNotEqual(ref, other_ref)
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.library.widget_list(ref)
        self.assertEqual(self.library.widget_list(other_ref)['items'][0]['title'], 'Synthetic movie')

    def test_profile_identity_different_for_same_account_and_list(self):
        ref = self.ref()
        with tempfile.TemporaryDirectory() as other:
            prefs = AccountPreferences(other)
            prefs.save('synthetic-a', ['trakt-list:1'])
            self.assertNotEqual(prefs.widget_snapshot('synthetic-a')[2][0], ref)

    def test_deselect_fails_without_rebinding_and_reselect_restores_same_identity(self):
        ref = self.ref()
        self.library.select_lists(['trakt-list:2'])
        with self.assertRaises(ApiError):
            self.library.widget_list(ref)
        self.library.select_lists(['trakt-list:1'])
        self.assertEqual(self.ref(), ref)

    def test_clear_disconnect_invalidates_old_refs_even_after_same_account_returns(self):
        ref = self.ref()
        self.library.disconnect()
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        self.assertNotEqual(self.ref(), ref)
        with self.assertRaises(ApiError):
            self.library.widget_list(ref)

    def test_item_refs_bound_to_list_account_kind_and_membership(self):
        first, second = self.ref(), self.ref(1)
        payload = self.library.widget_list(first)
        movie, show = payload['items']
        self.assertNotEqual(movie['item_ref'], show['item_ref'])
        other_movie = self.library.widget_list(second)['items'][0]
        self.assertNotEqual(movie['item_ref'], other_movie['item_ref'])
        with self.assertRaises(ApiError):
            self.library.widget_details(second, movie['item_ref'])
        self.assertEqual(self.library.widget_details(first, movie['item_ref'])['items'][0]['trakt_id'], 11)
        self.items = self.items[1:]
        self.library.clear()
        with self.assertRaises(ApiError):
            self.library.widget_details(first, movie['item_ref'])

    def test_show_routes_resolve_membership_before_reading_seasons(self):
        ref = self.ref()
        movie, show = self.library.widget_list(ref)['items']
        with self.assertRaises(ApiError):
            self.library.widget_seasons(ref, movie['item_ref'])
        self.assertEqual(self.library.widget_seasons(ref, show['item_ref'])['items'][0]['season'], 1)
        episodes = self.library.widget_episodes(ref, show['item_ref'], 1)
        self.assertEqual(episodes['items'][0]['trakt_id'], 222)
        self.assertFalse(episodes['items'][0]['watched'])
        episodes['guard']()
        details = self.library.widget_episode_details(ref, show['item_ref'], 1, 1)
        self.assertEqual(details['items'][0]['trakt_id'], 222)
        with self.assertRaises(ApiError):
            self.library.widget_episode_details(ref, show['item_ref'], 1, 2)

    def test_wrong_season_response_never_becomes_episode_or_detail_result(self):
        ref = self.ref()
        show = self.library.widget_list(ref)['items'][1]
        def wrong_season(path):
            if path == '/shows/22/seasons/1?extended=full':
                return Response(200, body=[{'season': 2, 'number': 1, 'ids': {'trakt': 222},
                    'title': 'Synthetic wrong season', 'first_aired': '2020-01-01T00:00:00Z'}])
            return None
        self.intercept = wrong_season
        for operation in (lambda: self.library.widget_episodes(ref, show['item_ref'], 1),
                          lambda: self.library.widget_episode_details(ref, show['item_ref'], 1, 1)):
            with self.assertRaisesRegex(ApiError, 'mismatched_season'):
                operation()

    def test_captured_guard_rejects_clear_deselect_and_reentrant_account_change(self):
        for action in ('clear', 'deselect', 'account'):
            with self.subTest(action=action):
                self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
                self.library = self.reopen()
                self.library.select_lists(['trakt-list:1', 'trakt-list:2'])
                result = self.library.widget_list(self.ref())
                if action == 'clear':
                    self.preferences.clear_all()
                elif action == 'deselect':
                    self.preferences.save('synthetic-a', ['trakt-list:2'])
                else:
                    self.store.install(TokenSet('synthetic-b', 'synthetic-refresh', 10000))
                    self.library.lists()
                with self.assertRaises(AuthError):
                    result['guard']()

    def test_guard_rejects_changed_profile_key_without_disclosing_old_rows(self):
        result = self.library.widget_list(self.ref())
        with sqlite3.connect(str(Path(self.profile) / 'trakt/preferences.sqlite3')) as conn:
            conn.execute('UPDATE widget_identity SET secret=?', (b'z' * 32,))
        with self.assertRaisesRegex(PreferencesError, '^preferences_changed$'):
            result['guard']()

    def test_selection_change_during_read_discards_data(self):
        ref = self.ref()
        def changed(path):
            if '/items?' in path:
                self.preferences.save('synthetic-a', ['trakt-list:2'])
            return None
        self.intercept = changed
        with self.assertRaisesRegex(PreferencesError, '^preferences_changed$'):
            self.library.widget_list(ref)

    def test_invalid_refs_and_season_fail_before_reads(self):
        self.calls.clear()
        for ref in (None, 1, '', 'g' * 64, 'A' * 64, 'a' * 63):
            with self.assertRaises(ApiError):
                self.library.widget_list(ref)
        with self.assertRaises(ApiError):
            self.library.widget_episodes('a' * 64, 'b' * 64, True)
        self.assertEqual(self.calls, [])

    def test_missing_preferences_and_malformed_key_fail_closed(self):
        without = Library(self.library._session)
        with self.assertRaisesRegex(PreferencesError, '^widget_storage_required$'):
            without.widget_sources()
        with sqlite3.connect(str(Path(self.profile) / 'trakt/preferences.sqlite3')) as conn:
            conn.execute('DELETE FROM widget_identity')
        with self.assertRaises(PreferencesError):
            self.library.widget_sources()

    def test_item_reference_invalid_inputs_never_make_reusable_locators(self):
        epoch = self.preferences.snapshot('synthetic-a')[0]
        for pairs in ([('episode', 2)], [('movie', True)], [('show', 0)], [('show', 2 ** 63)], ['movie'], [('show',)]):
            with self.assertRaises(PreferencesError):
                self.preferences.widget_item_refs('synthetic-a', 'trakt-list:1', pairs, epoch)
