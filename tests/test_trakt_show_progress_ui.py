"""Selected-show widget paths use fabricated metadata and isolated account stores."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from widget_fixtures import WidgetDirectoryFixture
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib import trakt_views
from resources.lib import trakt_widget_routes as routes
from resources.lib.trakt_widget_ui import WidgetDirectoryUI


class ShowProgressUITests(WidgetDirectoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.ui = WidgetDirectoryUI(self, self.item, lambda: self, self, dialog=self,
                                    addon_id='plugin.video.homefx.development')
        fixed = patch.object(trakt_views, '_now', return_value=datetime(2026, 11, 14, tzinfo=timezone.utc))
        fixed.start()
        self.addCleanup(fixed.stop)
        self.ref = self.library.widget_sources()['items'][0]['ref']
        self.item_ref = self.library.widget_shows(self.ref)['items'][0]['item_ref']
        self.intercept = self.series
        self.calls.clear()

    def target(self, view):
        return routes.url('trakt_show_progress', addon_id='plugin.video.homefx.development',
                          ref=self.ref, item=self.item_ref, view=view)

    def series(self, path):
        if path == '/shows/20/seasons?extended=full':
            return Response(200, body=[{'number': season, 'ids': {'trakt': 200 + season},
                                       'episode_count': 2} for season in (1, 2)])
        if path.startswith('/shows/20/seasons/'):
            season = int(path.split('/')[4].split('?')[0])
            return Response(200, body=[{'ids': {'trakt': 100 * season + number},
                'season': season, 'number': number, 'title': 'Synthetic episode',
                'first_aired': '2026-12-01T00:00:00Z' if (season, number) == (2, 2)
                               else '2026-01-01T00:00:00Z'} for number in (1, 2)])
        if path.startswith('/shows/20/progress/watched?'):
            return Response(200, body={'seasons': [
                {'number': 1, 'episodes': [{'number': 1, 'completed': True},
                                          {'number': 2, 'completed': False}]},
                {'number': 2, 'episodes': [{'number': 1, 'completed': False}]}]})
        if path.startswith('/sync/playback?'):
            return Response(200, body=[{'type': 'episode', 'progress': 35,
                'paused_at': '2026-11-13T12:00:00Z', 'show': {'ids': {'trakt': 20}},
                'episode': {'ids': {'trakt': 201}, 'season': 2, 'number': 1,
                            'title': 'Synthetic episode', 'first_aired': '2026-01-01T00:00:00Z'}}])
        return None

    def render(self, target, widget=True):
        return super().render(target, widget=widget)

    def test_picker_adds_three_distinct_terminal_choices_without_history_reads(self):
        target = routes.url('trakt_show_views', ref=self.ref, item=self.item_ref)
        self.assertEqual(self.render(target).state, 'ready')
        parsed = [routes.parse(urlsplit(url).query) for url, _, _ in self.rows]
        self.assertEqual([route for route, _ in parsed[:2]], ['trakt_seasons', 'trakt_show_unwatched'])
        self.assertEqual([params['view'] for _, params in parsed[2:]], ['continue', 'next', 'upcoming'])
        self.assertTrue(all(folder for _, _, folder in self.rows))
        self.assertTrue(all('this show, regular seasons' in item.label for _, item, _ in self.rows[2:]))
        self.assertFalse(any('/shows/' in path or '/sync/playback' in path for path in self.calls))
        self.assertEqual(self.events, [])

    def test_three_views_render_distinct_episodes_and_keep_episode_detail_scope(self):
        for view, expected in [('continue', (2, 1)), ('next', (1, 2)), ('upcoming', (2, 2))]:
            with self.subTest(view=view):
                self.assertEqual(self.render(self.target(view)).state, 'ready')
                self.assertEqual(len(self.rows), 1)
                target, item, folder = self.rows[0]
                self.assertFalse(folder)
                self.assertEqual((item.tag.values['season'], item.tag.values['episode']), expected)
                self.assertTrue(item.label.startswith('S' + str(expected[0]) + 'E' + str(expected[1])))
                route, params = routes.parse(urlsplit(target).query)
                self.assertEqual((route, params['season'], params['episode']),
                                 ('trakt_episode_details', *expected))
                self.assertTrue(target.startswith('plugin://plugin.video.homefx.development/'))
                self.assertIn('this show, regular seasons only', self.categories[-1])
                season_actions = [action for label, action in item.actions if 'in this season' in label]
                self.assertEqual(len(season_actions), 2)
                self.assertTrue(all('season=' + str(expected[0]) in action for action in season_actions))
                self.assertTrue(any(label == 'Open full list' for label, _ in item.actions))
                self.assertEqual(self.ends, [(True, False)])
                if view == 'continue':
                    self.assertIn('Unfinished progress: 35%', item.tag.values['plot'])
                if view == 'upcoming':
                    self.assertNotIn('playcount', item.tag.values)
                    self.assertIn('Watch status: unknown', item.tag.values['plot'])
                    self.assertIn('not playable availability', self.categories[-1])
        self.assertEqual(self.events, [])
        self.assertEqual(self.details, [])

    def test_progress_episode_opens_metadata_not_playback(self):
        self.assertEqual(self.render(self.target('continue')).state, 'ready')
        target = self.rows[0][0]
        self.assertEqual(self.render(target, widget=False).state, 'ready')
        self.assertEqual(len(self.details), 1)
        self.assertIn('Unfinished progress: 35%', self.details[0][1])
        self.assertIn('No playable source or playback action', self.details[0][1])

    def test_bad_view_or_extra_parameters_fail_before_any_read(self):
        base = self.target('next')
        queries = [base + '&view=next', base + '&season=1', base.replace('view=next', 'view='),
                   base.replace('view=next', 'view=all'), base.replace('&view=next', ''),
                   routes.url('trakt_show_unwatched', ref=self.ref, item=self.item_ref) + '&view=next']
        for target in queries:
            self.assertEqual(self.render(target).state, 'failed')
            self.assertEqual(self.rows, [])
        self.assertEqual(self.calls, [])
        for value in (None, True, {}, [], 'all'):
            with self.assertRaises(ValueError):
                self.target(value)

    def test_empty_success_is_distinct_from_offline_and_authorization_failures(self):
        original = self.series
        self.intercept = lambda path: Response(200, body=[]) if path.startswith('/sync/playback?') else original(path)
        self.assertEqual(self.render(self.target('continue')).state, 'empty')
        self.assertEqual(self.ends, [(True, False)])
        self.assertIn('No entries', self.categories[-1])
        self.library.clear()
        def offline(path):
            raise ApiError('transport')
        self.intercept = offline
        self.assertEqual(self.render(self.target('next')).state, 'offline')
        self.assertEqual(self.ends, [(False, False)])
        self.assertEqual(self.rows, [])
        self.store.disconnect()
        self.assertEqual(self.render(self.target('next')).state, 'authorization_needed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.events, [])

    def test_final_account_guard_prevents_staged_progress_rows(self):
        self.on_item = self.store.disconnect
        self.assertNotIn(self.render(self.target('next')).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])

    def test_cancelled_widget_does_not_read_or_open_dialogs(self):
        self.abort = True
        self.assertEqual(self.render(self.target('next')).state, 'cancelled')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.rows, [])
        self.assertEqual(self.events, [])
        self.assertEqual(self.details, [])

    def test_saved_progress_url_survives_reopen_but_not_account_replacement(self):
        target = self.target('next')
        self.assertEqual(self.render(target).state, 'ready')
        expected = [(url, item.label, folder) for url, item, folder in self.rows]
        self.library = self.reopen()
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual([(url, item.label, folder) for url, item, folder in self.rows], expected)
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])
