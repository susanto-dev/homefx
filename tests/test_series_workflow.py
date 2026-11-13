"""Complete-series joins through real sessions and clients; fabricated HTTP only."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_views import continuation

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
SEASONS = '/shows/10/seasons?extended=full'
PROGRESS = '/shows/10/progress/watched?hidden=false&specials=false'
PAUSES = '/sync/playback?page=1&limit=100'


def episode(ident, season, number, aired):
    return {'ids': {'trakt': ident}, 'season': season, 'number': number,
            'title': 'Invented episode ' + str(ident), 'first_aired': aired}


class SeriesWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.now = [1000]
        self.store = TokenStore(temporary.name, clock=lambda: self.now[0])
        self.store.install(TokenSet('synthetic-access', 'synthetic-refresh', 5000))
        self.reads, self.refreshes = [], []
        self.hook = None
        self.all_watched = False
        self.empty_progress = False
        self.failure_path = None
        self.episodes = {
            0: [episode(1, 0, 1, '2026-10-01T00:00:00Z')],
            1: [episode(101, 1, 1, '2026-11-01T00:00:00Z'),
                episode(102, 1, 2, '2026-11-02T00:00:00Z'),
                episode(103, 1, 3, '2026-11-03T00:00:00Z'),
                episode(104, 1, 4, '2026-11-04T00:00:00Z')],
            2: [episode(201, 2, 1, '2026-11-12T00:00:00Z'),
                episode(202, 2, 2, '2026-11-20T00:00:00Z'),
                episode(203, 2, 3, None)],
        }
        self.session = Session(self.store, self.oauth, self.api, 'synthetic-client',
            'https://example.invalid/callback', clock=lambda: self.now[0])
        self.library = Library(self.session)

    def oauth(self, method, path, body):
        self.assertEqual((method, path), ('POST', '/oauth/token'))
        self.refreshes.append(path)
        return Response(200, body={'access_token': 'synthetic-rotated-access',
            'refresh_token': 'synthetic-rotated-refresh', 'token_type': 'bearer',
            'created_at': self.now[0], 'expires_in': 3600})

    def api(self, method, path, headers, body=None):
        self.assertEqual(method, 'GET')
        self.reads.append(path)
        if self.hook:
            self.hook(path)
        if path == self.failure_path:
            return Response(503, body={})
        if path == SEASONS:
            return Response(200, body=[{'number': number, 'ids': {'trakt': 1000 + number},
                'episode_count': len(rows), 'aired_episodes': 0,
                'title': 'Invented season'} for number, rows in self.episodes.items()])
        for number, rows in self.episodes.items():
            if path == '/shows/10/seasons/' + str(number) + '?extended=full':
                return Response(200, body=deepcopy(rows))
        if path.startswith('/shows/10/progress/watched?'):
            seasons = []
            if not self.empty_progress:
                for number, rows in self.episodes.items():
                    if number == 0 and path.endswith('specials=false'):
                        continue
                    seasons.append({'number': number, 'episodes': [
                        {'number': row['number'], 'completed': self.all_watched or row['ids']['trakt'] == 101}
                        for row in rows if row['ids']['trakt'] != 104 or self.all_watched]})
            return Response(200, body={'seasons': seasons})
        self.assertEqual(path, PAUSES)
        return Response(200, body=[{'type': 'episode', 'episode': deepcopy(self.episodes[1][1]),
            'show': {'ids': {'trakt': 10}}, 'progress': 35,
            'paused_at': '2026-11-13T10:00:00Z'},
            {'type': 'episode', 'episode': deepcopy(self.episodes[2][0]),
             'show': {'ids': {'trakt': 999}}, 'progress': 80,
             'paused_at': '2026-11-13T11:00:00Z'}])

    def test_complete_series_order_summaries_and_continuation_share_reads(self):
        rows = self.library.series_view(10, NOW)
        self.assertEqual([row['trakt_id'] for row in rows], [101, 102, 103, 104, 201, 202, 203])
        self.assertIsNone(rows[3]['watched'])
        self.assertEqual(rows[4]['progress'], 0)  # Another show's pause cannot join.
        filtered = self.library.series_view(10, NOW, 'aired_unwatched')
        self.assertEqual([row['trakt_id'] for row in filtered], [102, 201, 103])
        summaries = self.library.series_seasons(10, NOW)
        self.assertEqual([(row['season'], row['total'], row['watched'], row['unknown_watched'])
                          for row in summaries], [(1, 4, 1, 1), (2, 3, 0, 0)])
        self.assertEqual([(row['aired_unwatched'], row['upcoming'], row['unknown_date'])
                          for row in summaries], [(2, 0, 0), (1, 1, 1)])
        immediate, unwatched = continuation(rows, 103)
        self.assertEqual(immediate['trakt_id'], 104)
        self.assertIsNone(immediate['watched'])
        self.assertEqual(unwatched['trakt_id'], 201)
        self.assertEqual(Counter(self.reads), Counter({SEASONS: 1, PROGRESS: 1, PAUSES: 1,
            '/shows/10/seasons/1?extended=full': 1, '/shows/10/seasons/2?extended=full': 1}))
        self.assertEqual(self.refreshes, [])

    def test_missing_progress_is_unknown_not_a_complete_unwatched_list(self):
        self.empty_progress = True
        rows = self.library.series_view(10, NOW)
        self.assertTrue(all(row['watched'] is None for row in rows))
        self.assertEqual(self.library.series_view(10, NOW, 'aired_unwatched'), [])
        self.assertEqual([row['unknown_watched'] for row in self.library.series_seasons(10, NOW)], [4, 3])

    def test_specials_require_explicit_metadata_and_progress_scope(self):
        regular = self.library.series_view(10, NOW)
        self.assertNotIn('/shows/10/seasons/0?extended=full', self.reads)
        included = self.library.series_view(10, NOW, include_specials=True)
        self.assertEqual(included[0]['trakt_id'], 1)
        self.assertFalse(included[0]['watched'])
        self.assertEqual(len(included), len(regular) + 1)
        self.assertEqual(self.reads.count('/shows/10/progress/watched?hidden=false&specials=true'), 1)
        self.assertEqual(self.reads.count(PROGRESS), 1)
        self.assertEqual(self.reads.count(PAUSES), 1)

    def test_account_replacement_during_second_season_aborts_and_refetches(self):
        def replace(path):
            if path == '/shows/10/seasons/2?extended=full':
                self.hook = None
                self.all_watched = True
                self.store.install(TokenSet('synthetic-other-access', 'synthetic-other-refresh', 5000))
        self.hook = replace
        with self.assertRaises(AuthError):
            self.library.series_view(10, NOW)
        self.assertNotIn(PROGRESS, self.reads)
        rows = self.library.series_view(10, NOW)
        self.assertTrue(all(row['watched'] is True for row in rows))
        self.assertEqual(self.reads.count(SEASONS), 2)
        self.assertEqual(self.reads.count('/shows/10/seasons/1?extended=full'), 2)
        self.assertEqual(self.library.series_view(10, NOW, 'aired_unwatched'), [])

    def test_provider_failure_never_returns_partial_series_or_retries(self):
        self.failure_path = '/shows/10/seasons/2?extended=full'
        with self.assertRaises(ApiError):
            self.library.series_view(10, NOW)
        self.assertEqual(self.reads.count(self.failure_path), 1)
        self.assertNotIn(PROGRESS, self.reads)
        self.failure_path = None
        self.assertEqual(len(self.library.series_view(10, NOW)), 7)
        self.assertEqual(self.reads.count(SEASONS), 2)
        self.assertEqual(self.reads.count('/shows/10/seasons/1?extended=full'), 2)

    def test_refresh_before_join_uses_one_rotated_generation(self):
        self.store.install(TokenSet('synthetic-old-access', 'synthetic-old-refresh', 900))
        rows = self.library.series_view(10, NOW)
        self.assertEqual(len(rows), 7)
        self.assertEqual(self.refreshes, ['/oauth/token'])
        self.assertEqual(len(self.reads), 5)

    def test_refresh_between_seasons_aborts_instead_of_mixing_generations(self):
        self.store.install(TokenSet('synthetic-short-access', 'synthetic-short-refresh', 1100))
        def advance(path):
            if path == '/shows/10/seasons/1?extended=full':
                self.hook = None
                self.now[0] = 1050
        self.hook = advance
        with self.assertRaises(AuthError):
            self.library.series_view(10, NOW)
        self.assertEqual(self.refreshes, ['/oauth/token'])
        self.assertNotIn('/shows/10/seasons/2?extended=full', self.reads)
        self.assertEqual(len(self.library.series_view(10, NOW)), 7)
        self.assertEqual(self.reads.count(SEASONS), 2)
