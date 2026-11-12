"""Library reads and caches are exercised only with fabricated account data."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, ListRef, Response
from resources.lib.trakt_library import Library, MemoryCache
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore


class MemoryCacheTests(unittest.TestCase):
    def test_ttl_and_copy_isolation(self):
        now = [0]
        cache = MemoryCache(clock=lambda: now[0], ttl=5)
        value = [{"synthetic": [1]}]
        cache.put("key", value)
        value[0]["synthetic"].append(2)
        found, cached = cache.get("key")
        self.assertTrue(found)
        self.assertEqual(cached, [{"synthetic": [1]}])
        cached[0]["synthetic"].append(3)
        self.assertEqual(cache.get("key")[1], [{"synthetic": [1]}])
        now[0] = 5
        self.assertEqual(cache.get("key"), (False, None))

    def test_entry_byte_and_row_limits(self):
        cache = MemoryCache(max_entries=1, max_bytes=30, max_rows=2)
        cache.put("first", [1])
        cache.put("second", [2])
        self.assertFalse(cache.get("first")[0])
        self.assertTrue(cache.get("second")[0])
        cache.put("oversized", "x" * 100)
        cache.put("rows", [1, 2, 3])
        cache.put("bad", float("nan"))
        self.assertFalse(cache.get("oversized")[0])
        self.assertFalse(cache.get("rows")[0])
        self.assertFalse(cache.get("bad")[0])
        cache.clear()
        self.assertFalse(cache.get("second")[0])
        zero = MemoryCache(ttl=0)
        zero.put("key", [1])
        self.assertFalse(zero.get("key")[0])


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TokenStore(self.temp.name)
        self.store.install(TokenSet("synthetic-account-a", "synthetic-refresh-a", 10000))
        self.calls, self.now = [], [0]
        self.reply = None

        def api(method, path, headers, body=None):
            self.calls.append(path)
            if self.reply:
                return self.reply(path, headers)
            if path.startswith("/users/me/lists?"):
                title = "Account A" if headers["Authorization"].endswith("account-a") else "Account B"
                return Response(200, body=[{"ids": {"trakt": 1}, "name": title}])
            if path.startswith("/users/likes/lists?"):
                return Response(200, body=[{"list": {"ids": {"trakt": 2}, "name": "Liked",
                    "user": {"ids": {"slug": "synthetic-owner"}}}}])
            return Response(200, body=[{"type": "movie", "movie": {"ids": {"trakt": 10}}}])

        def no_auth(*args):
            raise AssertionError("fresh account must not authenticate")
        self.session = Session(self.store, no_auth, api, "synthetic-client",
                               "https://example.invalid/callback", clock=lambda: 1000)
        self.cache = MemoryCache(clock=lambda: self.now[0], ttl=5)
        self.library = Library(self.session, self.cache)

    def test_list_selection_items_and_copy_isolation(self):
        lists = self.library.lists()
        self.assertEqual([ref.key for ref in lists], ["trakt-list:1", "trakt-list:2"])
        self.assertEqual([ref.writable for ref in lists], [True, False])
        self.library.select_lists(["trakt-list:2", "trakt-list:1"])
        self.assertEqual([x.key for x in self.library.selected_lists()], ["trakt-list:2", "trakt-list:1"])
        self.assertEqual(len(self.calls), 2)
        self.library.list_items("trakt-list:2")
        self.assertIn("/users/synthetic-owner/lists/2/items?", self.calls[-1])
        with self.assertRaisesRegex(ApiError, "unavailable_selection"):
            self.library.select_lists(["trakt-list:999"])
        with self.assertRaisesRegex(ApiError, "unavailable_selection"):
            self.library.select_lists(["trakt-list:1", "trakt-list:1"])

    def test_external_account_change_invalidates_cache_and_selection(self):
        self.library.select_lists(["trakt-list:1"])
        self.assertEqual(self.library.lists()[0].name, "Account A")
        TokenStore(self.temp.name).install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
        self.assertEqual(self.library.lists()[0].name, "Account B")
        self.assertEqual(self.library.selected_lists(), [])
        self.assertEqual(len(self.calls), 4)
        TokenStore(self.temp.name).disconnect()
        with self.assertRaisesRegex(AuthError, "reauthentication_required"):
            self.library.lists()
        self.assertEqual(self.cache._entries, {})

    def test_expiry_refetches_and_errors_are_not_cached(self):
        self.library.lists()
        self.now[0] = 5
        self.library.lists()
        self.assertEqual(len(self.calls), 4)
        self.reply = lambda *args: Response(404)
        for _ in range(2):
            with self.assertRaisesRegex(ApiError, "unavailable"):
                self.library.list_items("trakt-list:1")
        self.assertEqual(len(self.calls), 6)
        self.assertEqual(self.cache._entries, {})

    def test_disconnect_clears_memory_immediately(self):
        self.library.select_lists(["trakt-list:1"])
        self.library.disconnect()
        self.assertEqual(self.cache._entries, {})
        self.assertEqual(self.store.snapshot().state, "disconnected")

    def test_shared_cache_never_crosses_library_account_boundaries(self):
        with tempfile.TemporaryDirectory() as profile:
            other_store = TokenStore(profile)
            other_store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            self.assertEqual(other_store.snapshot().generation, self.store.snapshot().generation)

            def other_api(method, path, headers, body=None):
                if path.startswith('/users/me/lists?'):
                    return Response(200, body=[{'ids': {'trakt': 3}, 'name': 'Account B private'}])
                return Response(200, body=[])

            other_session = Session(other_store, lambda *args: None, other_api,
                                    'synthetic-client', 'https://example.invalid/callback',
                                    clock=lambda: 1000)
            other = Library(other_session, self.cache)
            self.assertEqual(self.library.lists()[0].name, 'Account A')
            self.assertEqual(other.lists()[0].name, 'Account B private')
            self.assertEqual(self.library.lists()[0].name, 'Account A')
            self.assertEqual(other.lists()[0].name, 'Account B private')

    def test_switch_between_list_lookup_and_item_request_cannot_use_old_ref(self):
        original = self.session.cache_key
        calls = [0]
        def switch():
            calls[0] += 1
            if calls[0] == 2:
                self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            return original()
        self.session.cache_key = switch
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.library.list_items("trakt-list:1")
        self.assertEqual(len(self.calls), 2)  # no old list request under new credentials
        self.assertEqual(self.cache._entries, {})

    def test_switch_before_selection_commit_rejects_old_list_refs(self):
        original = self.library.lists
        def switch():
            result = original()
            self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            return result
        self.library.lists = switch
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.library.select_lists(["trakt-list:1"])
        self.assertEqual(self.library._selected, ())

    def test_episode_join_keeps_future_unknown_and_watched_separate(self):
        def reply(path, headers):
            if "/seasons/" in path:
                return Response(200, body=[{"ids": {"trakt": 101}, "title": "Synthetic aired",
                    "season": 1, "number": 1, "first_aired": "2026-11-01T00:00:00Z"},
                    {"ids": {"trakt": 102}, "title": "Synthetic future", "season": 1,
                     "number": 2, "first_aired": "2026-12-01T00:00:00Z"}])
            if "/progress/" in path:
                return Response(200, body={"seasons": [{"number": 1, "episodes": [
                    {"number": 1, "completed": False}, {"number": 2, "completed": False}]}]})
            return Response(200, body=[{"type": "episode", "show": {"ids": {"trakt": 10}},
                 "episode": {"ids": {"trakt": 101}}, "progress": 35,
                 "paused_at": "2026-11-11T12:00:00Z"}])
        self.reply = reply
        result = self.library.episode_view(10, 1, now=datetime(2026, 11, 12, tzinfo=timezone.utc))
        self.assertEqual([x["aired_unwatched"] for x in result], [True, False])
        self.assertEqual([x["progress"] for x in result], [35, 0])
        self.library.episode_view(10, 1, now=datetime(2026, 11, 12, tzinfo=timezone.utc))
        self.assertEqual(len(self.calls), 3)

    def test_episode_view_auth_failure_clears_existing_cache(self):
        self.library.lists()
        self.store.disconnect()
        with self.assertRaisesRegex(AuthError, "reauthentication_required"):
            self.library.episode_view(10, 1)
        self.assertEqual(self.cache._entries, {})


class PersistentLibraryTests(unittest.TestCase):
    def setUp(self):
        from resources.lib.trakt_preferences import AccountPreferences
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TokenStore(self.temp.name)
        self.store.install(TokenSet('synthetic-account-a', 'synthetic-refresh-a', 10000))
        self.preferences = AccountPreferences(self.temp.name)
        self.settings_calls = 0
        self.intercept = None
        self.revision = [0]

        def api(method, path, headers, body=None):
            account = 'b' if headers['Authorization'].endswith('account-b') else 'a'
            if self.intercept:
                result = self.intercept(path, account)
                if result is not None:
                    return result
            if path == '/users/settings':
                self.settings_calls += 1
                return Response(200, body={'user': {'ids': {'uuid': 'synthetic-uuid-' + account,
                                                           'slug': 'mutable-name'}},
                                           'account': {'token': 'must-not-be-cached'}})
            if path.startswith('/users/me/lists?'):
                return Response(200, body=[{'ids': {'trakt': 1}, 'name': 'Private ' + account}])
            return Response(200, body=[])

        self.api = api
        self.session = Session(self.store, lambda *args: None, api, 'synthetic-client',
                               'https://example.invalid/callback', clock=lambda: 1000)
        self.library = Library(self.session, preferences=self.preferences)

    def test_restart_and_same_account_rotation_restore_selection(self):
        self.library.select_lists(['trakt-list:1'])
        restarted = Library(self.session, preferences=self.preferences)
        self.assertEqual([r.key for r in restarted.selected_lists()], ['trakt-list:1'])
        self.store.install(TokenSet('synthetic-account-a', 'new-synthetic-refresh', 20000))
        self.assertEqual([r.key for r in restarted.selected_lists()], ['trakt-list:1'])
        self.assertEqual(self.settings_calls, 3)
        cached = repr(restarted._cache._entries)
        self.assertNotIn('must-not-be-cached', cached)
        self.assertNotIn('mutable-name', cached)

    def test_distinct_accounts_and_disconnect_forget_local_choices(self):
        self.library.select_lists(['trakt-list:1'])
        self.store.install(TokenSet('synthetic-account-b', 'synthetic-refresh-b', 10000))
        self.assertEqual(self.library.selected_lists(), [])
        self.library.select_lists(['trakt-list:1'])
        self.assertEqual(self.library.selected_lists()[0].name, 'Private b')
        self.store.install(TokenSet('synthetic-account-a', 'synthetic-refresh-a', 10000))
        self.assertEqual(self.library.selected_lists()[0].name, 'Private a')
        Library(self.session, preferences=self.preferences).disconnect()  # no prior identity read
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), [])
        self.assertEqual(self.preferences.load('synthetic-uuid-b'), [])
        self.assertEqual(self.store.snapshot().state, 'disconnected')

    def test_missing_identity_or_removed_list_is_not_silently_accepted(self):
        self.intercept = lambda path, account: Response(200, body={'user': {'ids': {'slug': 'only-slug'}}}) if path == '/users/settings' else None
        with self.assertRaisesRegex(AuthError, 'invalid_account_identity'):
            self.library.select_lists(['trakt-list:1'])
        self.intercept = None
        self.preferences.save('synthetic-uuid-a', ['trakt-list:999'])
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.library.selected_lists()
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), ['trakt-list:999'])

    def test_switch_during_identity_lookup_cannot_load_another_account(self):
        def intercept(path, account):
            if path == '/users/settings':
                self.store.install(TokenSet('synthetic-account-b', 'synthetic-refresh-b', 10000))
            return None
        self.intercept = intercept
        with self.assertRaisesRegex(AuthError, 'session_changed'):
            self.library.selected_lists()
        self.assertIsNone(self.library._account)
        self.assertEqual(self.library._selected, ())

    def test_switch_during_save_never_writes_new_accounts_selection(self):
        original = self.preferences.save
        def save(uuid, keys, **kwargs):
            self.store.install(TokenSet('synthetic-account-b', 'synthetic-refresh-b', 10000))
            return original(uuid, keys, **kwargs)
        self.preferences.save = save
        with self.assertRaisesRegex(AuthError, 'session_changed'):
            self.library.select_lists(['trakt-list:1'])
        self.assertEqual(self.preferences.load('synthetic-uuid-b'), [])
        self.assertEqual(self.library._selected, ())

    def test_data_revision_invalidates_cache_but_keeps_selection(self):
        class RevisionSession:
            def __init__(self, inner):
                self.inner, self.data_revision = inner, 0
            def __getattr__(self, key):
                return getattr(self.inner, key)
        wrapped = RevisionSession(self.session)
        library = Library(wrapped, preferences=self.preferences)
        library.select_lists(['trakt-list:1'])
        self.intercept = lambda path, account: Response(200, body=[{'ids': {'trakt': 1}, 'name': 'Changed'}]) if path.startswith('/users/me/lists?') else None
        self.assertEqual(library.selected_lists()[0].name, 'Private a')
        wrapped.data_revision += 1
        self.assertEqual(library.selected_lists()[0].name, 'Changed')
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), ['trakt-list:1'])
        self.assertEqual(self.settings_calls, 1)

    def test_mutation_during_read_discards_results_and_preserves_saved_selection(self):
        self.preferences.save('synthetic-uuid-a', ['trakt-list:1'])
        class RevisionSession:
            def __init__(self, inner):
                self.inner, self.data_revision = inner, 0
            def __getattr__(self, key):
                return getattr(self.inner, key)
        wrapped = RevisionSession(self.session)
        library = Library(wrapped, preferences=self.preferences)
        def mutate(path, account):
            if path.startswith('/users/me/lists?'):
                wrapped.data_revision += 1
            return None
        self.intercept = mutate
        with self.assertRaisesRegex(ApiError, 'data_changed'):
            library.selected_lists()
        self.assertEqual(library._cache._entries, {})
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), ['trakt-list:1'])

    def test_disconnect_blocks_an_already_pending_selection_save(self):
        from resources.lib.trakt_preferences import AccountPreferences
        other_preferences = AccountPreferences(self.temp.name)
        other_session = Session(TokenStore(self.temp.name), lambda *args: None, self.api,
                                'synthetic-client', 'https://example.invalid/callback',
                                clock=lambda: 1000)
        other_library = Library(other_session, preferences=other_preferences)
        original_save = self.preferences.save
        def interrupted_save(uuid, keys, **kwargs):
            other_library.disconnect()
            return original_save(uuid, keys, **kwargs)
        self.preferences.save = interrupted_save
        with self.assertRaises(AuthError):
            self.library.select_lists(['trakt-list:1'])
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), [])
        self.assertEqual(self.store.snapshot().state, 'disconnected')

    def test_disconnect_invalidates_credentials_before_preference_clear_window(self):
        from resources.lib.trakt_preferences import AccountPreferences
        other_preferences = AccountPreferences(self.temp.name)
        other_library = Library(self.session, preferences=other_preferences)
        original_clear = other_preferences.clear_all
        attempts = []
        def interleaved_clear():
            original_clear()
            pending = Library(self.session, preferences=self.preferences)
            try:
                pending.select_lists(['trakt-list:1'])
                attempts.append('saved')
            except AuthError:
                attempts.append('blocked')
        other_preferences.clear_all = interleaved_clear
        other_library.disconnect()
        self.assertEqual(attempts, ['blocked'])
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), [])

    def test_confirmed_disconnect_preserves_preferences_on_generation_mismatch(self):
        self.library.select_lists(['trakt-list:1'])
        stale = self.store.snapshot().generation
        self.store.disconnect()
        self.assertFalse(self.library.disconnect(expected_generation=stale))
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), ['trakt-list:1'])
        current = self.store.snapshot().generation
        self.assertTrue(self.library.disconnect(expected_generation=current))
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), [])

    def test_disconnect_attempts_both_cleanup_steps_when_one_fails(self):
        self.library.select_lists(['trakt-list:1'])
        original_disconnect = self.session.disconnect
        def failed_disconnect():
            raise AuthError('token_store_unavailable')
        self.session.disconnect = failed_disconnect
        with self.assertRaisesRegex(AuthError, 'token_store_unavailable'):
            self.library.disconnect()
        self.assertEqual(self.preferences.load('synthetic-uuid-a'), [])
        self.session.disconnect = original_disconnect
        def failed_clear():
            raise AuthError('preferences_unavailable')
        self.preferences.clear_all = failed_clear
        with self.assertRaisesRegex(AuthError, 'preferences_unavailable'):
            self.library.disconnect()
        self.assertEqual(self.store.snapshot().state, 'disconnected')
