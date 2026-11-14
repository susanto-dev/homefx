"""Inactive directory renderer against real private stores and fabricated GET reads."""
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_widget_ui import WidgetDirectoryUI
from resources.lib import trakt_widget_routes as routes
from resources.lib import routes as preview_routes


class Tag:
    def __init__(self):
        self.values = {}

    def setTitle(self, value): self.values['title'] = value
    def setMediaType(self, value): self.values['type'] = value
    def setYear(self, value): self.values['year'] = value
    def setPlaycount(self, value): self.values['playcount'] = value
    def setPlot(self, value): self.values['plot'] = value
    def setRating(self, rating, votes, source, default):
        self.values['rating'] = (rating, votes, source, default)

    def setUniqueIDs(self, values, default): self.values['ids'] = (values, default)
    def setTvShowTitle(self, value): self.values['show_title'] = value

    def setSeason(self, value): self.values['season'] = value
    def setEpisode(self, value): self.values['episode'] = value


class Item:
    def __init__(self, label):
        self.label, self.tag, self.actions, self.art = label, Tag(), [], {}

    def setArt(self, art): self.art = art
    def getVideoInfoTag(self): return self.tag
    def addContextMenuItems(self, actions): self.actions.extend(actions)


class WidgetRouteTests(unittest.TestCase):
    def test_exact_schema_roundtrip_and_public_preview_remains_inactive(self):
        cases = [('trakt_sources', {}), ('trakt_list', {'ref': 'a' * 64}),
                 ('trakt_seasons', {'ref': 'a' * 64, 'item': 'b' * 64}),
                 ('trakt_details', {'ref': 'a' * 64, 'item': 'b' * 64}),
                 ('trakt_episode_details', {'ref': 'a' * 64, 'item': 'b' * 64, 'season': 1, 'episode': 2}),
                 ('trakt_episodes', {'ref': 'a' * 64, 'item': 'b' * 64, 'season': 2})]
        for route, params in cases:
            query = urlsplit(routes.url(route, **params)).query
            self.assertEqual(routes.parse(query), (route, params))
            with self.assertRaises(ValueError):
                preview_routes.parse(query)
        self.assertEqual(preview_routes.parse('?route=continue&id='), ('continue', {}))

    def test_movie_filters_are_explicit_and_bad_values_rejected(self):
        for mode in routes.MOVIE_FILTERS:
            for route, params in [('trakt_list', {'ref': 'a' * 64}),
                                  ('trakt_details', {'ref': 'a' * 64, 'item': 'b' * 64})]:
                params = dict(params, filter=mode)
                self.assertEqual(routes.parse(urlsplit(routes.url(route, **params)).query), (route, params))
        for query in ('route=trakt_list&ref=' + 'a' * 64 + '&filter=aired_unwatched',
                      'route=trakt_movie_views&ref=' + 'a' * 64 + '&filter=all',
                      'route=trakt_movie_sources&ref=' + 'a' * 64):
            with self.assertRaises(ValueError): routes.parse(query)
        self.assertEqual(routes.parse('route=trakt_sources'), ('trakt_sources', {}))

    def test_malformed_or_extra_route_fields_are_rejected(self):
        ref, item = 'a' * 64, 'b' * 64
        bad = ['', '?route=home', '?route=trakt_list', '?route=trakt_sources&ref=' + ref,
               '?route=trakt_sources&route=trakt_sources', '?route=trakt_list&ref=' + 'A' * 64,
               '?route=trakt_list&ref=' + ref + '&token=secret', '?route=trakt_sources&',
               '?route=trakt_list&ref=' + ref + '&ref=' + ref]
        for season in ['-1', '01', '10001', 'true', '1.0', '']:
            bad.append('?route=trakt_episodes&ref=' + ref + '&item=' + item + '&season=' + season)
        for query in bad:
            with self.subTest(query=query), self.assertRaises(ValueError):
                routes.parse(query)
        with self.assertRaises(ValueError):
            routes.url('trakt_episodes', ref=ref, item=item, season=True)


class WidgetDirectoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.store = TokenStore(self.profile)
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        self.preferences = AccountPreferences(self.profile)
        self.calls, self.rows, self.ends, self.events, self.categories = [], [], [], [], []
        self.abort, self.progress_cancel, self.submission = False, False, True
        self.details = []
        self.on_item = lambda: None
        self.on_close = lambda: None
        self.on_add = lambda: None
        self.on_abort_probe = lambda: None
        self.intercept = lambda path: None
        self.items = [{'type': 'movie', 'movie': {'ids': {'trakt': 10}, 'title': '[B]Synthetic movie[/B]'}},
                      {'type': 'show', 'show': {'ids': {'trakt': 20}, 'title': 'Synthetic show'}}]
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        self.calls.clear()
        self.ui = WidgetDirectoryUI(self, self.item, lambda: self, self, dialog=self, art_root="/synthetic/art/")

    def reopen(self):
        def api(method, path, headers, body=None):
            self.assertEqual(method, 'GET')
            self.assertIsNone(body)
            self.calls.append(path)
            response = self.intercept(path)
            if response is not None:
                return response
            if path == '/users/settings':
                account = 'b' if headers['Authorization'].endswith('synthetic-b') else 'a'
                return Response(200, body={'user': {'ids': {'uuid': 'synthetic-' + account}}})
            if path.startswith('/users/me/lists?'):
                return Response(200, body=[{'ids': {'trakt': 1}, 'name': '[B]Synthetic list[/B]'}])
            if path.startswith('/users/likes/lists?'):
                return Response(200, body=[])
            return Response(200, body=self.items)

        def no_auth(*args):
            raise AssertionError('No authentication expected')
        return Library(Session(TokenStore(self.profile), no_auth, api, 'synthetic-client',
                       'https://example.invalid/callback', clock=lambda: 1000),
                       preferences=AccountPreferences(self.profile))

    def item(self, label):
        self.on_item()
        return Item(label)

    def abortRequested(self):
        self.on_abort_probe()
        return self.abort
    def iscanceled(self): return self.progress_cancel
    def create(self, title, message): self.events.append(('loading', message))
    def update(self, percent): self.events.append(('update', percent))
    def close(self):
        self.events.append(('close',))
        self.on_close()

    def textviewer(self, title, text): self.details.append((title, text))

    def setPluginCategory(self, handle, category): self.categories.append(category)
    def setContent(self, handle, content): self.assertEqual(content, 'videos')
    def addDirectoryItems(self, handle, items, totalItems):
        self.assertEqual(totalItems, len(items))
        self.rows.extend(items)
        self.on_add()
        return self.submission

    def endOfDirectory(self, handle, succeeded, cacheToDisc):
        self.ends.append((succeeded, cacheToDisc))

    def render(self, target, widget=False):
        self.rows, self.ends = [], []
        return self.ui.render(self.library, 1, urlsplit(target).query, widget=widget)

    def source(self):
        return routes.url('trakt_list', ref=self.library.widget_sources()['items'][0]['ref'])

    def test_construction_and_sources_then_list_and_movie_details(self):
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])
        self.assertEqual(self.render(routes.url('trakt_sources')).state, 'ready')
        self.assertEqual(self.rows[0][1].label, '(B)Synthetic list(/B)')
        target = self.rows[0][0]
        self.assertNotIn('synthetic', target)
        self.assertNotIn('trakt-list', target)
        self.assertEqual(self.render(target, widget=True).state, 'ready')
        self.assertEqual(len(self.rows), 2)
        self.assertEqual([folder for _, _, folder in self.rows], [False, True])
        movie_target, movie, _ = self.rows[0]
        self.assertNotIn('playcount', movie.tag.values)
        self.assertEqual(movie.actions, [('Open full list', 'Container.Update(' + target + ')')])
        self.assertNotIn('[B]', movie.label)
        self.assertEqual(movie.art['poster'], '/synthetic/art/poster.png')
        self.assertEqual(movie.art['icon'], '/synthetic/art/icon.png')
        self.assertEqual(self.render(movie_target).state, 'ready')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [])
        self.assertEqual(self.details[0][0], '(B)Synthetic movie(/B)')
        self.assertIn('No playable source', self.details[0][1])
        self.assertNotIn('Synthetic', repr(self.ui))

    def test_list_descriptions_and_named_ratings_use_existing_reads_only(self):
        target = self.source()
        self.library = self.reopen()
        self.calls.clear()
        self.render(target, widget=True)
        original_calls = list(self.calls)
        self.calls.clear()
        self.library = self.reopen()
        for row in self.items:
            row[row['type']].update(overview='An original [B]synopsis[/B].\nSecond line.',
                                   rating=7.25, votes=123)
        self.assertEqual(self.render(target, widget=True).state, 'ready')
        self.assertEqual(self.calls, original_calls)
        for _, item, _ in self.rows:
            self.assertEqual(item.tag.values['rating'], (7.25, 123, 'trakt', True))
            self.assertIn('Trakt rating: 7.2/10 (123 votes).', item.tag.values['plot'])
            self.assertIn('(B)synopsis(/B). Second line.', item.tag.values['plot'])
            self.assertIn('Watch status: unknown', item.tag.values['plot'])
        movie_target = self.rows[0][0]
        self.assertEqual(self.render(movie_target).state, 'ready')
        self.assertIn('Trakt rating:', self.details[-1][1])
        self.assertIn('synopsis', self.details[-1][1])
        self.assertNotIn('[B]', self.details[-1][1])
        self.assertIn('No playable source', self.details[-1][1])

    def test_optional_bad_metadata_does_not_break_list_or_invent_rating(self):
        self.items[0]['movie'].update(overview='x' * 4097, rating=8, votes=0)
        self.items[1]['show'].update(overview={'bad': 'value'}, rating=True, votes=100)
        self.assertEqual(self.render(self.source(), widget=True).state, 'ready')
        for _, item, _ in self.rows:
            self.assertNotIn('rating', item.tag.values)
            self.assertNotIn('Trakt rating:', item.tag.values['plot'])
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertNotIn('Trakt rating:', self.details[-1][1])

    def movie_fixture(self):
        self.items = [{'type': 'movie', 'movie': {'ids': {'trakt': ident},
            'title': 'Movie ' + str(ident), 'released': released, 'overview': 'Synthetic plot',
            'rating': 8, 'votes': 10}} for ident, released in
            [(10, '2020-01-01'), (11, '2099-01-01'), (12, '2020-01-01'), (13, None)]]
        self.items.append({'type': 'show', 'show': {'ids': {'trakt': 20}, 'title': 'Show'}})
        self.watched = [12]
        def replies(path):
            if path == '/users/me/watched/movies':
                return Response(200, body=[{'plays': 1, 'movie': {'ids': {'trakt': ident}}} for ident in self.watched])
            if path.startswith('/sync/playback?'):
                return Response(200, body=[{'type': 'movie', 'movie': {'ids': {'trakt': ident}},
                    'progress': 42, 'paused_at': '2020-03-01T12:00:00Z'} for ident in (10, 12)])
            return None
        self.intercept = replies

    def test_movie_sources_and_views_preserve_plain_list_and_do_not_read_history_early(self):
        self.movie_fixture()
        self.assertEqual(self.render(routes.url('trakt_movie_sources')).state, 'ready')
        choices = self.rows[0][0]
        self.assertEqual(self.render(choices).state, 'ready')
        self.assertEqual(len(self.rows), 5)
        self.assertTrue(all(folder for _, _, folder in self.rows))
        self.assertFalse(any('/watched/' in p or '/sync/playback' in p for p in self.calls))
        self.assertEqual(self.render(self.source()).state, 'ready')
        self.assertEqual(len(self.rows), 5)  # Original mixed movie/show list stays unchanged.
        self.assertTrue(all('playcount' not in row[1].tag.values for row in self.rows))

    def test_movie_filters_and_details_share_progress_without_per_title_reads(self):
        self.movie_fixture()
        ref = self.library.widget_sources()['items'][0]['ref']
        expected = {'all': ['Movie 10', 'Movie 11', 'Movie 13', 'Movie 12'],
                    'unwatched': ['Movie 10', 'Movie 11', 'Movie 13'],
                    'released_unwatched': ['Movie 10'], 'unfinished': ['Movie 10'],
                    'upcoming': ['Movie 11']}
        for mode, titles in expected.items():
            self.assertEqual(self.render(routes.url('trakt_list', ref=ref, filter=mode), widget=True).state, 'ready')
            self.assertEqual([row[1].label for row in self.rows], titles)
            self.assertTrue(all(not folder for _, _, folder in self.rows))
        self.assertEqual(self.calls.count('/users/me/watched/movies'), 1)
        self.assertEqual(sum('/sync/playback?' in path for path in self.calls), 1)
        self.assertFalse(any(path.startswith('/movies/') for path in self.calls))
        self.render(routes.url('trakt_list', ref=ref, filter='unfinished'), widget=True)
        target, item, _ = self.rows[0]
        self.assertIn('Unfinished progress: 42%', item.tag.values['plot'])
        self.assertEqual(item.tag.values['rating'], (8.0, 10, 'trakt', True))
        self.assertIn('filter=unfinished', target)
        self.assertEqual(self.render(target).state, 'ready')
        self.assertIn('Unfinished progress: 42%', self.details[-1][1])
        self.assertIn('Watch status: unwatched', self.details[-1][1])
        self.assertIn('No playable source', self.details[-1][1])

    def test_movie_view_refetches_progress_after_reopen_and_rejects_old_account_ref(self):
        self.movie_fixture()
        ref = self.library.widget_sources()['items'][0]['ref']
        target = routes.url('trakt_list', ref=ref, filter='unfinished')
        self.assertEqual(self.render(target, widget=True).state, 'ready')
        self.watched = [10, 12]
        self.library = self.reopen()
        self.assertEqual(self.render(target, widget=True).state, 'empty')
        self.assertEqual(self.rows, [])
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        before = self.calls.count('/users/me/watched/movies')
        self.assertEqual(self.render(target, widget=True).state, 'unavailable')
        self.assertEqual(self.calls.count('/users/me/watched/movies'), before)
        self.assertEqual(self.rows, [])

    def test_failed_or_paginated_history_never_becomes_all_unwatched(self):
        self.movie_fixture()
        original = self.intercept
        for response in (Response(503), Response(200, {'x-pagination-page': '1'}, [])):
            self.intercept = lambda path: response if path == '/users/me/watched/movies' else original(path)
            self.library = self.reopen()
            ref = self.library.widget_sources()['items'][0]['ref']
            self.assertNotIn(self.render(routes.url('trakt_list', ref=ref, filter='unwatched'), widget=True).state,
                             {'ready', 'empty', 'partial'})
            self.assertEqual(self.rows, [])
            self.assertEqual(self.ends, [(False, False)])

    def test_movie_view_for_show_only_list_does_not_fetch_history(self):
        self.items = [{'type': 'show', 'show': {'ids': {'trakt': 20}, 'title': 'Synthetic show'}}]
        ref = self.library.widget_sources()['items'][0]['ref']
        self.assertEqual(self.render(routes.url('trakt_list', ref=ref, filter='all'), widget=True).state, 'empty')
        self.assertFalse(any('/watched/' in path or '/sync/playback' in path for path in self.calls))
        self.assertEqual(self.rows, [])

    def test_movie_rows_are_not_submitted_after_account_change_during_staging(self):
        self.movie_fixture()
        ref = self.library.widget_sources()['items'][0]['ref']
        self.on_item = lambda: self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.assertEqual(self.render(routes.url('trakt_list', ref=ref, filter='all'), widget=True).state, 'changed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])

    def test_widget_has_no_modal_dialogs_and_uri_survives_reopen(self):
        target = self.source()
        self.library = self.reopen()
        self.assertEqual(self.render(target, widget=True).state, 'ready')
        self.assertEqual(self.events, [])
        self.assertEqual(self.ends, [(True, False)])

    def test_native_ids_preserve_namespaces_without_extra_reads(self):
        self.items[0]['movie']['ids']['tmdb'] = 310
        self.items[1]['show']['ids']['tmdb'] = 420
        self.assertEqual(self.render(self.source()).state, 'ready')
        self.assertEqual([item.tag.values['ids'] for _, item, _ in self.rows],
                         [({'trakt': '10', 'tmdb': '310'}, 'trakt'),
                          ({'trakt': '20', 'tmdb': '420'}, 'trakt')])
        self.assertFalse(any('/movies/' in path or '/shows/' in path for path in self.calls))
        self.assertTrue(all('tmdb' not in target for target, _, _ in self.rows))

    def test_invalid_optional_tmdb_ids_never_become_native_ids(self):
        for value in (True, 0, -1, 2**63, '310', '1),RunScript(other'):
            self.items[0]['movie']['ids']['tmdb'] = value
            self.library.clear()
            self.assertEqual(self.render(self.source()).state, 'ready')
            self.assertEqual(self.rows[0][1].tag.values['ids'], ({'trakt': '10'}, 'trakt'))

    def test_show_seasons_then_read_only_episode_metadata(self):
        self.items[1]['show']['ids']['tmdb'] = 420
        def series(path):
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
        self.intercept = series
        self.render(self.source())
        target = self.rows[1][0]
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual(self.rows[0][1].label, 'Season 1')
        self.assertEqual(self.rows[0][1].tag.values['ids'],
                         ({'tvshow.trakt': '20', 'tvshow.tmdb': '420'}, 'tvshow.trakt'))
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual(self.rows[0][1].tag.values['episode'], 1)
        self.assertEqual(self.rows[0][1].tag.values['ids'],
                         ({'trakt': '21', 'tvshow.trakt': '20', 'tvshow.tmdb': '420'}, 'trakt'))
        self.assertEqual(self.rows[0][1].tag.values['show_title'], 'Synthetic show')
        self.assertEqual(self.rows[0][1].tag.values['playcount'], 0)
        self.assertTrue(self.rows[0][0].startswith(routes.BASE))
        self.assertFalse(self.rows[0][2])
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual(self.details[0][0], 'Synthetic episode')
        self.assertEqual(self.ends, [])
        del self.items[1]['show']['ids']['tmdb']
        self.library.clear()
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual(self.rows[0][1].tag.values['ids'],
                         ({'tvshow.trakt': '20'}, 'tvshow.trakt'))
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual(self.rows[0][1].tag.values['ids'],
                         ({'trakt': '21', 'tvshow.trakt': '20'}, 'trakt'))

    def test_empty_partial_authorization_and_offline_remain_distinct(self):
        target = self.source()
        self.items = []
        self.assertEqual(self.render(target).state, 'empty')
        self.assertEqual(self.rows, [])
        self.library.clear()
        self.items = [{'type': 'person', 'person': {'ids': {'trakt': 7}}}]
        self.assertEqual(self.render(target).state, 'partial')
        self.assertIn('not the complete list', self.categories[-1])
        self.store.disconnect()
        self.assertEqual(self.render(target, widget=True).state, 'authorization_needed')
        self.assertEqual(self.ends, [(False, False)])
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        def offline(path): raise OSError('synthetic-private-network')
        self.intercept = offline
        self.assertEqual(self.render(target, widget=True).state, 'offline')
        self.assertEqual(self.rows, [])
        self.assertNotIn('synthetic-private-network', self.categories[-1])

    def test_account_switch_during_staging_discards_all_staged_rows(self):
        target = self.source()
        def switch():
            self.store.install(TokenSet('synthetic-b', 'synthetic-refresh', 10000))
            self.library.lists()
        self.on_item = switch
        self.assertEqual(self.render(target).state, 'changed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])

    def test_selection_change_after_submission_never_finalizes_successfully(self):
        target = self.source()
        self.on_add = lambda: self.preferences.save('synthetic-a', [])
        self.assertEqual(self.render(target).state, 'changed')
        self.assertEqual(len(self.rows), 2)  # Kodi submission itself cannot be undone here.
        self.assertIn('choices changed', self.categories[-1])
        self.assertEqual(self.ends, [(False, False)])

    def test_cancel_after_submission_updates_category_and_fails_end(self):
        target = self.source()
        self.on_add = lambda: setattr(self, 'abort', True)
        self.assertEqual(self.render(target).state, 'cancelled')
        self.assertIn('Cancelled', self.categories[-1])
        self.assertEqual(self.ends, [(False, False)])

    def test_failed_item_or_bulk_submission_never_succeeds(self):
        target = self.source()
        def fail(): raise RuntimeError('synthetic-private-title')
        self.on_item = fail
        self.assertEqual(self.render(target).state, 'failed')
        self.assertEqual(self.rows, [])
        self.on_item = lambda: None
        self.submission = False
        self.assertEqual(self.render(target).state, 'failed')
        self.assertEqual(self.ends, [(False, False)])

    def test_cancel_and_invalid_routes_do_not_read_or_show_private_rows(self):
        self.abort = True
        self.assertEqual(self.render(routes.url('trakt_sources')).state, 'cancelled')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.rows, [])
        self.abort = False
        self.assertEqual(self.ui.render(self.library, 1, '?route=trakt_list&ref=bad').state, 'failed')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.rows, [])

    def test_details_route_in_widget_mode_never_opens_modal(self):
        self.render(self.source(), widget=True)
        target = self.rows[0][0]
        self.assertEqual(self.render(target, widget=True).state, 'failed')
        self.assertEqual(self.details, [])
        self.assertEqual(self.events, [])

    def test_account_change_in_final_cancel_probe_cannot_finalize_old_rows(self):
        target = self.source()
        def after_submission():
            self.on_abort_probe = lambda: self.store.install(TokenSet('synthetic-b', 'synthetic-refresh', 10000))
        self.on_add = after_submission
        self.assertEqual(self.render(target).state, 'changed')
        self.assertEqual(self.ends, [(False, False)])

    def test_explicit_failed_details_shows_fixed_feedback_only(self):
        self.render(self.source(), widget=True)
        target = self.rows[0][0]
        self.store.disconnect()
        self.assertEqual(self.render(target).state, 'authorization_needed')
        self.assertEqual(self.details[0][0], 'HomeFX')
        self.assertIn('authorization is needed', self.details[0][1])
        self.assertEqual(self.ends, [])

    def test_cancelled_details_does_not_open_a_followup_dialog(self):
        self.render(self.source(), widget=True)
        target = self.rows[0][0]
        self.abort = True
        self.assertEqual(self.render(target).state, 'cancelled')
        self.assertEqual(self.details, [])
        self.assertEqual(self.ends, [])

    def test_failed_error_feedback_is_reported_as_failed(self):
        self.render(self.source(), widget=True)
        target = self.rows[0][0]
        self.store.disconnect()
        def fail(*args): raise RuntimeError('synthetic-private-dialog')
        self.textviewer = fail
        result = self.render(target)
        self.assertEqual(result.state, 'failed')
        self.assertNotIn('synthetic-private-dialog', result.message)
        self.assertEqual(self.ends, [])

    def test_failed_category_still_attempts_failed_directory_end(self):
        target = self.source()
        self.store.disconnect()
        def fail(*args): raise RuntimeError('synthetic-private-category')
        self.setPluginCategory = fail
        result = self.render(target)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(self.ends, [(False, False)])
        self.assertNotIn('synthetic-private-category', result.message)

    def test_failed_end_is_not_masked_by_original_changed_result(self):
        target = self.source()
        self.on_add = lambda: self.preferences.save('synthetic-a', [])
        attempts = []
        def fail(handle, succeeded, cacheToDisc):
            attempts.append((succeeded, cacheToDisc))
            raise RuntimeError('synthetic-private-end')
        self.endOfDirectory = fail
        result = self.render(target)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(attempts, [(False, False)])
        self.assertNotIn('synthetic-private-end', result.message)

    def test_art_root_rejects_network_and_parent_traversal(self):
        for root in ['https://example.invalid/', '/synthetic/../art/', 'relative/', '/synthetic/']:
            if root == '/synthetic/':
                WidgetDirectoryUI(self, self.item, lambda: self, self, art_root=root)
            else:
                with self.assertRaises(ValueError):
                    WidgetDirectoryUI(self, self.item, lambda: self, self, art_root=root)

    def test_progress_cleanup_account_change_rejects_rows(self):
        target = self.source()
        self.on_close = lambda: self.store.disconnect()
        self.assertEqual(self.render(target).state, 'changed')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])
