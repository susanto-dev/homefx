"""Distinct selected-show views with fabricated metadata and private stores."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib import trakt_views
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_preferences import AccountPreferences
from widget_fixtures import WidgetDirectoryFixture

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def row(season, episode, *, status='aired', watched=False, progress=0,
        release=None, pause=None):
    return dict(kind='episode', show_id=20, trakt_id=season * 100 + episode,
                season=season, episode=episode, watched=watched,
                release_status=status, release_at=release or NOW - timedelta(days=1),
                progress=progress, last_played=pause)


def positions(rows):
    return [(item['season'], item['episode']) for item in rows]


class ShowProgressSelectionTests(unittest.TestCase):
    def test_next_is_one_narrative_first_not_newest_airdate_or_pause(self):
        rows = [row(2, 1, progress=50, pause=NOW), row(1, 2),
                row(1, 1, watched=True), row(1, 3, release=NOW - timedelta(days=20)),
                row(0, 1), row(1, 4, watched=None), row(1, 5, status='upcoming')]
        before = deepcopy(rows)
        self.assertEqual(positions(trakt_views.show_progress(rows, 'next')), [(1, 2)])
        self.assertEqual(rows, before)

    def test_continue_requires_known_unwatched_aired_resumable_pause(self):
        rows = [row(2, 1, progress=20, pause=NOW), row(1, 2, progress=50, pause=NOW),
                row(1, 1, progress=90, pause=NOW - timedelta(days=1)),
                row(1, 3, watched=True, progress=40, pause=NOW),
                row(1, 4, watched=None, progress=40, pause=NOW),
                row(1, 5, status='upcoming', progress=40, pause=NOW),
                row(1, 6, progress=100, pause=NOW), row(1, 7, progress=0, pause=NOW),
                row(1, 8, progress=20), row(0, 1, progress=20, pause=NOW),
                row(1, 9, status='unknown_date', progress=20, pause=NOW)]
        self.assertEqual(positions(trakt_views.show_progress(rows, 'continue')),
                         [(1, 2), (2, 1), (1, 1)])

    def test_upcoming_orders_dates_and_preserves_unknown_watched(self):
        first, later = NOW + timedelta(days=1), NOW + timedelta(days=3)
        rows = [row(1, 1, status='upcoming', release=later),
                row(2, 2, status='upcoming', release=first, watched=None),
                row(2, 1, status='upcoming', release=first),
                row(1, 2, status='upcoming', release=first, watched=True),
                row(0, 1, status='upcoming', release=first), row(1, 3),
                row(1, 4, status='unknown_date')]
        result = trakt_views.show_progress(rows, 'upcoming')
        self.assertEqual(positions(result), [(2, 1), (2, 2), (1, 1)])
        self.assertIsNone(result[1]['watched'])

    def test_empty_and_unknown_evidence_do_not_create_next_or_continue(self):
        for choice in ('continue', 'next', 'upcoming'):
            self.assertEqual(trakt_views.show_progress([], choice), [])
        rows = [row(1, 1, watched=None), row(1, 2, status='unknown_date')]
        self.assertEqual(trakt_views.show_progress(rows, 'next'), [])
        self.assertEqual(trakt_views.show_progress(rows, 'continue'), [])

    def test_invalid_selection_identity_dates_and_progress_fail_closed(self):
        for choice in (None, True, [], 'all', 'NEXT'):
            with self.subTest(choice=choice), self.assertRaisesRegex(ApiError, 'invalid_filter'):
                trakt_views.show_progress([], choice)
        invalid = [dict(row(1, 1), show_id=30), row(1, 1),
                   dict(row(2, 1), release_at=None), dict(row(2, 1), release_at=NOW.replace(tzinfo=None)),
                   dict(row(2, 1), progress=float('nan')), dict(row(2, 1), progress=True),
                   dict(row(2, 1), last_played='private malformed pause')]
        for bad in invalid:
            with self.subTest(keys=tuple(bad)), self.assertRaises(ApiError):
                trakt_views.show_progress([row(1, 1), bad], 'next')


class SelectedShowProgressTests(WidgetDirectoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.ref = self.library.widget_sources()['items'][0]['ref']
        self.show_ref = self.library.widget_list(self.ref)['items'][1]['item_ref']
        self.hook = lambda path: None
        self.fail_path = None
        self.incomplete = False
        self.intercept = self.series
        self.calls.clear()
        clock = patch.object(trakt_views, '_now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)

    def series(self, path):
        self.hook(path)
        if path == self.fail_path:
            return Response(503)
        if path == '/shows/20/seasons?extended=full':
            return Response(200, body=[{'number': n, 'ids': {'trakt': 200 + n},
                                       'episode_count': 2} for n in (1, 2)])
        if path in ('/shows/20/seasons/1?extended=full', '/shows/20/seasons/2?extended=full'):
            season = int(path.split('/')[4].split('?')[0])
            episodes = [{'ids': {'trakt': season * 100 + number}, 'season': season,
                         'number': number, 'title': 'Synthetic episode',
                         'first_aired': ('2026-11-14T00:00:00Z' if season == 1 else
                                         '2026-11-15T00:00:00Z')} for number in (1, 2)]
            return Response(200, body=episodes[:1] if self.incomplete else episodes)
        if path.startswith('/shows/20/progress/watched?'):
            return Response(200, body={'seasons': [{'number': 1, 'episodes': [
                {'number': 1, 'completed': True}, {'number': 2, 'completed': False}]}]})
        if path.startswith('/sync/playback?'):
            return Response(200, body=[{'type': 'episode', 'show': {'ids': {'trakt': 20}},
                'episode': {'ids': {'trakt': 102}}, 'progress': 42,
                'paused_at': '2026-11-13T23:00:00Z'}])
        return None

    def view(self, choice):
        return self.library.widget_show_progress(self.ref, self.show_ref, choice)

    def test_real_read_join_has_distinct_views_and_date_boundary(self):
        continued = self.view('continue')
        self.assertEqual(positions(continued['items']), [(1, 2)])
        self.assertEqual(continued['items'][0]['progress'], 42)
        self.assertEqual(continued['items'][0]['show_trakt_id'], 20)
        self.assertEqual(positions(self.view('next')['items']), [(1, 2)])
        upcoming = self.view('upcoming')['items']
        self.assertEqual(positions(upcoming), [(2, 1), (2, 2)])
        self.assertTrue(all(item['watched'] is None for item in upcoming))
        self.assertIn('/shows/20/progress/watched?hidden=false&specials=false', self.calls)
        continued['guard']()

    def test_invalid_view_is_rejected_before_any_authenticated_work(self):
        for value in (None, [], True, 'all', 'continue&next=1'):
            with self.subTest(value=value), self.assertRaisesRegex(ApiError, 'invalid_filter'):
                self.view(value)
        self.assertEqual(self.calls, [])

    def test_read_failures_and_incomplete_series_are_not_empty_success(self):
        self.fail_path = '/shows/20/seasons/2?extended=full'
        with self.assertRaises(ApiError):
            self.view('continue')
        self.fail_path, self.incomplete = None, True
        with self.assertRaisesRegex(ApiError, 'incomplete_series'):
            self.view('next')

    def test_account_change_during_reads_rejects_new_view(self):
        def switch(path):
            if '/seasons/1?' in path:
                self.store.install(TokenSet('synthetic-new', 'synthetic-refresh-new', 10000))
        self.hook = switch
        with self.assertRaises(AuthError):
            self.view('upcoming')

    def test_deselection_during_selection_and_after_success_rejects_rows(self):
        original = trakt_views.show_progress
        def deselect(rows, view):
            result = original(rows, view)
            AccountPreferences(self.profile).save('synthetic-a', [])
            return result
        with patch.object(trakt_views, 'show_progress', side_effect=deselect):
            with self.assertRaises(AuthError):
                self.view('next')
        self.library.select_lists(['trakt-list:1'])
        result = self.view('continue')
        AccountPreferences(self.profile).save('synthetic-a', [])
        with self.assertRaises(AuthError):
            result['guard']()

    def test_revision_change_during_filtering_rejects_joined_rows(self):
        revision = [0]
        original = trakt_views.show_progress
        def change(rows, view):
            result = original(rows, view)
            revision[0] += 1
            return result
        with patch.object(self.library, '_data_revision', side_effect=lambda: revision[0]), \
                patch.object(trakt_views, 'show_progress', side_effect=change):
            with self.assertRaisesRegex(ApiError, 'data_changed'):
                self.view('continue')

    def test_old_account_reference_and_movie_reference_cannot_read_show_progress(self):
        movie_ref = self.library.widget_list(self.ref)['items'][0]['item_ref']
        with self.assertRaises(ApiError):
            self.library.widget_show_progress(self.ref, movie_ref, 'next')
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        self.calls.clear()
        with self.assertRaises(ApiError):
            self.view('next')
        self.assertFalse(any(path.startswith('/shows/') for path in self.calls))
