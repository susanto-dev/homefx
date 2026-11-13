"""Real account/session/client boundaries with invented browsing responses only."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_calendar import upcoming
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
PAUSES = '/sync/playback?page=1&limit=100'
WATCHED = '/users/me/watched/movies'
PROGRESS = '/shows/10/progress/watched?hidden=false&specials=false'
CALENDAR = '/calendars/my/shows/2026-11-13/7?extended=full'


def movie(ident, released=None):
    return {'ids': {'trakt': ident}, 'title': 'Invented movie ' + str(ident),
            'year': 2026, 'released': released}


def episode(ident, number, aired=None):
    return {'ids': {'trakt': ident}, 'season': 1, 'number': number,
            'title': 'Invented episode ' + str(ident), 'first_aired': aired}


def pause(kind, item, percent, hour):
    result = {'type': kind, kind: item, 'progress': percent,
              'paused_at': '2026-11-13T' + hour + ':00:00Z'}
    if kind == 'episode':
        result['show'] = {'ids': {'trakt': 10}, 'title': 'Invented show', 'year': 2026}
    return result


def airing(ident, number, when, show=10):
    return {'first_aired': when,
            'show': {'ids': {'trakt': show}, 'title': 'Invented show', 'year': 2026},
            'episode': episode(ident, number, when)}


class BrowsingWorkflowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = TokenStore(directory.name, clock=lambda: 1000)
        self.store.install(TokenSet('synthetic-access', 'synthetic-refresh', 5000))
        self.reads, self.refreshes = [], []
        self.hook = None
        self.failure = None
        self.responses = {
            PAUSES: [pause('movie', movie(201), 30, '08'),
                     pause('movie', movie(201), 45, '10'),
                     pause('movie', movie(202), 20, '09'),
                     pause('episode', episode(301, 1), 55, '11'),
                     pause('episode', episode(302, 2), 15, '07')],
            WATCHED: [{'plays': 1, 'movie': movie(202)}],
            PROGRESS: {'seasons': [{'number': 1, 'episodes': [
                {'number': 1, 'completed': False}, {'number': 2, 'completed': True}]}]},
            '/movies/201?extended=full': movie(201, '2026-11-01'),
            '/movies/202?extended=full': movie(202, '2026-11-02'),
            '/shows/10/seasons/1/episodes/1?extended=full': episode(301, 1, '2026-11-10T12:00:00Z'),
            '/shows/10/seasons/1/episodes/2?extended=full': episode(302, 2, '2026-11-11T12:00:00Z'),
            CALENDAR: [airing(401, 3, '2026-11-13T13:00:00Z'),
                       airing(402, 4, '2026-11-15T00:00:00Z', 20),
                       airing(403, 5, '2026-11-13T11:00:00Z')],
        }
        self.session = Session(self.store, self.oauth, self.api, 'synthetic-client',
            'https://example.invalid/callback', clock=lambda: 1000)
        self.library = Library(self.session)

    def oauth(self, method, path, body):
        self.refreshes.append(path)
        self.fail('No valid workflow in this fixture should refresh credentials')

    def api(self, method, path, headers, body=None):
        self.assertEqual(method, 'GET')
        self.assertIsNone(body)
        self.assertIn(path, self.responses)
        self.reads.append(path)
        if self.hook:
            self.hook(path)
        if path == self.failure:
            return Response(503, body={})
        return Response(200, body=deepcopy(self.responses[path]))

    def test_missing_pause_dates_are_enriched_and_watched_history_wins(self):
        self.assertEqual(self.library.continue_view(NOW), [])
        rows = self.library.enriched_continue_view(NOW)
        self.assertEqual([row['trakt_id'] for row in rows], [301, 201])
        self.assertEqual([row['progress'] for row in rows], [55, 45])
        self.assertTrue(all(row['watched'] is False and row['playable'] is False for row in rows))
        self.assertEqual(Counter(self.reads), Counter({path: 1 for path in self.responses if path != CALENDAR}))
        self.assertEqual(self.library.enriched_continue_view(NOW), rows)
        self.assertTrue(all(count == 1 for count in Counter(self.reads).values()))

    def test_empty_and_oversized_pause_sets_never_start_enrichment(self):
        self.responses[PAUSES] = []
        self.assertEqual(self.library.enriched_continue_view(NOW), [])
        self.assertEqual(self.reads, [PAUSES])
        self.library.clear()
        self.responses[PAUSES] = [pause('movie', movie(ident), 10, '10') for ident in range(1, 52)]
        with self.assertRaises(ApiError):
            self.library.enriched_continue_view(NOW)
        self.assertEqual(self.reads, [PAUSES, PAUSES])

    def test_metadata_identity_mismatch_rejects_whole_join_without_retry(self):
        path = '/movies/201?extended=full'
        self.responses[path] = movie(999, '2026-11-01')
        with self.assertRaises(ApiError):
            self.library.enriched_continue_view(NOW)
        self.assertEqual(self.reads.count(path), 1)
        self.assertNotIn('/movies/202?extended=full', self.reads)

    def test_account_replacement_during_details_invalidates_cached_components(self):
        path = '/shows/10/seasons/1/episodes/1?extended=full'
        def replace(current):
            if current == path:
                self.hook = None
                self.store.install(TokenSet('synthetic-other', 'synthetic-other-refresh', 5000))
        self.hook = replace
        with self.assertRaises(AuthError):
            self.library.enriched_continue_view(NOW)
        self.assertNotIn('/shows/10/seasons/1/episodes/2?extended=full', self.reads)
        rows = self.library.enriched_continue_view(NOW)
        self.assertEqual([row['trakt_id'] for row in rows], [301, 201])
        self.assertEqual(self.reads.count(PAUSES), 2)
        self.assertEqual(self.reads.count(WATCHED), 2)
        self.assertEqual(self.reads.count(PROGRESS), 2)

    def test_failed_metadata_read_returns_no_partial_rows_and_no_retry(self):
        self.failure = '/shows/10/seasons/1/episodes/1?extended=full'
        with self.assertRaises(ApiError):
            self.library.enriched_continue_view(NOW)
        self.assertEqual(self.reads.count(self.failure), 1)
        self.failure = None
        self.assertEqual(len(self.library.enriched_continue_view(NOW)), 2)
        self.assertEqual(self.reads.count(PAUSES), 2)

    def test_calendar_filter_is_personal_intersection_with_unknown_watched_state(self):
        rows = upcoming(self.session, '2026-11-13', 7, now=NOW)
        self.assertEqual([row['trakt_id'] for row in rows], [401, 402])
        self.assertTrue(all(row['watched'] is None and row['playable'] is False for row in rows))
        selected = upcoming(self.session, '2026-11-13', 7, now=NOW, allowed_show_ids={10, 30})
        self.assertEqual([row['trakt_id'] for row in selected], [401])
        self.assertEqual(self.reads, [CALENDAR, CALENDAR])
        self.assertEqual(self.refreshes, [])

    def test_calendar_revision_change_rejects_result_and_bad_window_precedes_refresh(self):
        def revise(path):
            self.session.data_revision += 1
            self.hook = None
        self.hook = revise
        with self.assertRaises(ApiError):
            upcoming(self.session, '2026-11-13', 7, now=NOW)
        self.assertEqual(len(upcoming(self.session, '2026-11-13', 7, now=NOW)), 2)
        self.store.install(TokenSet('synthetic-expired', 'synthetic-old-refresh', 900))
        for start, days in [('2026-02-30', 7), ('2026-11-13', 32), ('2026-11-13', True)]:
            with self.subTest(start=start, days=days), self.assertRaises(ApiError):
                upcoming(self.session, start, days, now=NOW)
        self.assertEqual(self.refreshes, [])
        self.assertEqual(self.reads, [CALENDAR, CALENDAR])
