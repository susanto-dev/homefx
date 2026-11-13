"""Read-only list journeys with fabricated responses and real private stores."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib import trakt_views


class TraktListJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TokenStore(self.temp.name)
        self.store.install(TokenSet("synthetic-account-a", "synthetic-refresh-a", 10000))
        self.preferences = AccountPreferences(self.temp.name)
        self.calls = []
        self.items = [
            {"type": "movie", "movie": {"ids": {"trakt": 7}, "title": "Synthetic future movie",
                                       "released": "2040-01-01", "year": 2040}},
            {"type": "show", "show": {"ids": {"trakt": 7}, "title": "Synthetic series"}},
        ]
        self.failure = None

        def request(method, path, headers, body=None):
            self.assertEqual(method, "GET")
            self.assertIsNone(body)
            self.calls.append(path)
            if self.failure:
                return self.failure(path)
            if path == "/users/settings":
                account = "a" if headers["Authorization"].endswith("account-a") else "b"
                return Response(200, body={"user": {"ids": {"uuid": "synthetic-uuid-" + account}}})
            if path.startswith("/users/me/lists?"):
                return Response(200, body=[{"ids": {"trakt": 1}, "name": "Synthetic personal"}])
            if path.startswith("/users/likes/lists?"):
                return Response(200, body=[{"list": {"ids": {"trakt": 2}, "name": "Synthetic liked",
                    "user": {"ids": {"slug": "synthetic-owner"}}}}])
            if "/items?" in path:
                return Response(200, body=self.items)
            self.fail("unexpected operation")

        def no_auth(*args):
            self.fail("fresh synthetic tokens must not authorize or refresh")

        self.session = Session(self.store, no_auth, request, "synthetic-client",
                               "https://example.invalid/callback", clock=lambda: 1000)
        self.library = Library(self.session, preferences=self.preferences)
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def test_personal_and_liked_mixed_lists_keep_order_identity_and_unknown_watch_state(self):
        for key, owner in (("trakt-list:1", "me"), ("trakt-list:2", "synthetic-owner")):
            result = self.library.browse_list(key, now=self.now)
            self.assertEqual(result["unsupported_count"], 0)
            rows = result["items"]
            self.assertEqual([row["id"] for row in rows], ["trakt:movie:7", "trakt:show:7"])
            self.assertEqual([row["release_status"] for row in rows], ["upcoming", "unknown"])
            self.assertTrue(all(row["watched"] is None and row["playable"] is False for row in rows))
            self.assertTrue(any(path.startswith("/users/" + owner + "/lists/") for path in self.calls))
            rows[0]["title"] = "Changed returned copy"
            self.assertEqual(self.library.browse_list(key, now=self.now)["items"][0]["title"],
                             "Synthetic future movie")
        self.assertFalse(any("watched" in path or "playback" in path for path in self.calls))

    def test_unsupported_entries_are_explicit_even_when_no_supported_titles_exist(self):
        self.items = [{"type": kind, kind: {"ids": {"trakt": index}}}
                      for index, kind in enumerate(("episode", "season", "person"), 1)]
        self.assertEqual(self.library.browse_list("trakt-list:1"),
                         {"items": [], "unsupported_count": 3})
        self.items = []
        self.library.clear()
        self.assertEqual(self.library.browse_list("trakt-list:1"),
                         {"items": [], "unsupported_count": 0})

    def test_malformed_or_duplicate_entries_fail_instead_of_partial_list(self):
        malformed = [{"type": "other"}, {"type": []}, {"type": "person"},
                     {"type": "show", "show": {"ids": {"trakt": True}, "title": "Bad"}},
                     {"type": "movie", "movie": {"ids": {"trakt": 5}, "title": "Bad\nTitle"}}]
        for item in malformed + [self.items[0]]:
            with self.subTest(item=item):
                with self.assertRaises(ApiError):
                    trakt_views.browse_list([self.items[0], item], now=self.now)

    def test_account_change_during_projection_discards_result(self):
        original = trakt_views.browse_list

        def change(*args):
            result = original(*args)
            self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            return result

        with patch.object(trakt_views, "browse_list", side_effect=change):
            with self.assertRaises(AuthError):
                self.library.browse_list("trakt-list:1")
        self.assertIsNone(self.library._generation)

    def test_failed_enumeration_never_opens_chooser_or_clears_preferences(self):
        self.library.select_lists(["trakt-list:1"])
        self.library.clear()
        self.failure = lambda path: Response(503, body={})
        with self.assertRaises(ApiError):
            self.library.choose_lists(lambda *args: self.fail("dialog must not open"))
        self.assertEqual(self.preferences.load("synthetic-uuid-a"), ["trakt-list:1"])

    def test_choose_personal_and_liked_lists_restores_after_real_store_reopen(self):
        def choose(refs, selected):
            self.assertIsInstance(refs, tuple)
            self.assertEqual(selected, ())
            self.assertEqual([ref.writable for ref in refs], [True, False])
            return [refs[1].key, refs[0].key]

        self.assertEqual([ref.key for ref in self.library.choose_lists(choose)],
                         ["trakt-list:2", "trakt-list:1"])
        reopened = Library(self.session, preferences=AccountPreferences(self.temp.name))
        self.assertEqual([ref.key for ref in reopened.selected_lists()],
                         ["trakt-list:2", "trakt-list:1"])

    def test_cancel_does_not_save_even_if_account_changed_during_dialog(self):
        self.library.select_lists(["trakt-list:1"])

        def cancel(refs, selected):
            self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
            return None

        self.assertIsNone(self.library.choose_lists(cancel))
        self.assertEqual(self.preferences.load("synthetic-uuid-a"), ["trakt-list:1"])
        self.assertEqual(self.preferences.load("synthetic-uuid-b"), [])

    def test_stale_confirmation_rejected_after_account_switch_or_token_rotation(self):
        for account in ("b", "a"):
            with self.subTest(account=account):
                self.store.install(TokenSet("synthetic-account-a", "synthetic-refresh-a", 10000))
                self.library.select_lists(["trakt-list:1"])

                def choose(refs, selected):
                    self.store.install(TokenSet("synthetic-account-" + account, "synthetic-refresh", 10000))
                    return ["trakt-list:2"]

                with self.assertRaises(AuthError):
                    self.library.choose_lists(choose)
                self.assertEqual(self.preferences.load("synthetic-uuid-a"), ["trakt-list:1"])
                self.assertEqual(self.preferences.load("synthetic-uuid-b"), [])

    def test_clear_or_concurrent_choice_during_dialog_rejects_delayed_save(self):
        for clear in (True, False):
            with self.subTest(clear=clear):
                self.library.clear()
                self.library.select_lists(["trakt-list:1"])

                def choose(refs, selected):
                    if clear:
                        self.preferences.clear_all()
                    else:
                        self.preferences.save("synthetic-uuid-a", ["trakt-list:2"])
                    return []

                with self.assertRaisesRegex(AuthError, "preferences_changed"):
                    self.library.choose_lists(choose)
                self.assertEqual(self.preferences.load("synthetic-uuid-a"),
                                 [] if clear else ["trakt-list:2"])

    def test_invalid_confirmation_never_replaces_saved_selection(self):
        for chosen in ("trakt-list:2", ["missing"], ["trakt-list:2", "trakt-list:2"], [True]):
            with self.subTest(chosen=chosen):
                self.library.select_lists(["trakt-list:1"])
                with self.assertRaises(ApiError):
                    self.library.choose_lists(lambda *args: chosen)
                self.assertEqual(self.preferences.load("synthetic-uuid-a"), ["trakt-list:1"])

    def test_incomplete_item_pagination_fails_without_exposing_partial_metadata(self):
        self.library.lists()
        self.failure = lambda path: Response(200, headers={"X-Pagination-Page-Count": "2"}, body=[])
        with self.assertRaisesRegex(ApiError, "invalid_pagination"):
            self.library.browse_list("trakt-list:1")
        self.assertIsNone(self.library._generation)

    def test_mutation_revision_change_during_chooser_rejects_confirmation(self):
        revision = [0]
        with patch.object(self.library, "_data_revision", side_effect=lambda: revision[0]):
            self.library.select_lists(["trakt-list:1"])

            def choose(refs, selected):
                revision[0] += 1
                return ["trakt-list:2"]

            with self.assertRaisesRegex(ApiError, "data_changed"):
                self.library.choose_lists(choose)
        self.assertEqual(self.preferences.load("synthetic-uuid-a"), ["trakt-list:1"])

    def test_invalid_clock_fails_before_account_or_list_requests(self):
        with self.assertRaisesRegex(ApiError, "invalid_clock"):
            self.library.browse_list("trakt-list:1", now="not a clock")
        self.assertEqual(self.calls, [])

    def test_captured_guard_rejects_old_rows_after_reentrant_new_account_read(self):
        self.library.browse_list("trakt-list:1")
        guard = self.library.capture_view_guard()
        self.store.install(TokenSet("synthetic-account-b", "synthetic-refresh-b", 10000))
        self.library.browse_list("trakt-list:1")
        self.library.assert_current_view()
        with self.assertRaises(AuthError):
            guard()
        self.assertIsNone(self.library._generation)

    def test_concurrent_save_after_final_snapshot_is_rejected_atomically(self):
        self.library.select_lists(["trakt-list:1"])
        other = AccountPreferences(self.temp.name)
        original = self.preferences.save

        def interleaved(uuid, keys, **kwargs):
            other.save(uuid, ["trakt-list:2"])
            return original(uuid, keys, **kwargs)

        with patch.object(self.preferences, "save", side_effect=interleaved):
            with self.assertRaisesRegex(AuthError, "preferences_changed"):
                self.library.choose_lists(lambda *args: [])
        self.assertEqual(other.load("synthetic-uuid-a"), ["trakt-list:2"])

    def test_ordered_selection_compare_and_swap_preserves_changed_order(self):
        self.preferences.save("synthetic-uuid-a", ["trakt-list:1", "trakt-list:2"])
        epoch, keys = self.preferences.snapshot("synthetic-uuid-a")
        other = AccountPreferences(self.temp.name)
        other.save("synthetic-uuid-a", list(reversed(keys)))
        self.assertFalse(self.preferences.save("synthetic-uuid-a", [],
                         expected_epoch=epoch, expected_keys=keys))
        self.assertEqual(other.load("synthetic-uuid-a"), list(reversed(keys)))
        self.assertTrue(self.preferences.save("synthetic-uuid-a", [],
                        expected_epoch=epoch, expected_keys=list(reversed(keys))))
        self.assertEqual(other.load("synthetic-uuid-a"), [])

    def test_malformed_list_names_never_reach_chooser(self):
        from resources.lib.trakt_client import Client
        for name in ("", "   ", "Bad\nTitle", "Bad\x00Title", "Hidden\u202eTitle", "x" * 1001):
            for own in (True, False):
                with self.subTest(name=name, own=own):
                    row = {"ids": {"trakt": 1}, "name": name,
                           "user": {"ids": {"slug": "synthetic-owner"}}}
                    with self.assertRaisesRegex(ApiError, "invalid_response"):
                        Client._list(row if own else {"list": row}, own)
        row = {"ids": {"trakt": 1}, "name": "Synthetic list " + "x" * 985}
        self.assertEqual(Client._list(row, True).name, row["name"])

    def test_final_ui_guard_rejects_account_change_after_successful_read(self):
        with self.assertRaises(AuthError):
            self.library.assert_current_view()
        self.library.browse_list("trakt-list:1")
        self.library.assert_current_view()
        self.store.disconnect()
        with self.assertRaises(AuthError):
            self.library.assert_current_view()


if __name__ == "__main__":
    unittest.main()
