"""Browsing precedence and saved-route boundaries with fabricated metadata."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import catalogue, trakt_views as views
from resources.lib.trakt_client import ApiError

TODAY = date(2026, 11, 13)
NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def movie(ident, released):
    return {"ids": {"trakt": ident}, "title": "Invented movie " + str(ident),
            "released": released}


def pause(ident, when, kind="movie", progress=30):
    return {"type": kind, kind: {"ids": {"trakt": ident}},
            "show": {"ids": {"trakt": 70}}, "progress": progress,
            "paused_at": when}


class DemoBrowsingInvariants(unittest.TestCase):
    def test_multiple_unfinished_titles_use_recency_before_release_date(self):
        def item(ident, released, progress=0, played="", watched=False):
            return {"id": ident, "date": released, "progress": progress,
                    "last_played": played, "watched": watched}

        rows = [
            item("watched", "2026-11-13", 90, "2026-11-13", True),
            item("future-paused", "2026-11-15", 80, "2026-11-13"),
            item("unknown-paused", None, 70, "2026-11-13"),
            item("released-new", "2026-11-13"),
            item("resume-old", "2026-11-12", 90, "2026-11-10"),
            item("released-old", "2026-11-01"),
            item("resume-new", "2026-10-01", 10, "2026-11-12"),
            item("future-near", "2026-11-14"),
        ]
        original = deepcopy(rows)
        self.assertEqual([row["id"] for row in catalogue.ordered(rows, TODAY)],
                         ["resume-new", "resume-old", "released-new", "released-old",
                          "future-near", "future-paused", "unknown-paused", "watched"])
        self.assertEqual(rows, original)

    def test_deselection_preserves_existing_list_routes_and_saved_collection(self):
        items = catalogue.catalogue(TODAY)
        for selected in ([], ["series"], ["saved", "weekend"]):
            prefs = {"selected": selected, "saved_movies": ["m3", "m1"]}
            original = deepcopy(prefs)
            with self.subTest(selected=selected):
                self.assertEqual([row["id"] for row in catalogue.view(
                    "list", items, prefs, "weekend", today=TODAY)],
                    ["m1", "m2", "m3", "m4"])
                self.assertEqual([row["id"] for row in catalogue.view(
                    "list", items, prefs, "saved", today=TODAY)], ["m1", "m3"])
                self.assertEqual([row["id"] for row in catalogue.view(
                    "upcoming_movies", items, prefs, today=TODAY)], ["m3"])
                self.assertEqual(prefs, original)


class JoinedBrowsingInvariants(unittest.TestCase):
    def test_movie_groups_keep_future_and_unknown_pauses_behind_aired_unwatched(self):
        metadata = [movie(ident, released) for ident, released in [
            (20, None), (19, "2026-01-01"), (18, "2026-12-01"),
            (17, None), (16, "2026-11-14"), (15, "2026-11-20"),
            (14, "2026-11-13"), (13, "2026-11-01"),
            (12, "2026-01-01"), (11, "2026-11-12")]]
        pauses = [pause(ident, when) for ident, when in [
            (11, "2026-11-12T08:00:00Z"), (12, "2026-11-12T08:00:01Z"),
            (15, "2026-11-13T11:00:00Z"), (17, "2026-11-13T11:30:00Z"),
            (18, "2026-11-13T11:45:00Z"), (20, "2026-11-13T11:55:00Z")]]
        rows = views.movies(metadata, {18, 19, 20}, pauses, NOW)
        self.assertEqual([row["trakt_id"] for row in views.movie_filter(rows)],
                         [12, 11, 14, 13, 16, 15, 17, 18, 19, 20])
        self.assertEqual([row["trakt_id"] for row in views.movie_filter(
            rows, "released_unwatched")], [12, 11, 14, 13])
        watched = {row["trakt_id"]: (row["progress"], row["last_played"])
                   for row in rows if row["watched"] is True}
        self.assertEqual(watched, {18: (0, None), 19: (0, None), 20: (0, None)})

    def test_filtered_episodes_prioritize_later_resumes_without_reordering_folder(self):
        source = []
        for number, aired in [(7, "2026-11-01T00:00:00Z"),
                              (6, None), (5, "2026-11-14T00:00:00Z"),
                              (4, "2026-11-12T00:00:00Z"),
                              (3, "2026-11-02T00:00:00Z"),
                              (2, "2026-11-03T00:00:00Z"),
                              (1, "2026-11-11T00:00:00Z")]:
            source.append({"ids": {"trakt": 200 + number}, "season": 1,
                           "number": number, "title": "Invented episode",
                           "first_aired": aired})
        progress = {"show_id": 70, "progress": {"seasons": [{"number": 1,
            "episodes": [{"number": number, "completed": number == 4}
                         for number in range(1, 7)]}]}}
        pauses = [pause(202, "2026-11-12T10:00:00Z", "episode"),
                  pause(203, "2026-11-12T11:00:00Z", "episode"),
                  pause(204, "2026-11-13T11:00:00Z", "episode"),
                  pause(205, "2026-11-13T11:10:00Z", "episode"),
                  pause(206, "2026-11-13T11:20:00Z", "episode"),
                  pause(207, "2026-11-13T11:30:00Z", "episode")]
        rows = views.episodes({"show_id": 70, "episodes": source}, progress, pauses, NOW)
        self.assertEqual([row["trakt_id"] for row in views.episode_filter(
            rows, "aired_unwatched")], [203, 202, 201])
        self.assertEqual([row["trakt_id"] for row in views.episode_filter(rows)],
                         [201, 202, 203, 204, 205, 206, 207])
        self.assertEqual((rows[3]["progress"], rows[3]["last_played"]), (0, None))
        self.assertIsNone(rows[6]["watched"])

    def test_one_unknown_watched_row_rejects_entire_unwatched_filter(self):
        known = views.movies([movie(1, "2026-11-01")], set(), now=NOW)
        unknown = views.movies([movie(2, "2026-11-02")], now=NOW)
        rows = known + unknown
        original = deepcopy(rows)
        for selection in ("unwatched", "released_unwatched"):
            with self.subTest(selection=selection):
                with self.assertRaisesRegex(ApiError, "watched_status_unavailable"):
                    views.movie_filter(rows, selection)
        self.assertEqual(rows, original)
        self.assertEqual([row["trakt_id"] for row in views.movie_filter(rows)], [1, 2])

    def test_airing_at_exact_utc_instant_is_distinct_from_one_microsecond_future(self):
        metadata = {"show_id": 70, "episodes": [
            {"ids": {"trakt": 1}, "season": 1, "number": 1, "title": "Exact",
             "first_aired": "2026-11-13T15:00:00+03:00"},
            {"ids": {"trakt": 2}, "season": 1, "number": 2, "title": "Future",
             "first_aired": "2026-11-13T07:00:00.000001-05:00"}]}
        progress = {"show_id": 70, "progress": {"seasons": [{"number": 1,
            "episodes": [{"number": 1, "completed": False},
                         {"number": 2, "completed": False}]}]}}
        local_now = NOW.astimezone(timezone(timedelta(hours=-7)))
        rows = views.episodes(metadata, progress, now=local_now)
        self.assertEqual([row["release_status"] for row in rows], ["aired", "upcoming"])
        self.assertEqual([row["trakt_id"] for row in views.episode_filter(
            rows, "aired_unwatched")], [1])

    def test_invalid_movie_dates_remain_unknown_even_with_partial_progress(self):
        for released in ("", "unknown", "2026-02-30", "2025-02-29",
                         "2026-11-12T12:00:00", None):
            with self.subTest(released=released):
                rows = views.movies([movie(1, released)], set(),
                                    [pause(1, "2026-11-12T12:00:00Z")], NOW)
                self.assertEqual(rows[0]["release_status"], "unknown_date")
                self.assertFalse(rows[0]["aired_unwatched"])
                self.assertEqual(views.movie_filter(rows, "released_unwatched"), [])
                self.assertEqual(views.movie_filter(rows, "upcoming"), [])
                self.assertEqual([row["trakt_id"] for row in views.movie_filter(
                    rows, "unwatched")], [1])


if __name__ == "__main__":
    unittest.main()
