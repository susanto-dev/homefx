"""Bounded resume metadata/history joins with invented responses only."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError
from resources.lib.trakt_client import ApiError
from resources.lib.trakt_library import Library

NOW = datetime(2030, 6, 10, tzinfo=timezone.utc)


def movie_pause(ident=1, progress=40, when="2030-06-09T12:00:00Z"):
    return {"type": "movie", "progress": progress, "paused_at": when,
            "movie": {"ids": {"trakt": ident}}}


def episode_pause(ident=11, show=20, season=1, number=1, progress=30,
                  when="2030-06-09T13:00:00Z"):
    return {"type": "episode", "progress": progress, "paused_at": when,
            "show": {"ids": {"trakt": show}},
            "episode": {"ids": {"trakt": ident}, "season": season, "number": number}}


class Session:
    def __init__(self):
        self.generation, self.data_revision = 1, 0
        self.calls, self.hook = [], None
        self.responses = {
            ("paused",): [movie_pause(), episode_pause()],
            ("watched_movies",): (),
            ("movie_details", 1): {"ids": {"trakt": 1}, "title": "Invented movie", "released": "2029-01-01"},
            ("episode_details", 20, 1, 1): {"show_id": 20, "episode": {
                "ids": {"trakt": 11}, "season": 1, "number": 1,
                "title": "Invented episode", "first_aired": "2029-01-01T12:00:00Z"}},
            ("show_progress", 20, False): {"show_id": 20, "progress": {"seasons": [
                {"number": 1, "episodes": [{"number": 1, "completed": False}]}]}},
        }

    def cache_key(self):
        return self.generation

    def assert_current(self, generation):
        if generation != self.generation:
            raise AuthError("session_changed")

    def read(self, operation, *args):
        key = (operation,) + args
        self.calls.append(key)
        if self.hook:
            self.hook(key)
        return deepcopy(self.responses[key])


class EnrichedContinueTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.library = Library(self.session)

    def test_missing_pause_dates_enriched_sorted_and_cached_without_seconds(self):
        rows = self.library.enriched_continue_view(NOW)
        self.assertEqual([row["trakt_id"] for row in rows], [11, 1])
        self.assertEqual([row["progress"] for row in rows], [30, 40])
        self.assertTrue(all(row["watched"] is False and row["playable"] is False for row in rows))
        self.assertTrue(all("resume" not in row and "duration" not in row for row in rows))
        self.assertEqual(len(self.session.calls), 5)
        rows[0]["title"] = "changed"
        self.assertEqual(self.library.enriched_continue_view(NOW)[0]["title"], "Invented episode")
        self.assertEqual(len(self.session.calls), 5)

    def test_watched_history_overrides_stale_pauses_unknown_episode_stays_unknown(self):
        self.session.responses[("watched_movies",)] = (1,)
        self.session.responses[("show_progress", 20, False)]["progress"]["seasons"] = []
        rows = self.library.enriched_continue_view(NOW)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["watched"])
        self.assertFalse(rows[0]["aired_unwatched"])
        self.library.clear()
        self.session.responses[("show_progress", 20, False)]["progress"]["seasons"] = [
            {"number": 1, "episodes": [{"number": 1, "completed": True}]}]
        self.assertEqual(self.library.enriched_continue_view(NOW), [])

    def test_unknown_or_future_release_dates_do_not_become_resume_candidates(self):
        self.session.responses[("movie_details", 1)]["released"] = None
        self.session.responses[("episode_details", 20, 1, 1)]["episode"]["first_aired"] = "2031-01-01T00:00:00Z"
        self.assertEqual(self.library.enriched_continue_view(NOW), [])

    def test_latest_duplicate_wins_and_completion_supersedes_old_pause(self):
        self.session.responses[("paused",)] = [movie_pause(), movie_pause(progress=50, when="2030-06-09T14:00:00Z")]
        self.assertEqual(self.library.enriched_continue_view(NOW)[0]["progress"], 50)
        self.assertEqual(self.session.calls.count(("movie_details", 1)), 1)
        self.library.clear()
        self.session.responses[("paused",)].append(movie_pause(progress=100, when="2030-06-09T15:00:00Z"))
        self.session.calls.clear()
        self.assertEqual(self.library.enriched_continue_view(NOW), [])
        self.assertEqual(self.session.calls, [("paused",)])
        self.library.clear()
        self.session.responses[("paused",)] = [movie_pause(), movie_pause(progress=50)]
        with self.assertRaisesRegex(ApiError, "conflicting_progress"):
            self.library.enriched_continue_view(NOW)

    def test_specials_and_regular_episodes_share_one_explicit_progress_scope(self):
        special = episode_pause(12, season=0, number=2)
        self.session.responses[("paused",)] = [episode_pause(), special]
        self.session.responses[("show_progress", 20, True)] = self.session.responses[("show_progress", 20, False)]
        self.session.responses[("episode_details", 20, 0, 2)] = {"show_id": 20, "episode": {
            "ids": {"trakt": 12}, "season": 0, "number": 2, "title": None,
            "first_aired": "2029-01-01T12:00:00Z"}}
        rows = self.library.enriched_continue_view(NOW)
        self.assertEqual([call for call in self.session.calls if call[0] == "show_progress"],
                         [("show_progress", 20, True)])
        self.assertFalse(any(call[0] == "watched_movies" for call in self.session.calls))
        unknown = next(row for row in rows if row["trakt_id"] == 12)
        self.assertEqual(unknown["title"], "Episode S00E02")
        self.assertTrue(unknown["title_unknown"])
        self.assertIsNone(unknown["watched"])

    def test_mismatched_details_and_conflicting_episode_identity_fail_entire_join(self):
        self.session.responses[("episode_details", 20, 1, 1)]["episode"]["ids"]["trakt"] = 99
        with self.assertRaisesRegex(ApiError, "mismatched_metadata"):
            self.library.enriched_continue_view(NOW)
        self.assertEqual(len(self.library._cache._entries), 0)
        self.session.responses[("paused",)] = [episode_pause(), episode_pause(show=21)]
        self.session.calls.clear()
        with self.assertRaisesRegex(ApiError, "mismatched_show"):
            self.library.enriched_continue_view(NOW)
        self.assertEqual(self.session.calls, [("paused",)])

    def test_invalid_rows_and_bounds_fail_before_enrichment(self):
        cases = [None, [movie_pause()] * 101,
                 [movie_pause(ident=i) for i in range(1, 52)],
                 [movie_pause(progress=float("nan"))], [movie_pause(progress=True)],
                 [movie_pause(when="2031-01-01T00:00:00Z")], [episode_pause(number=0)]]
        for paused in cases:
            with self.subTest(paused_type=type(paused).__name__):
                self.library.clear()
                self.session.calls.clear()
                self.session.responses[("paused",)] = paused
                with self.assertRaises(ApiError):
                    self.library.enriched_continue_view(NOW)
                self.assertEqual(self.session.calls, [("paused",)])

    def test_empty_and_invalid_clock_do_not_trigger_unnecessary_reads(self):
        for now in (False, 0, "", datetime(2030, 1, 1)):
            with self.assertRaisesRegex(ApiError, "invalid_clock"):
                self.library.enriched_continue_view(now)
        self.assertEqual(self.session.calls, [])
        self.session.responses[("paused",)] = []
        self.assertEqual(self.library.enriched_continue_view(NOW), [])
        self.assertEqual(self.session.calls, [("paused",)])

    def test_account_or_revision_change_and_remote_failure_never_return_partial_rows(self):
        for mode in ("account", "revision", "failure"):
            with self.subTest(mode=mode):
                self.setUp()
                def hook(key):
                    if key[0] == "episode_details":
                        if mode == "account":
                            self.session.generation += 1
                        elif mode == "revision":
                            self.session.data_revision += 1
                        else:
                            raise ApiError("service_unavailable")
                self.session.hook = hook
                with self.assertRaises((AuthError, ApiError)):
                    self.library.enriched_continue_view(NOW)
                self.assertEqual(len(self.library._cache._entries), 0)
                self.assertEqual(self.session.calls.count(("episode_details", 20, 1, 1)), 1)
