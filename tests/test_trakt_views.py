"""Fabricated metadata, progress and pause snapshots deliberately disagree."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import trakt_views as views
from resources.lib.trakt_client import ApiError

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def episode(number, aired="2026-11-01T00:00:00Z"):
    return {"ids": {"trakt": 100 + number}, "season": 1, "number": number,
            "title": "Synthetic episode " + str(number), "first_aired": aired}


def snapshot(values):
    return {"show_id": 10, "progress": {"seasons": [
        {"number": 1, "episodes": [{"number": n, "completed": completed} for n, completed in values]}]}}


def pause(ident, show=10, progress=35, when="2026-11-11T21:00:00Z", kind="episode"):
    return {"type": kind, kind: {"ids": {"trakt": ident}},
            "show": {"ids": {"trakt": show}}, "progress": progress, "paused_at": when}


class ViewTests(unittest.TestCase):
    def test_list_optional_details_preserve_identity_and_ignore_invalid_values(self):
        base = {'ids': {'trakt': 1}, 'title': 'Synthetic', 'year': 2026}
        for rating, votes in [(7.5, 12), (0, 1), (10, 2147483647)]:
            row = views.browse_list([{'type': 'movie', 'movie': dict(
                base, overview='Synthetic plot', rating=rating, votes=votes)}], NOW)['items'][0]
            self.assertEqual((row['overview'], row['trakt_rating'], row['trakt_votes']),
                             ('Synthetic plot', rating, votes))
            self.assertIsNone(row['watched'])
            self.assertFalse(row['playable'])
        for rating, votes in [(True, 1), ('8', 1), (8, True), (8, 0), (8, -1),
                              (8, 2147483648), (-1, 1), (11, 1), (float('nan'), 1),
                              (float('inf'), 1), (10**1000, 1), (None, None)]:
            with self.subTest(rating_type=type(rating).__name__, votes=votes):
                row = views.browse_list([{'type': 'show', 'show': dict(
                    base, overview=None, rating=rating, votes=votes)}], NOW)['items'][0]
                self.assertNotIn('trakt_rating', row)
                self.assertNotIn('trakt_votes', row)
                self.assertNotIn('overview', row)
        for overview in ('', '   ', [], 'x' * 4097):
            row = views.browse_list([{'type': 'movie', 'movie': dict(base, overview=overview)}], NOW)['items'][0]
            self.assertNotIn('overview', row)

    def test_episode_folder_is_narrative_and_widgets_prioritize_unfinished(self):
        source = {"show_id": 10, "episodes": [episode(3), episode(1), episode(2)]}
        result = views.episodes(source, snapshot([(1, True), (2, False), (3, False)]),
                                [pause(102), pause(101)], NOW)
        self.assertEqual([x["episode"] for x in result], [1, 2, 3])
        self.assertEqual([x["episode"] for x in views.widget_order(result)], [2, 3, 1])
        self.assertEqual(result[0]["progress"], 0)  # watched wins over stale pause
        self.assertTrue(result[1]["aired_unwatched"])
        self.assertNotIn("playable", result[1])

    def test_future_unknown_and_missing_watch_evidence_never_enter_aired_unwatched(self):
        source = {"show_id": 10, "episodes": [episode(1, "2026-11-12T13:00:00Z"),
                    episode(2, None), episode(3)]}
        result = views.episodes(source, snapshot([(1, False), (2, False)]),
                                [pause(101), pause(102), pause(103)], NOW)
        self.assertEqual([x["release_status"] for x in result], ["upcoming", "unknown_date", "aired"])
        self.assertEqual([x["aired_unwatched"] for x in result], [False, False, False])
        self.assertIsNone(result[2]["watched"])

    def test_episode_pauses_require_show_and_global_episode_id(self):
        source = {"show_id": 10, "episodes": [episode(1)]}
        pauses = [pause(101, show=20), pause(999), pause(101, progress=float("nan")),
                  pause(101, progress=True), pause(101, when="unknown")]
        result = views.episodes(source, snapshot([(1, False)]), pauses, NOW)
        self.assertEqual(result[0]["progress"], 0)
        with self.assertRaisesRegex(ApiError, "mismatched_show"):
            views.episodes(source, {"show_id": 20, "progress": {"seasons": []}}, now=NOW)

    def test_latest_valid_pause_and_timezone_offsets(self):
        source = {"show_id": 10, "episodes": [episode(1, "2026-11-12T14:00:00+03:00")]}
        pauses = [pause(101, progress=20, when="2026-11-11T21:00:00Z"),
                  pause(101, progress=40, when="2026-11-11T23:00:00+01:00")]
        result = views.episodes(source, snapshot([(1, False)]), pauses, NOW)
        self.assertEqual(result[0]["progress"], 40)
        self.assertTrue(result[0]["aired_unwatched"])
        self.assertEqual(result[0]["release_at"].hour, 11)

    def test_extreme_pause_values_are_ignored_for_movies_and_episodes(self):
        movie = {"ids": {"trakt": 1}, "title": "Synthetic", "released": "2026-11-01"}
        source = {"show_id": 10, "episodes": [episode(1)]}
        for progress in (10 ** 400, -(10 ** 400), float("inf"), float("-inf"), float("nan")):
            with self.subTest(progress_type=type(progress).__name__):
                rows = views.movies([movie], set(), [pause(1, kind="movie", progress=progress)], NOW)
                self.assertEqual(rows[0]["progress"], 0)
                rows = views.episodes(source, snapshot([(1, False)]),
                                      [pause(101, progress=progress)], NOW)
                self.assertEqual(rows[0]["progress"], 0)

    def test_movies_include_future_dates_without_claiming_availability(self):
        source = [{"ids": {"trakt": n}, "title": "Synthetic", "released": day}
                  for n, day in [(1, "2026-11-01"), (2, "2027-01-01"),
                                 (3, None), (4, "2026-10-01"), (5, "2026-11-10")]]
        rows = views.movies(source, {4}, [pause(1, kind="movie"), pause(4, kind="movie")], NOW)
        self.assertEqual([r["trakt_id"] for r in views.widget_order(rows)], [1, 5, 2, 3, 4])
        self.assertEqual(rows[1]["release_status"], "upcoming")
        self.assertEqual(rows[3]["progress"], 0)
        unknown_watch = views.movies(source, None, now=NOW)
        self.assertFalse(any(r["aired_unwatched"] for r in unknown_watch))

    def test_duplicate_or_malformed_snapshots_rejected(self):
        with self.assertRaisesRegex(ApiError, "duplicate_metadata"):
            views.episodes({"show_id": 10, "episodes": [episode(1), episode(1)]}, snapshot([]), now=NOW)
        with self.assertRaisesRegex(ApiError, "invalid_progress"):
            views.episodes({"show_id": 10, "episodes": [episode(1)]}, snapshot([(1, "false")]), now=NOW)
        with self.assertRaisesRegex(ApiError, "invalid_clock"):
            views.movies([], now=datetime(2026, 1, 1))

    def test_naive_or_malformed_release_timestamp_stays_unknown(self):
        source = {"show_id": 10, "episodes": [episode(1, "2026-11-01T00:00:00"),
                                              episode(2, "not a date")]}
        result = views.episodes(source, snapshot([(1, False), (2, False)]), now=NOW)
        self.assertTrue(all(r["release_status"] == "unknown_date" for r in result))


    def test_movie_filters_require_complete_watch_evidence(self):
        metadata = [{"ids": {"trakt": n}, "title": "Synthetic", "released": day}
                    for n, day in [(1, "2026-11-01"), (2, "2026-12-01"), (3, None)]]
        unknown = views.movies(metadata, now=NOW)
        for mode in ("unwatched", "released_unwatched"):
            with self.assertRaisesRegex(ApiError, "watched_status_unavailable"):
                views.movie_filter(unknown, mode)
        known = views.movies(metadata, {1}, now=NOW)
        self.assertEqual([r["trakt_id"] for r in views.movie_filter(known, "unwatched")], [2, 3])
        self.assertEqual(views.movie_filter(known, "released_unwatched"), [])
        self.assertEqual([r["trakt_id"] for r in views.movie_filter(unknown, "upcoming")], [2])
        for mode in ([], "invalid"):
            with self.assertRaisesRegex(ApiError, "invalid_filter"):
                views.movie_filter(unknown, mode)

    def test_strict_movie_progress_supersedes_old_pauses_and_watched_wins(self):
        movie = {'ids': {'trakt': 1}, 'title': 'Synthetic', 'released': '2026-01-01'}
        older = pause(1, kind='movie', progress=40, when='2026-11-10T12:00:00Z')
        for progress in (0, 100):
            newer = dict(older, progress=progress, paused_at='2026-11-11T12:00:00Z')
            rows = views.movies([movie], set(), [older, newer], NOW, strict_pauses=True)
            self.assertEqual(views.movie_filter(rows, 'unfinished'), [])
        rows = views.movies([movie], {1}, [older], NOW, strict_pauses=True)
        self.assertEqual(rows[0]['progress'], 0)
        self.assertEqual(views.movie_filter(rows, 'unfinished'), [])
        for bad in (dict(older, progress=float('nan')), dict(older, progress=True),
                    dict(older, paused_at='2099-01-01T00:00:00Z')):
            with self.assertRaises(ApiError): views.movies([movie], set(), [bad], NOW, strict_pauses=True)
        with self.assertRaisesRegex(ApiError, 'conflicting_progress'):
            views.movies([movie], set(), [older, dict(older, progress=50)], NOW, strict_pauses=True)

    def test_continued_uses_latest_valid_pause_and_keeps_watch_unknown(self):
        older = pause(101, when="2026-11-11T21:00:00Z")
        older["episode"] = episode(1)
        newer = dict(older, paused_at="2026-11-11T23:00:00+01:00", progress=45)
        movie = pause(101, kind="movie", when="2026-11-11T21:30:00Z")
        movie["movie"] = {"ids": {"trakt": 101}, "title": "Synthetic movie", "released": "2026-11-01"}
        result = views.continued([movie, older, newer], NOW)
        self.assertEqual([r["kind"] for r in result], ["episode", "movie"])
        self.assertEqual(result[0]["progress"], 45)
        self.assertEqual((result[0]["show_id"], result[0]["season"], result[0]["episode"]), (10, 1, 1))
        self.assertTrue(all(r["watched"] is None and not r["aired_unwatched"] for r in result))
        self.assertTrue(all("playable" not in r for r in result))

    def test_continued_excludes_undated_future_and_malformed_progress(self):
        sources = []
        for n, day in [(1, None), (2, "2026-11-12T12:00:01Z"),
                       (3, "2026-11-12T12:00:00Z")]:
            row = pause(100+n)
            row["episode"] = episode(n, day)
            sources.append(row)
        future_pause = dict(sources[2], paused_at="2026-11-12T12:00:01Z")
        malformed = [dict(sources[2], progress=x) for x in (True, 0, 100, float("nan"), 10**400)]
        self.assertEqual([r["trakt_id"] for r in views.continued(
            sources + [future_pause, None, {"type": "movie"}, {"type": []},
                       {"type": {}}, {"type": None}, {"type": True}, {"type": 1}] + malformed, NOW)], [103])
        conflict = dict(sources[2], show={"ids": {"trakt": 20}})
        with self.assertRaisesRegex(ApiError, "mismatched_show"):
            views.continued([sources[2], conflict], NOW)


if __name__ == "__main__":
    unittest.main()


class SeriesHelpersTests(unittest.TestCase):
    def rows(self):
        source = [episode(1), episode(2), episode(3, "2026-11-10T00:00:00Z"),
                  episode(4, "2027-01-01T00:00:00Z"), episode(5, None), episode(6)]
        source[2].update(season=2, number=1)
        watched = {"show_id": 10, "progress": {"seasons": [
            {"number": 1, "episodes": [{"number": 1, "completed": False},
                {"number": 2, "completed": True}, {"number": 4, "completed": False},
                {"number": 5, "completed": False}]},
            {"number": 2, "episodes": [{"number": 1, "completed": False}]}]}}
        return views.episodes({"show_id": 10, "episodes": source}, watched, [pause(101)], NOW)

    def test_filtered_order_and_summary_preserve_unknown_evidence(self):
        rows = self.rows()
        self.assertEqual([r["trakt_id"] for r in views.episode_filter(rows, "aired_unwatched")], [101, 103])
        self.assertEqual([r["trakt_id"] for r in views.episode_filter(rows)], [101, 102, 104, 105, 106, 103])
        self.assertEqual(views.season_summaries(rows), [
            dict(season=1, total=5, watched=1, unwatched=3, unknown_watched=1,
                 aired_unwatched=1, upcoming=1, unknown_date=1),
            dict(season=2, total=1, watched=0, unwatched=1, unknown_watched=0,
                 aired_unwatched=1, upcoming=0, unknown_date=0)])

    def test_continuation_crosses_season_and_does_not_infer_unknown_is_unwatched(self):
        rows = self.rows()
        immediate, unwatched = views.continuation(rows, 101)
        self.assertEqual(immediate["trakt_id"], 102)
        self.assertTrue(immediate["watched"])
        self.assertEqual(unwatched["trakt_id"], 103)
        immediate, unwatched = views.continuation(rows, 102)
        self.assertEqual(immediate["trakt_id"], 106)
        self.assertIsNone(immediate["watched"])
        self.assertEqual(unwatched["trakt_id"], 103)
        immediate["title"] = "Changed copy"
        self.assertNotEqual(rows[-2]["title"], "Changed copy")
        self.assertEqual(views.continuation(rows, 103), (None, None))

    def test_specials_scope_is_explicit_and_bad_series_rejected(self):
        rows = self.rows()
        special = dict(rows[0], season=0, trakt_id=999, id="trakt:episode:999")
        rows.insert(0, special)
        with self.assertRaisesRegex(ApiError, "episode_not_in_scope"):
            views.continuation(rows, 999)
        self.assertEqual(views.continuation(rows, 999, include_specials=True)[0]["trakt_id"], 101)
        for replacement in (dict(rows[1], show_id=20), dict(rows[1], episode=0),
                            dict(rows[1], release_status=[])):
            with self.subTest(replacement=replacement):
                with self.assertRaises(ApiError):
                    views.season_summaries([rows[0], replacement])
        with self.assertRaisesRegex(ApiError, "duplicate_metadata"):
            views.continuation([rows[1], dict(rows[1])], 101)
        for bad in (True, 0, "101"):
            with self.assertRaises(ApiError):
                views.continuation(rows, bad)
