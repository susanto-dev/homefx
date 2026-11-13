"""Bound episode views use actual sessions/stores and fabricated read responses."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib import trakt_views

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


class EpisodeFilterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.store = TokenStore(self.profile)
        self.store.install(TokenSet('synthetic-access', 'synthetic-refresh', 10000))
        self.calls = []
        self.hook = lambda path: None
        self.episodes = [self.episode(number, aired) for number, aired in [
            (1, '2026-11-01T00:00:00Z'), (2, '2026-11-05T00:00:00Z'),
            (3, '2026-11-02T00:00:00Z'), (4, '2026-11-03T00:00:00Z'),
            (5, '2026-11-20T00:00:00Z'), (6, None),
            (7, '2026-11-07T00:00:00Z')]]
        self.progress = [{'number': number, 'completed': number == 1} for number in (1, 2, 3, 5, 6, 7)]
        self.pauses = [self.pause(3, 35), self.pause(4, 80), self.pause(1, 50)]
        self.library = Library(Session(self.store, self.no_auth, self.api, 'synthetic-client',
            'https://example.invalid/callback', clock=lambda: 1000),
            preferences=AccountPreferences(self.profile))
        self.library.select_lists(['trakt-list:1'])
        self.ref = self.library.widget_sources()['items'][0]['ref']
        self.item = self.library.widget_list(self.ref)['items'][0]['item_ref']
        fixed = patch.object(trakt_views, '_now', return_value=NOW)
        fixed.start()
        self.addCleanup(fixed.stop)
        self.calls.clear()

    @staticmethod
    def episode(number, aired, season=1):
        return {'ids': {'trakt': 100 + number}, 'season': season, 'number': number,
                'title': 'Synthetic episode ' + str(number), 'first_aired': aired}

    def pause(self, number, progress):
        return {'type': 'episode', 'show': {'ids': {'trakt': 22}},
                'episode': self.episodes[number - 1], 'progress': progress,
                'paused_at': '2026-11-12T12:00:00Z'}

    def no_auth(self, *args):
        self.fail('No authentication request expected')

    def api(self, method, path, headers, body=None):
        self.assertEqual(method, 'GET')
        self.assertIsNone(body)
        self.calls.append(path)
        self.hook(path)
        if path == '/users/settings':
            return Response(200, body={'user': {'ids': {'uuid': 'synthetic-account'}}})
        if path.startswith('/users/me/lists?'):
            return Response(200, body=[{'ids': {'trakt': 1}, 'name': 'Synthetic list'}])
        if path.startswith('/users/likes/lists?'):
            return Response(200, body=[])
        if '/items?' in path:
            return Response(200, body=[{'type': 'show', 'show': {'ids': {'trakt': 22}, 'title': 'Synthetic show'}}])
        if path == '/shows/22/seasons/1?extended=full':
            return Response(200, body=deepcopy(self.episodes))
        if path.startswith('/shows/22/progress/watched?'):
            return Response(200, body={'seasons': [{'number': 1, 'episodes': deepcopy(self.progress)}]})
        if path.startswith('/sync/playback?'):
            return Response(200, body=deepcopy(self.pauses))
        self.fail('Unexpected read')

    def test_default_and_explicit_all_keep_narrative_order_and_unknowns(self):
        default = self.library.widget_episodes(self.ref, self.item, 1)['items']
        explicit = self.library.widget_episodes(self.ref, self.item, 1, 'all')['items']
        self.assertEqual(default, explicit)
        self.assertEqual([row['episode'] for row in default], list(range(1, 8)))
        self.assertIsNone(default[3]['watched'])
        self.assertEqual(default[3]['progress'], 80)
        self.assertEqual(default[0]['progress'], 0)  # Watched evidence overrides stale pause.

    def test_filtered_view_requires_known_aired_unwatched_and_orders_unfinished_first(self):
        result = self.library.widget_episodes(self.ref, self.item, 1, 'aired_unwatched')
        self.assertEqual([row['episode'] for row in result['items']], [3, 7, 2])
        self.assertEqual(result['items'][0]['progress'], 35)
        self.assertTrue(all(row['watched'] is False and row['release_status'] == 'aired'
                            for row in result['items']))
        result['guard']()
        self.assertEqual(self.library.widget_episode_details(self.ref, self.item, 1, 3)['items'][0]['episode'], 3)

    def test_invalid_filter_fails_before_reads_or_refresh(self):
        for value in (None, True, 0, [], {}, '', 'unwatched', 'ALL', 'all&other=1'):
            with self.subTest(value=value), self.assertRaisesRegex(ApiError, 'invalid_filter'):
                self.library.widget_episodes(self.ref, self.item, 1, value)
        self.assertEqual(self.calls, [])

    def test_wrong_season_is_rejected_even_when_filter_would_exclude_it(self):
        self.episodes.append(self.episode(8, '2026-11-20T00:00:00Z', season=2))
        with self.assertRaisesRegex(ApiError, 'mismatched_season'):
            self.library.widget_episodes(self.ref, self.item, 1, 'aired_unwatched')

    def test_account_change_during_filtered_read_rejects_payload(self):
        def replace(path):
            if '/seasons/1?' in path:
                self.store.install(TokenSet('synthetic-replacement', 'synthetic-refresh-new', 10000))
        self.hook = replace
        with self.assertRaises(AuthError):
            self.library.widget_episodes(self.ref, self.item, 1, 'aired_unwatched')

    def test_account_change_during_filtering_rejects_normalized_rows(self):
        original = trakt_views.episode_filter
        def replace(rows, selection):
            result = original(rows, selection)
            self.store.install(TokenSet('synthetic-replacement', 'synthetic-refresh-new', 10000))
            return result
        with patch.object(trakt_views, 'episode_filter', side_effect=replace):
            with self.assertRaises(AuthError):
                self.library.widget_episodes(self.ref, self.item, 1, 'aired_unwatched')

    def test_filtered_guard_rejects_deselection_after_successful_read(self):
        result = self.library.widget_episodes(self.ref, self.item, 1, 'aired_unwatched')
        AccountPreferences(self.profile).save('synthetic-account', [])
        with self.assertRaises(AuthError):
            result['guard']()

    def test_empty_filtered_view_is_success_not_unknown_as_unwatched(self):
        self.progress = []
        result = self.library.widget_episodes(self.ref, self.item, 1, 'aired_unwatched')
        self.assertEqual(result['items'], [])
        self.assertEqual(result['unsupported_count'], 0)
        result['guard']()
