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

    def test_widget_has_no_modal_dialogs_and_uri_survives_reopen(self):
        target = self.source()
        self.library = self.reopen()
        self.assertEqual(self.render(target, widget=True).state, 'ready')
        self.assertEqual(self.events, [])
        self.assertEqual(self.ends, [(True, False)])

    def test_show_seasons_then_read_only_episode_metadata(self):
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
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual(self.rows[0][1].tag.values['episode'], 1)
        self.assertEqual(self.rows[0][1].tag.values['playcount'], 0)
        self.assertTrue(self.rows[0][0].startswith(routes.BASE))
        self.assertFalse(self.rows[0][2])
        self.assertEqual(self.render(self.rows[0][0]).state, 'ready')
        self.assertEqual(self.details[0][0], 'Synthetic episode')
        self.assertEqual(self.ends, [])

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
