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
