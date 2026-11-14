"""Account-wide widget UI uses fabricated responses and private temporary stores."""
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


class ContinueWidgetUITests(WidgetDirectoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.library.select_lists([])
        self.intercept = self.responses
        self.library = self.reopen()
        self.ui = WidgetDirectoryUI(self, self.item, lambda: self, self, dialog=self,
                                    addon_id='plugin.video.homefx.development')
        fixed = patch.object(trakt_views, '_now', return_value=datetime(2026, 11, 14, tzinfo=timezone.utc))
        fixed.start()
        self.addCleanup(fixed.stop)
        self.calls.clear()

    def responses(self, path):
        if path.startswith(('/users/me/lists?', '/users/likes/lists?')):
            raise AssertionError('Continue does not require saved list reads')
        if path.startswith('/sync/playback?'):
            return Response(200, body=[
                {'type': 'movie', 'progress': 40, 'paused_at': '2026-11-12T12:00:00Z',
                 'movie': {'ids': {'trakt': 10}}},
                {'type': 'episode', 'progress': 35, 'paused_at': '2026-11-13T12:00:00Z',
                 'show': {'ids': {'trakt': 20}},
                 'episode': {'ids': {'trakt': 201}, 'season': 2, 'number': 1}}])
        if path == '/users/me/watched/movies':
            return Response(200, body=[])
        if path == '/movies/10?extended=full':
            return Response(200, body={'ids': {'trakt': 10}, 'title': 'Synthetic movie',
                                       'released': '2020-01-01'})
        if path.startswith('/shows/20/progress/watched?'):
            return Response(200, body={'seasons': []})
        if path == '/shows/20/seasons/2/episodes/1?extended=full':
            return Response(200, body={'ids': {'trakt': 201}, 'season': 2, 'number': 1,
                'title': 'Synthetic episode', 'first_aired': '2020-01-01T00:00:00Z'})
        return None

    def url(self, route, **params):
        return routes.url(route, addon_id='plugin.video.homefx.development', **params)

    def render(self, target, widget=True):
        return super().render(target, widget=widget)

    def feed(self):
        self.assertEqual(self.render(self.url('trakt_continue_sources')).state, 'ready')
        self.assertEqual(len(self.rows), 1)
        self.assertTrue(self.rows[0][2])
        return self.rows[0][0]

    def test_static_picker_and_account_source_do_not_read_pause_or_history(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError('Static menu opened runtime')
        result = self.ui.render(Forbidden(), 1, '?route=trakt_widget_menu', widget=True)
        self.assertEqual(result.state, 'ready')
        self.assertEqual([routes.parse(urlsplit(url).query)[0] for url, _, _ in self.rows],
                         ['trakt_sources', 'trakt_movie_sources', 'trakt_show_sources', 'trakt_continue_sources'])
        self.assertEqual(self.calls, [])
        target = self.feed()
        self.assertEqual(routes.parse(urlsplit(target).query)[0], 'trakt_continue')
        self.assertFalse(any('/sync/' in path or '/watched/' in path for path in self.calls))
        self.assertEqual(self.events, [])

    def test_mixed_feed_keeps_episode_identity_unknown_watch_and_feed_only_actions(self):
        target = self.feed()
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual([item.tag.values['type'] for _, item, _ in self.rows], ['episode', 'movie'])
        episode = self.rows[0][1]
        self.assertEqual(episode.tag.values['ids'], ({'trakt': '201', 'tvshow.trakt': '20'}, 'trakt'))
        self.assertEqual((episode.tag.values['season'], episode.tag.values['episode']), (2, 1))
        self.assertNotIn('show_title', episode.tag.values)
        self.assertNotIn('playcount', episode.tag.values)
        self.assertIn('Watch status: unknown', episode.tag.values['plot'])
        self.assertIn('Unfinished progress: 35%', episode.tag.values['plot'])
        self.assertEqual(self.rows[1][1].tag.values['playcount'], 0)
        for url, item, folder in self.rows:
            self.assertFalse(folder)
            self.assertEqual(routes.parse(urlsplit(url).query)[0], 'trakt_continue_details')
            self.assertTrue(url.startswith('plugin://plugin.video.homefx.development/'))
            self.assertEqual(item.actions, [('Open Continue watching', 'Container.Update(' + target + ')')])
            self.assertFalse(any('trakt_list' in command or 'trakt_episodes' in command for _, command in item.actions))
        self.assertIn('not limited to selected lists', self.categories[-1])
        self.assertEqual(self.ends, [(True, False)])
        self.assertEqual(self.events, [])

    def test_detail_opens_metadata_and_never_becomes_a_widget_action(self):
        self.assertEqual(self.render(self.feed()).state, 'ready')
        target = self.rows[0][0]
        self.assertEqual(self.render(target, widget=False).state, 'ready')
        self.assertEqual(len(self.details), 1)
        self.assertTrue(self.details[0][0].startswith('S2E1'))
        self.assertIn('Watch status: unknown', self.details[0][1])
        self.assertIn('No playable source or playback action', self.details[0][1])
        self.assertEqual(self.render(target, widget=True).state, 'failed')
        self.assertEqual(len(self.details), 1)

    def test_route_schema_rejects_public_ids_and_selected_list_parameters_before_reads(self):
        ref, item = 'a' * 64, 'b' * 64
        for query in ['?route=trakt_continue', '?route=trakt_continue&ref=10',
                      '?route=trakt_continue&ref=' + ref + '&ref=' + ref,
                      '?route=trakt_continue&ref=' + ref + '&filter=all',
                      '?route=trakt_continue_sources&ref=' + ref,
                      '?route=trakt_continue_details&ref=' + ref + '&item=' + item + '&season=2']:
            self.assertEqual(self.render(query).state, 'failed')
        self.assertEqual(self.calls, [])
        for route, params in [('trakt_continue', {'ref': ref}),
                              ('trakt_continue_details', {'ref': ref, 'item': item})]:
            self.assertEqual(routes.parse(urlsplit(self.url(route, **params)).query), (route, params))

    def test_empty_offline_and_authorization_states_are_distinct(self):
        target = self.feed()
        original = self.responses
        self.intercept = lambda path: Response(200, body=[]) if path.startswith('/sync/playback?') else original(path)
        self.assertEqual(self.render(target).state, 'empty')
        self.assertEqual(self.ends, [(True, False)])
        self.library.clear()
        def offline(path):
            raise ApiError('transport')
        self.intercept = offline
        self.assertEqual(self.render(target).state, 'offline')
        self.assertEqual(self.ends, [(False, False)])
        self.assertEqual(self.rows, [])
        self.store.disconnect()
        self.assertEqual(self.render(target).state, 'authorization_needed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.details, [])

    def test_final_guard_and_cancellation_prevent_submission(self):
        target = self.feed()
        self.on_item = self.store.disconnect
        self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])
        self.calls.clear()
        self.abort = True
        self.assertEqual(self.render(target).state, 'cancelled')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])

    def test_feed_reopens_but_old_account_url_does_not_follow_account_switch(self):
        target = self.feed()
        self.assertEqual(self.render(target).state, 'ready')
        expected = [(url, item.label, folder) for url, item, folder in self.rows]
        self.library = self.reopen()
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual([(url, item.label, folder) for url, item, folder in self.rows], expected)
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])

    def test_removed_pause_detail_is_unavailable_not_stale_metadata(self):
        self.assertEqual(self.render(self.feed()).state, 'ready')
        target = self.rows[0][0]
        original = self.responses
        self.intercept = lambda path: Response(200, body=[]) if path.startswith('/sync/playback?') else original(path)
        self.library = self.reopen()
        self.assertEqual(self.render(target, widget=False).state, 'unavailable')
        self.assertEqual(len(self.details), 1)
        self.assertNotIn('Synthetic episode', self.details[0][1])
