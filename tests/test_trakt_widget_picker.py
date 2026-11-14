"""Real directory traversal with isolated stores and fabricated account responses."""
import unittest
from urllib.parse import urlsplit

from widget_fixtures import WidgetDirectoryFixture
from resources.lib.trakt_widget_ui import WidgetDirectoryUI
from resources.lib.trakt_client import Response
from resources.lib.trakt_auth import TokenSet
from resources.lib import trakt_widget_routes as routes


class WidgetPickerTests(WidgetDirectoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.ui = WidgetDirectoryUI(self, self.item, lambda: self, self,
            dialog=self, addon_id='plugin.video.homefx.development')

    def url(self, route, **params):
        return routes.url(route, addon_id='plugin.video.homefx.development', **params)

    def render(self, target):
        return super().render(target, widget=True)

    def show_choices(self):
        self.assertEqual(self.render(self.url('trakt_widget_menu')).state, 'ready')
        self.assertEqual(self.render(self.rows[2][0]).state, 'ready')
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(self.rows[0][1].tag.values['type'], 'tvshow')
        target = self.rows[0][0]
        self.assertEqual(self.render(target).state, 'ready')
        return target

    def series(self, path):
        if path == '/shows/20/seasons?extended=full':
            return Response(200, body=[{'number': 1, 'ids': {'trakt': 201}, 'episode_count': 1}])
        if path == '/shows/20/seasons/1?extended=full':
            return Response(200, body=[{'ids': {'trakt': 21}, 'title': 'Synthetic episode',
                'season': 1, 'number': 1, 'first_aired': '2020-01-01T00:00:00Z'}])
        if path.startswith('/shows/20/progress/watched?'):
            return Response(200, body={'seasons': [{'number': 1, 'episodes': [
                {'number': 1, 'completed': False}]}]})
        if path.startswith('/sync/playback?'):
            return Response(200, body=[])
        return None

    def test_static_root_is_local_and_categories_use_existing_routes(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError('Static picker opened account runtime')
        result = self.ui.render(Forbidden(), 1, 'route=trakt_widget_menu', widget=True)
        self.assertEqual(result.state, 'ready')
        self.assertEqual([routes.parse(urlsplit(url).query)[0] for url, _, _ in self.rows],
                         ['trakt_sources', 'trakt_movie_sources', 'trakt_show_sources'])
        self.assertTrue(all(folder for _, _, folder in self.rows))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])
        self.assertTrue(all(not item.tag.values for _, item, _ in self.rows))

    def test_folder_picker_reaches_show_view_without_context_or_early_history(self):
        self.intercept = self.series
        self.show_choices()
        self.assertFalse(any('/shows/' in path or '/sync/playback' in path for path in self.calls))
        self.assertEqual(len(self.rows), 2)
        terminal = [url for url, _, folder in self.rows if folder]
        self.assertEqual([routes.parse(urlsplit(url).query)[0] for url in terminal],
                         ['trakt_seasons', 'trakt_show_unwatched'])
        for url in terminal:
            with self.subTest(url=routes.parse(urlsplit(url).query)[0]):
                self.assertEqual(self.render(url).state, 'ready')
                self.assertEqual(len(self.rows), 1)
                self.assertTrue(all(target.startswith('plugin://plugin.video.homefx.development/')
                                    for target, _, _ in self.rows))
        self.assertEqual(self.rows[0][1].tag.values['episode'], 1)
        self.assertEqual(self.rows[0][1].label, 'S1E1 — Synthetic episode')
        self.assertEqual(self.details, [])
        self.assertEqual(self.events, [])
        self.assertEqual(self.ends, [(True, False)])

    def test_terminal_folder_url_survives_reopen_with_saved_selection(self):
        self.intercept = self.series
        self.show_choices()
        terminal = self.rows[1][0]
        self.assertEqual(self.render(terminal).state, 'ready')
        first = [(url, item.label, folder) for url, item, folder in self.rows]
        self.library = self.reopen()
        self.assertEqual(self.render(terminal).state, 'ready')
        self.assertEqual(first, [(url, item.label, folder) for url, item, folder in self.rows])

    def test_deselection_and_new_account_reject_saved_picker_and_terminal_routes(self):
        self.intercept = self.series
        choices = self.show_choices()
        terminal = self.rows[1][0]
        self.library.select_lists([])
        for target in (choices, terminal):
            self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
            self.assertEqual(self.rows, [])
        self.library.select_lists(['trakt-list:1'])
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        for target in (choices, terminal):
            self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
            self.assertEqual(self.rows, [])

    def test_show_choices_cannot_open_a_movie_or_render_after_account_change(self):
        ref = self.library.widget_sources()['items'][0]['ref']
        movie = self.library.widget_list(ref)['items'][0]['item_ref']
        self.assertNotEqual(self.render(self.url('trakt_show_views', ref=ref, item=movie)).state, 'ready')
        self.assertEqual(self.rows, [])
        target = self.show_choices()
        self.on_item = lambda: self.store.disconnect()
        self.assertNotEqual(self.render(target).state, 'ready')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])

    def test_empty_show_list_and_authorization_error_never_substitute_demo_rows(self):
        ref = self.library.widget_sources()['items'][0]['ref']
        self.items = self.items[:1]
        self.assertEqual(self.render(self.url('trakt_shows', ref=ref)).state, 'empty')
        self.assertEqual(self.rows, [])
        self.assertFalse(any('/shows/' in path or '/sync/playback' in path for path in self.calls))
        self.store.disconnect()
        self.assertEqual(self.render(self.url('trakt_show_sources')).state, 'authorization_needed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.details, [])

    def test_picker_offline_and_cancelled_reads_remain_silent_failures(self):
        self.library.clear()
        self.intercept = lambda path: Response(503, body={})
        self.assertNotIn(self.render(self.url('trakt_show_sources')).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])
        self.assertEqual(self.details, [])
        self.assertEqual(self.events, [])
        self.calls.clear()
        self.abort = True
        self.assertEqual(self.render(self.url('trakt_widget_menu')).state, 'cancelled')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.rows, [])

    def test_existing_list_and_movie_picker_leaves_are_unchanged(self):
        self.assertEqual(self.render(self.url('trakt_widget_menu')).state, 'ready')
        lists, movies = self.rows[0][0], self.rows[1][0]
        self.assertEqual(self.render(lists).state, 'ready')
        full_list = self.rows[0][0]
        self.assertEqual(routes.parse(urlsplit(full_list).query)[0], 'trakt_list')
        self.assertEqual(self.render(full_list).state, 'ready')
        self.assertEqual(len(self.rows), 2)
        self.assertEqual(self.render(movies).state, 'ready')
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual([routes.parse(urlsplit(url).query)[1]['filter']
                          for url, _, _ in self.rows], list(routes.MOVIE_FILTERS))
        self.assertFalse(any('/sync/playback' in path for path in self.calls))

    def test_new_route_schema_rejects_extra_fields_before_reads(self):
        ref, item = 'a' * 64, 'b' * 64
        cases = [('trakt_widget_menu', {}), ('trakt_show_sources', {}),
                 ('trakt_shows', {'ref': ref}), ('trakt_show_views', {'ref': ref, 'item': item})]
        for route, params in cases:
            query = urlsplit(self.url(route, **params)).query
            self.assertEqual(routes.parse(query), (route, params))
            self.assertEqual(self.render(self.url(route, **params) + '&filter=all').state, 'failed')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.rows, [])
