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

    def test_metadata_order_unknown_state_and_cache_copy(self):
        media = [{"ids": {"trakt": 20}, "title": "Z"}, {"ids": {"trakt": 10}, "title": "A", "year": 2030}]
        self.reply = lambda path, headers: Response(200, body=(
            [{"type": "movie", "movie": row} for row in media] if path.startswith("/search/") else media))
        rows = self.library.search_titles("Synthetic")
        self.assertEqual([row["trakt_id"] for row in rows], [20, 10])
        self.assertTrue(all(row["watched"] is None and not row["playable"] for row in rows))
        self.assertTrue(all(row["release_status"] == "unknown" for row in rows))
        rows[0]["title"] = "Edited"
        self.assertEqual(self.library.search_titles("Synthetic")[0]["title"], "Z")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.library.related_movies(1)[0]["trakt_id"], 20)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(any("watched" in path or "playback" in path for path in self.calls))

    def test_metadata_account_and_revision_changes_discard_results(self):
        def replace(path, headers):
            self.store.install(TokenSet("synthetic-new", "synthetic-refresh", 10000))
            return Response(200, body=[])
        self.reply = replace
        with self.assertRaises(AuthError):
            self.library.related_movies(1)
        from unittest.mock import patch
        self.reply = lambda path, headers: Response(200, body=[])
        revision = [0]
        with patch.object(self.library, "_data_revision", side_effect=lambda: revision[0]):
            def normalize(*args, **kwargs):
                revision[0] += 1
                return []
            with patch("resources.lib.trakt_library.metadata_rows", side_effect=normalize):
                with self.assertRaisesRegex(ApiError, "data_changed"):
                    self.library.search_titles("Synthetic")
        self.assertIsNone(self.library._generation)

    def test_invalid_metadata_query_does_not_activate_account(self):
        with self.assertRaises(ApiError):
            self.library.search_titles("\n")
        with self.assertRaises(ApiError):
            self.library.related_movies(0)
        self.assertEqual(self.calls, [])

    def _view_reply(self, path, headers):
        if path.startswith("/users/me/lists?"):
            return Response(200, body=[{"ids": {"trakt": 1}, "name": "Synthetic list"}])
        if path.startswith("/users/likes/lists?"):
            return Response(200, body=[])
        if "/items?" in path:
            return Response(200, body=[{"type": "movie", "movie": {
                "ids": {"trakt": ident}, "title": "Synthetic movie", "released": day}}
                for ident, day in [(10, "2026-11-01"), (11, "2026-12-01"), (12, None)]])
        if path == "/users/me/watched/movies":
            return Response(200, body=[{"plays": 1, "movie": {"ids": {"trakt": 12}}}])
        if "/seasons/" in path:
            return Response(200, body=[{"ids": {"trakt": n}, "title": "Synthetic episode",
                "season": 1, "number": n, "first_aired": "2026-11-01T00:00:00Z"}
                for n in (1, 2, 3)])
        if "/progress/" in path:
            return Response(200, body={"seasons": [{"number": 1, "episodes": [
                {"number": 1, "completed": False}, {"number": 2, "completed": True}]}]})
        return Response(200, body=[{"type": "movie", "movie": {
            "ids": {"trakt": 10}, "title": "Synthetic movie", "released": "2026-11-01"},
            "progress": 42, "paused_at": "2026-11-11T12:00:00Z"}])

    def test_movie_views_join_watched_snapshot_and_filter_future_dates(self):
        self.reply = self._view_reply
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        rows = self.library.movie_view("trakt-list:1", now)
        self.assertEqual({r["trakt_id"] for r in rows}, {10, 11, 12})
        self.assertEqual({r["trakt_id"]: r["watched"] for r in rows},
                         {10: False, 11: False, 12: True})
        self.assertEqual(next(r for r in rows if r["trakt_id"] == 10)["progress"], 42)
        future = self.library.movie_view("trakt-list:1", now, "upcoming")
        self.assertEqual([r["trakt_id"] for r in future], [11])
        requests = len(self.calls)
        self.assertEqual([r["trakt_id"] for r in self.library.movie_view(
            "trakt-list:1", now, "unwatched")], [10, 11])
        self.assertEqual([r["trakt_id"] for r in self.library.movie_view(
            "trakt-list:1", now, "released_unwatched")], [10])
        self.assertEqual(len(self.calls), requests)
        self.assertEqual(self.calls.count("/users/me/watched/movies"), 1)

    def test_empty_snapshot_is_evidence_but_failed_or_partial_snapshot_is_not(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        snapshot = [Response(200, body=[])]
        def reply(path, headers):
            return snapshot[0] if path == "/users/me/watched/movies" else self._view_reply(path, headers)
        self.reply = reply
        self.assertTrue(all(row["watched"] is False for row in
                            self.library.movie_view("trakt-list:1", now)))
        for bad in (Response(500), Response(200, body=[{}]),
                    Response(200, {"X-Pagination-Page": "1"}, [])):
            self.library.clear()
            snapshot[0] = bad
            with self.assertRaises(ApiError):
                self.library.movie_view("trakt-list:1", now, "unwatched")
            self.assertEqual(self.cache._entries, {})
        snapshot[0] = Response(200, body=[])
        self.assertEqual(len(self.library.movie_view("trakt-list:1", now, "unwatched")), 3)

    def test_account_or_revision_change_during_watched_join_rejects_result(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        def switch(path, headers):
            if path == "/users/me/watched/movies":
                self.store.install(TokenSet("synthetic-new", "synthetic-refresh-new", 10000))
                return Response(200, body=[])
            return self._view_reply(path, headers)
        self.reply = switch
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.library.movie_view("trakt-list:1", now, "unwatched")
        self.assertEqual(self.cache._entries, {})
        def revise(path, headers):
            if path == "/users/me/watched/movies":
                self.session.data_revision += 1
                return Response(200, body=[])
            return self._view_reply(path, headers)
        self.reply = revise
        with self.assertRaisesRegex(ApiError, "data_changed"):
            self.library.movie_view("trakt-list:1", now, "unwatched")
        self.assertEqual(self.cache._entries, {})

    def test_movie_watched_cache_is_invalidated_after_explicit_history_write(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        watched, mutations = [], []
        def reply(path, headers):
            if path == "/users/me/watched/movies":
                return Response(200, body=[{"plays": 1, "movie": {"ids": {"trakt": ident}}}
                                           for ident in watched])
            return self._view_reply(path, headers)
        def mutate(method, path, headers, body):
            mutations.append(path)
            watched.append(body["movies"][0]["ids"]["trakt"])
            return Response(200, body={"added": {"movies": 1, "episodes": 0},
                                      "updated": {"movies": 0, "episodes": 0}, "not_found": {}})
        self.reply = reply
        self.session._mutation = mutate
        self.assertEqual(len(self.library.movie_view("trakt-list:1", now, "released_unwatched")), 1)
        self.assertEqual(self.session.mutate("mark_watched", "movie", 10, now).outcome, "confirmed")
        self.assertEqual(self.library.movie_view("trakt-list:1", now, "released_unwatched"), [])
        self.assertEqual(mutations, ["/sync/history"])
        self.assertEqual(self.calls.count("/users/me/watched/movies"), 2)

    def test_movie_watched_snapshot_refetches_after_refresh(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        clock, watched, reads, refreshes = [1000], [], [], []
        self.store.install(TokenSet("synthetic-old", "synthetic-refresh-old", 1100))
        def api(method, path, headers, body=None):
            reads.append(path)
            if path == "/users/me/watched/movies":
                return Response(200, body=[{"plays": 1, "movie": {"ids": {"trakt": ident}}}
                                           for ident in watched])
            return self._view_reply(path, headers)
        def oauth(method, path, body):
            refreshes.append(path)
            return Response(200, body=dict(access_token="synthetic-refreshed",
                refresh_token="synthetic-refreshed-refresh", token_type="bearer",
                created_at=clock[0], expires_in=3600))
        library = Library(Session(self.store, oauth, api, "synthetic-client",
            "https://example.invalid/callback", clock=lambda: clock[0]))
        self.assertEqual(len(library.movie_view("trakt-list:1", now, "released_unwatched")), 1)
        watched.append(10)
        clock[0] = 1050
        self.assertEqual(library.movie_view("trakt-list:1", now, "released_unwatched"), [])
        self.assertEqual(refreshes, ["/oauth/token"])
        self.assertEqual(reads.count("/users/me/watched/movies"), 2)

    def test_continue_view_and_episode_filter_do_not_invent_watch_evidence(self):
        self.reply = self._view_reply
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        rows = self.library.continue_view(now)
        self.assertEqual([r["trakt_id"] for r in rows], [10])
        self.assertIsNone(rows[0]["watched"])
        episodes = self.library.episode_view(1, 1, now, "aired_unwatched")
        self.assertEqual([r["episode"] for r in episodes], [1])
        self.assertEqual(len(self.library.episode_view(1, 1, now)), 3)
        for mode in ([], "invalid"):
            with self.assertRaisesRegex(ApiError, "invalid_filter"):
                self.library.episode_view(1, 1, now, mode)

    def test_movie_join_rejects_account_and_data_changes_after_list_read(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        self.reply = self._view_reply
        original = self.library.list_items
        def switch(key):
            result = original(key)
            self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            return result
        self.library.list_items = switch
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.library.movie_view("trakt-list:1", now)
        self.assertFalse(any(path.startswith("/sync/playback") for path in self.calls))
        self.assertEqual(self.cache._entries, {})
        def revise(key):
            result = original(key)
            self.session.data_revision += 1
            return result
        self.library.list_items = revise
        with self.assertRaisesRegex(ApiError, "data_changed"):
            self.library.movie_view("trakt-list:1", now)
        self.assertEqual(self.cache._entries, {})

    def test_continue_view_rechecks_generation_after_normalization(self):
        from unittest.mock import patch
        from resources.lib import trakt_views
        self.reply = self._view_reply
        original = trakt_views.continued
        def switch(rows, now):
            result = original(rows, now)
            self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            return result
        with patch.object(trakt_views, "continued", switch):
            with self.assertRaisesRegex(AuthError, "session_changed"):
                self.library.continue_view(datetime(2026, 11, 12, 12, tzinfo=timezone.utc))
        self.assertEqual(self.cache._entries, {})

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


class CompleteSeriesTests(unittest.TestCase):
    """A fake session exposes deliberate account changes between component reads."""
    def setUp(self):
        from copy import deepcopy
        self.calls = []
        self.generation = 1
        self.revision = 0
        self.responses = {
            ("show_seasons", 10): {"show_id": 10, "seasons": [
                {"number": n, "ids": {"trakt": 100 + n}} for n in (2, 0, 1)]},
            ("show_progress", 10, False): {"show_id": 10, "progress": {"seasons": [
                {"number": 1, "episodes": [{"number": 1, "completed": False}]},
                {"number": 2, "episodes": [{"number": 1, "completed": True}]}]}},
            ("paused",): [],
        }
        for season in (0, 1, 2):
            self.responses[("season_episodes", 10, season)] = {"show_id": 10, "episodes": [{
                "season": season, "number": 1, "ids": {"trakt": 200 + season},
                "title": "Synthetic", "first_aired": "2026-11-01T00:00:00Z"}]}
        self.hook = lambda key: None
        owner = self

        class FakeSession:
            @property
            def data_revision(self):
                return owner.revision

            def cache_key(self):
                return owner.generation

            def assert_current(self, generation):
                if generation != owner.generation:
                    raise AuthError("session_changed")

            def read(self, operation, *args):
                key = (operation,) + args
                owner.calls.append(key)
                value = deepcopy(owner.responses[key])
                owner.hook(key)
                return value

        self.library = Library(FakeSession())
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)

    def test_complete_regular_series_one_progress_pause_and_cached_copies(self):
        result = self.library.series_view(10, now=self.now)
        self.assertEqual([row["season"] for row in result], [1, 2])
        self.assertEqual([row["watched"] for row in result], [False, True])
        self.assertEqual(self.calls, [("show_seasons", 10), ("season_episodes", 10, 1),
            ("season_episodes", 10, 2), ("show_progress", 10, False), ("paused",)])
        result[0]["title"] = "Changed copy"
        self.assertEqual(self.library.series_view(10, now=self.now,
            episode_filter="aired_unwatched")[0]["title"], "Synthetic")
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(len(self.library.series_seasons(10, now=self.now)), 2)

    def test_specials_require_optin_and_matching_progress_scope(self):
        self.responses[("show_progress", 10, True)] = self.responses[("show_progress", 10, False)]
        rows = self.library.series_view(10, now=self.now, include_specials=True)
        self.assertEqual([row["season"] for row in rows], [0, 1, 2])
        self.assertIsNone(rows[0]["watched"])
        self.assertIn(("show_progress", 10, True), self.calls)
        self.assertFalse(rows[0]["aired_unwatched"])

    def test_invalid_inputs_do_not_activate_or_request(self):
        for values in ({"show_id": True}, {"show_id": 0}, {"show_id": 10, "include_specials": 1},
                       {"show_id": 10, "episode_filter": []}, {"show_id": 10, "now": 0}):
            with self.subTest(values=values), self.assertRaises(ApiError):
                self.library.series_view(**values)
        self.assertEqual(self.calls, [])

    def test_budgets_fail_without_partial_result_and_clear_cache(self):
        self.responses[("show_seasons", 10)]["seasons"] = [
            {"number": n, "ids": {"trakt": n}} for n in range(1, 52)]
        with self.assertRaisesRegex(ApiError, "series_limit_exceeded"):
            self.library.series_view(10)
        self.assertEqual(self.calls, [("show_seasons", 10)])
        self.responses[("show_seasons", 10)]["seasons"] = [{"number": 1, "ids": {"trakt": 1}}]
        self.responses[("season_episodes", 10, 1)]["episodes"] *= 5001
        with self.assertRaisesRegex(ApiError, "series_limit_exceeded"):
            self.library.series_view(10)
        self.assertIsNone(self.library._generation)
        self.assertNotIn(("paused",), self.calls)

    def test_bad_wrappers_duplicates_and_season_mismatch_fail_closed(self):
        from copy import deepcopy
        original = deepcopy(self.responses)
        changes = [(("show_seasons", 10), {"show_id": 20, "seasons": []}),
                   (("show_seasons", 10), {"show_id": 10, "seasons": [
                       {"number": 1, "ids": {"trakt": 1}}, {"number": 1, "ids": {"trakt": 2}}]}),
                   (("season_episodes", 10, 1), {"show_id": 10, "episodes": [{"season": 2}]}),
                   (("season_episodes", 10, 2), deepcopy(original[("season_episodes", 10, 1)]))]
        for key, value in changes:
            self.responses = deepcopy(original)
            self.responses[key] = value
            with self.subTest(key=key), self.assertRaises(ApiError):
                self.library.series_view(10)
            self.assertIsNone(self.library._generation)

    def test_account_revision_and_read_failure_abort_the_entire_join(self):
        for failure in ("account", "revision", "error"):
            self.library.clear()
            self.calls.clear()

            def change(key):
                if key == ("season_episodes", 10, 2):
                    if failure == "account":
                        self.generation += 1
                    elif failure == "revision":
                        self.revision += 1
                    else:
                        raise ApiError("cancelled")
            self.hook = change
            with self.subTest(failure=failure), self.assertRaises((AuthError, ApiError)):
                self.library.series_view(10)
            self.assertIsNone(self.library._generation)
            self.assertNotIn(("show_progress", 10, False), self.calls)


    def test_advertised_count_mismatch_and_cross_season_duplicate_fail_closed(self):
        self.responses[("show_seasons", 10)]["seasons"][-1]["episode_count"] = 2
        with self.assertRaisesRegex(ApiError, "incomplete_series"):
            self.library.series_view(10)
        self.assertEqual(self.calls, [("show_seasons", 10), ("season_episodes", 10, 1)])
        self.responses[("show_seasons", 10)]["seasons"][-1]["episode_count"] = 1
        self.responses[("season_episodes", 10, 2)]["episodes"][0]["ids"]["trakt"] = 201
        with self.assertRaisesRegex(ApiError, "duplicate_metadata"):
            self.library.series_view(10)
        self.assertIsNone(self.library._generation)

    def test_summary_generation_is_rechecked_after_derivation(self):
        from unittest.mock import patch
        def summarize(rows):
            self.generation += 1
            return []
        with patch("resources.lib.trakt_library.trakt_views.season_summaries", side_effect=summarize):
            with self.assertRaisesRegex(AuthError, "session_changed"):
                self.library.series_seasons(10)
        self.assertIsNone(self.library._generation)
