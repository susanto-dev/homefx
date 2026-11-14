"""Bound episode filters and status rendering with fabricated read-only responses."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_widget_ui import WidgetDirectoryUI, _progress_text
from resources.lib import trakt_widget_routes as routes, trakt_views
from widget_fixtures import Item


class EpisodeProgressUITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.calls, self.rows, self.ends, self.dialogs, self.events = [], [], [], [], []
        self.episodes = [{'ids': {'trakt': 100 + n}, 'season': 1, 'number': n,
            'title': 'Synthetic episode ' + str(n), 'first_aired': aired} for n, aired in [
                (1, '2026-11-01T00:00:00Z'), (2, '2026-11-05T00:00:00Z'),
                (3, '2026-11-02T00:00:00Z'), (4, '2026-11-03T00:00:00Z'),
                (5, '2026-11-20T00:00:00Z'), (6, None), (7, '2026-11-07T00:00:00Z')]]
        self.progress = [{'number': n, 'completed': n == 1} for n in (1, 2, 3, 5, 6, 7)]
        self.pauses = [{'type': 'episode', 'show': {'ids': {'trakt': 22}},
            'episode': self.episodes[n - 1], 'progress': percent,
            'paused_at': '2026-11-12T12:00:00Z'} for n, percent in [(1, 50), (3, 35), (4, 80)]]
        store = TokenStore(temporary.name)
        store.install(TokenSet('synthetic-access', 'synthetic-refresh', 10000))
        session = Session(store, lambda *a: self.fail('No authentication expected'), self.api,
                          'synthetic-client', 'https://example.invalid/callback', clock=lambda: 1000)
        self.library = Library(session, preferences=AccountPreferences(temporary.name))
        self.library.select_lists(['trakt-list:1'])
        self.ref = self.library.widget_sources()['items'][0]['ref']
        self.item_ref = self.library.widget_list(self.ref)['items'][0]['item_ref']
        fixed = patch.object(trakt_views, '_now', return_value=datetime(2026, 11, 13, tzinfo=timezone.utc))
        fixed.start()
        self.addCleanup(fixed.stop)
        self.ui = WidgetDirectoryUI(self, Item, lambda: self, self, dialog=self)
        self.calls.clear()

    def api(self, method, path, headers, body=None):
        self.assertEqual(method, 'GET')
        self.assertIsNone(body)
        self.calls.append(path)
        if path == '/users/settings':
            data = {'user': {'ids': {'uuid': 'synthetic-account'}}}
        elif path.startswith('/users/me/lists?'):
            data = [{'ids': {'trakt': 1}, 'name': 'Synthetic list'}]
        elif path.startswith('/users/likes/lists?'):
            data = []
        elif '/items?' in path:
            data = [{'type': 'show', 'show': {'ids': {'trakt': 22}, 'title': 'Synthetic show'}}]
        elif path == '/shows/22/seasons?extended=full':
            data = [{'number': 1, 'ids': {'trakt': 221}, 'episode_count': 7}]
        elif path == '/shows/22/seasons/1?extended=full':
            data = self.episodes
        elif path.startswith('/shows/22/progress/watched?'):
            data = {'seasons': [{'number': 1, 'episodes': self.progress}]}
        elif path.startswith('/sync/playback?'):
            data = self.pauses
        else:
            self.fail('Unexpected read')
        return Response(200, body=deepcopy(data))

    def abortRequested(self): return False
    def iscanceled(self): return False
    def create(self, title, text): self.events.append('loading')
    def update(self, percent): return None
    def close(self): self.events.append('closed')
    def setPluginCategory(self, handle, text): self.category = text
    def setContent(self, handle, content): self.assertEqual(content, 'videos')
    def addDirectoryItems(self, handle, items, totalItems):
        self.assertEqual(totalItems, len(items))
        self.rows.extend(items)
        return True
    def endOfDirectory(self, handle, succeeded, cacheToDisc): self.ends.append((succeeded, cacheToDisc))
    def textviewer(self, title, text): self.dialogs.append((title, text))

    def target(self, **params):
        return routes.url('trakt_episodes', ref=self.ref, item=self.item_ref, season=1, **params)

    def render(self, target, widget=False):
        self.rows, self.ends = [], []
        return self.ui.render(self.library, 1, urlsplit(target).query, widget=widget)

    def show_target(self):
        return routes.url('trakt_show_unwatched', ref=self.ref, item=self.item_ref)

    def test_show_view_spans_regular_seasons_and_keeps_episode_detail_scope(self):
        original = self.api
        def api(method, path, headers, body=None):
            if path == '/shows/22/seasons?extended=full':
                self.calls.append(path)
                return Response(200, body=[{'number': n, 'ids': {'trakt': 220 + n},
                    'episode_count': count} for n, count in [(0, 1), (1, 7), (2, 1)]])
            if path == '/shows/22/seasons/2?extended=full':
                self.calls.append(path)
                return Response(200, body=[{'ids': {'trakt': 201}, 'title': 'Synthetic later season',
                    'season': 2, 'number': 1, 'first_aired': '2026-11-09T00:00:00Z'}])
            response = original(method, path, headers, body)
            if path.startswith('/shows/22/progress/watched?'):
                response.body['seasons'].append({'number': 2, 'episodes': [{'number': 1, 'completed': False}]})
            return response
        self.library._session._api = api
        # Install the alternate fixture at the session transport boundary.
        self.library.clear()
        self.assertEqual(self.render(self.show_target()).state, 'ready')
        self.assertEqual([(item.tag.values['season'], item.tag.values['episode'])
                         for _, item, _ in self.rows], [(1, 3), (2, 1), (1, 7), (1, 2)])
        self.assertTrue(self.rows[1][1].label.startswith('S2E1'))
        route, params = routes.parse(urlsplit(self.rows[1][0]).query)
        self.assertEqual((route, params['season'], params['episode']), ('trakt_episode_details', 2, 1))
        self.assertFalse(any('/seasons/0?' in path for path in self.calls))
        self.assertEqual(self.ends, [(True, False)])

    def test_show_view_empty_unknown_and_failed_snapshots_are_not_invented_unwatched(self):
        self.progress = [{'number': n, 'completed': True} for n in range(1, 8)]
        self.assertEqual(self.render(self.show_target(), widget=True).state, 'empty')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.dialogs, [])
        self.library.clear()
        self.progress = []
        self.assertEqual(self.render(self.show_target(), widget=True).state, 'empty')
        self.library.clear()
        self.episodes.pop()
        self.assertEqual(self.render(self.show_target(), widget=True).state, 'failed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])

    def test_show_route_rejects_deselected_refs_and_extra_choices(self):
        query = self.show_target()
        self.assertEqual(self.render(query + '&season=1').state, 'failed')
        self.assertEqual(self.calls, [])
        self.library.select_lists([])
        self.assertNotEqual(self.render(query).state, 'ready')
        self.assertEqual(self.rows, [])

    def test_legacy_url_is_unchanged_and_filter_is_optional(self):
        expected = ('plugin://plugin.video.homefx/?route=trakt_episodes&ref=' + self.ref
                    + '&item=' + self.item_ref + '&season=1')
        self.assertEqual(self.target(), expected)
        self.assertNotIn('filter', routes.parse(urlsplit(expected).query)[1])
        self.assertEqual(self.render(expected).state, 'ready')
        self.assertEqual([item.tag.values['episode'] for _, item, _ in self.rows], list(range(1, 8)))
        for selection in ('all', 'aired_unwatched'):
            self.assertEqual(routes.parse(urlsplit(self.target(filter=selection)).query)[1]['filter'], selection)

    def test_filter_schema_rejects_other_routes_duplicates_and_invalid_values_before_reads(self):
        queries = [self.target() + '&filter=' + value for value in ('', 'ALL', 'unwatched', '1')]
        queries += [self.target(filter='all') + '&filter=all',
                    routes.url('trakt_list', ref=self.ref) + '&filter=aired_unwatched',
                    routes.url('trakt_sources') + '&filter=all',
                    routes.url('trakt_seasons', ref=self.ref, item=self.item_ref) + '&filter=all',
                    routes.url('trakt_episode_details', ref=self.ref, item=self.item_ref, season=1, episode=3) + '&filter=all']
        for query in queries:
            self.assertEqual(self.render(query).state, 'failed')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.rows, [])
        for value in (None, True, [], {}, 'unknown'):
            with self.assertRaises(ValueError):
                self.target(filter=value)

    def test_season_counts_are_independent_metadata_and_actions_keep_scope(self):
        self.assertEqual(self.render(routes.url('trakt_seasons', ref=self.ref, item=self.item_ref)).state, 'ready')
        target, item, folder = self.rows[0]
        self.assertTrue(folder)
        self.assertEqual(target, self.target())
        self.assertEqual(item.tag.values['type'], 'season')
        self.assertEqual(item.tag.values['title'], 'Season 1')
        self.assertEqual(item.tag.values['season'], 1)
        plot = item.tag.values['plot']
        for text in ('Total episodes: 7', 'Watched: 1', 'Aired unwatched: 3',
                     'Upcoming dates: 1', 'Unknown watched status: 1', 'Unknown dates: 1',
                     'Counts overlap', 'do not establish playable availability'):
            self.assertIn(text, plot)
        self.assert_actions(item)

    def assert_actions(self, item):
        actions = dict(item.actions)
        for label, selection in [('All episodes in this season', 'all'),
                                 ('Aired unwatched episodes in this season', 'aired_unwatched')]:
            self.assertEqual(actions[label], 'Container.Update(' + self.target(filter=selection) + ')')
        self.assertEqual(actions['Open full list'], 'Container.Update(' + routes.url('trakt_list', ref=self.ref) + ')')

    def test_filtered_view_has_unfinished_first_and_details_do_not_carry_filter(self):
        self.assertEqual(self.render(self.target(filter='aired_unwatched'), widget=True).state, 'ready')
        self.assertEqual([item.tag.values['episode'] for _, item, _ in self.rows], [3, 7, 2])
        self.assertEqual(self.events, [])
        target, item, folder = self.rows[0]
        self.assertFalse(folder)
        self.assertIn('Unfinished progress: 35%', item.tag.values['plot'])
        self.assert_actions(item)
        route, params = routes.parse(urlsplit(target).query)
        self.assertEqual(route, 'trakt_episode_details')
        self.assertNotIn('filter', params)
        self.assertEqual(self.render(target).state, 'ready')
        self.assertIn('Unfinished progress: 35%', self.dialogs[-1][1])
        self.assertFalse(any('/oauth/' in call or '/sync/history' in call for call in self.calls))

    def test_all_view_keeps_unknown_watch_status_and_suppresses_watched_pause(self):
        self.assertEqual(self.render(self.target()).state, 'ready')
        first, unknown = self.rows[0][1], self.rows[3][1]
        self.assertNotIn('Unfinished progress', first.tag.values['plot'])
        self.assertIn('Watch status: unknown', unknown.tag.values['plot'])
        self.assertIn('Unfinished progress: 80%', unknown.tag.values['plot'])
        self.assertNotIn('playcount', unknown.tag.values)

    def test_empty_filtered_view_has_no_controls_in_folder_or_widget(self):
        self.progress = [{'number': n, 'completed': True} for n in range(1, 8)]
        self.library.clear()
        for widget in (False, True):
            self.assertEqual(self.render(self.target(filter='aired_unwatched'), widget=widget).state, 'empty')
            self.assertEqual(self.rows, [])
            self.assertEqual(self.ends, [(True, False)])

    def test_percentage_bounds_never_invent_resume_or_round_to_complete(self):
        for value in (0.00001, 35.5, 99.999999):
            text = _progress_text({'kind': 'episode', 'watched': False, 'progress': value})
            self.assertIn(str(value) + '%', text)
            self.assertNotIn('100%', text)
        for value in (True, None, -1, 100, float('nan'), float('inf'), '35'):
            with self.assertRaises(ValueError):
                _progress_text({'kind': 'episode', 'watched': False, 'progress': value})
        self.assertEqual(_progress_text({'kind': 'episode', 'watched': True, 'progress': 35}), '')
        self.assertEqual(_progress_text({'kind': 'episode', 'watched': False, 'progress': 0}), '')
