"""Actual Library/Session and private stores with fabricated GET responses only."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_list_ui import TraktListUI
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore


class TraktListUITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.store = TokenStore(self.profile)
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        self.preferences = AccountPreferences(self.profile)
        self.calls, self.events, self.prompts = [], [], []
        self.answer, self.abort, self.progress_cancel = [0], False, False
        self.on_dialog = lambda: None
        self.on_close = lambda: None
        self.intercept = lambda path: None
        self.items = [{'type': 'movie', 'movie': {'ids': {'trakt': 10}, 'title': 'Synthetic Movie'}},
                      {'type': 'show', 'show': {'ids': {'trakt': 20}, 'title': 'Synthetic Show'}}]
        self.library = self.reopen()
        self.ui = TraktListUI(self, lambda: self, self)

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
                return Response(200, body=[{'list': {'ids': {'trakt': 2}, 'name': 'Synthetic liked',
                    'user': {'ids': {'slug': 'synthetic-owner'}}}}])
            return Response(200, body=self.items)

        def no_auth(*args):
            raise AssertionError('No authentication request expected')
        session = Session(TokenStore(self.profile), no_auth, api, 'synthetic-client',
                          'https://example.invalid/callback', clock=lambda: 1000)
        return Library(session, preferences=AccountPreferences(self.profile))

    def abortRequested(self):
        return self.abort

    def iscanceled(self):
        return self.progress_cancel

    def create(self, title, message):
        self.events.append(('loading', message))

    def update(self, percent):
        self.events.append(('update', percent))

    def close(self):
        self.events.append(('close',))
        self.on_close()

    def multiselect(self, title, labels, preselect):
        self.prompts.append((labels, preselect))
        self.on_dialog()
        return self.answer

    def test_construction_inactive_selection_restart_and_mixed_list(self):
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])
        self.assertEqual(self.ui.choose(self.library).state, 'saved')
        self.assertEqual(self.events[-1], ('close',))
        self.assertNotIn('[B]', self.prompts[0][0][0])
        reopened = self.reopen()
        self.assertEqual([ref.key for ref in reopened.selected_lists()], ['trakt-list:1'])
        result = TraktListUI(self, lambda: self, self).list(reopened, 'trakt-list:1')
        self.assertEqual(result.state, 'ready')
        self.assertEqual([row['kind'] for row in result.rows], ['movie', 'show'])
        self.assertTrue(all(row['watched'] is None and not row['playable'] for row in result.rows))
        self.assertNotIn('Synthetic', repr(result))
        self.assertNotIn('synthetic', repr(self.ui))
        self.assertFalse(any('/sync/' in path or '/oauth/' in path for path in self.calls))

    def test_widget_mode_has_no_dialogs_and_full_list_order(self):
        result = self.ui.list(self.library, 'trakt-list:2', widget=True)
        self.assertEqual(result.state, 'ready')
        self.assertEqual([row['trakt_id'] for row in result.rows], [10, 20])
        self.assertEqual(self.events, [])
        self.assertEqual(self.prompts, [])
        self.assertTrue(any('/users/synthetic-owner/lists/2/items?' in path for path in self.calls))

    def test_empty_and_unsupported_only_are_distinct(self):
        self.items = []
        self.assertEqual(self.ui.list(self.library, 'trakt-list:1').state, 'empty')
        self.library.clear()
        self.items = [{'type': 'person', 'person': {'ids': {'trakt': 5}, 'name': 'Synthetic Person'}}]
        result = self.ui.list(self.library, 'trakt-list:1')
        self.assertEqual((result.state, result.rows, result.unsupported_count), ('partial', (), 1))
        self.assertIn('not the complete list', result.message)

    def test_cancel_chooser_retains_previous_selection(self):
        self.library.select_lists(['trakt-list:2'])
        self.answer = None
        self.assertEqual(self.ui.choose(self.library).state, 'cancelled')
        self.assertEqual([ref.key for ref in self.reopen().selected_lists()], ['trakt-list:2'])
        self.assertEqual(self.prompts[0][1], [1])

    def test_deselect_all_is_an_explicit_save(self):
        self.library.select_lists(['trakt-list:2'])
        self.answer = []
        self.assertEqual(self.ui.choose(self.library).state, 'saved')
        self.assertEqual(self.reopen().selected_lists(), [])

    def test_account_switch_during_dialog_rejects_save(self):
        self.library.select_lists(['trakt-list:2'])
        self.on_dialog = lambda: self.store.install(TokenSet('synthetic-b', 'synthetic-refresh', 10000))
        result = self.ui.choose(self.library)
        self.assertEqual((result.state, result.rows), ('changed', ()))
        self.assertEqual(self.reopen().selected_lists(), [])
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        self.assertEqual([ref.key for ref in self.reopen().selected_lists()], ['trakt-list:2'])

    def test_account_switch_during_loading_cleanup_discards_rows(self):
        self.on_close = lambda: self.store.install(TokenSet('synthetic-b', 'synthetic-refresh', 10000))
        result = self.ui.list(self.library, 'trakt-list:1')
        self.assertEqual((result.state, result.rows), ('changed', ()))

    def test_reentrant_new_account_read_does_not_bless_old_results(self):
        def switch_and_read():
            self.store.install(TokenSet('synthetic-b', 'synthetic-refresh', 10000))
            self.library.lists()
        self.on_close = switch_and_read
        result = self.ui.list(self.library, 'trakt-list:1')
        self.assertEqual((result.state, result.rows), ('changed', ()))

    def test_abort_before_read_and_cancel_after_read(self):
        self.abort = True
        self.assertEqual(self.ui.list(self.library, 'trakt-list:1').state, 'cancelled')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])
        self.abort = False
        self.progress_cancel = True
        result = self.ui.list(self.library, 'trakt-list:1')
        self.assertEqual((result.state, result.rows), ('cancelled', ()))
        self.assertEqual(self.events[-1], ('close',))

    def test_error_states_never_become_empty_or_keep_old_rows(self):
        for status, expected in [(401, 'authorization_needed'), (403, 'unavailable'),
                                 (429, 'limited'), (503, 'failed')]:
            with self.subTest(status=status):
                self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
                self.library.clear()
                self.intercept = lambda path, code=status: Response(code, body={'private': 'synthetic-secret'})
                result = self.ui.list(self.library, 'trakt-list:1', widget=True)
                self.assertEqual((result.state, result.rows), (expected, ()))
                self.assertNotIn('synthetic-secret', result.message)
        self.assertEqual(self.events, [])

    def test_missing_authorization_and_offline_are_distinct(self):
        self.store.disconnect()
        self.assertEqual(self.ui.list(self.library, 'trakt-list:1').state, 'authorization_needed')
        self.assertEqual(self.calls, [])
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))

        def offline(path):
            raise OSError('synthetic-private-network-details')
        self.intercept = offline
        result = self.ui.list(self.library, 'trakt-list:1')
        self.assertEqual((result.state, result.rows), ('offline', ()))
        self.assertNotIn('synthetic-private', result.message)

    def test_invalid_dialog_answer_never_changes_selection(self):
        self.library.select_lists(['trakt-list:2'])
        for answer in [[True], [-1], [2], [0, 0], '0', [[0]]]:
            self.answer = answer
            self.assertEqual(self.ui.choose(self.library).state, 'failed')
            self.assertEqual([ref.key for ref in self.reopen().selected_lists()], ['trakt-list:2'])

    def test_season_and_episode_views_use_existing_read_only_joins(self):
        episode = {'ids': {'trakt': 21}, 'title': 'Synthetic episode',
                   'season': 1, 'number': 1, 'first_aired': '2020-01-01T00:00:00Z'}
        def series(path):
            if path == '/shows/20/seasons?extended=full':
                return Response(200, body=[{'number': 1, 'ids': {'trakt': 201}, 'episode_count': 1}])
            if path == '/shows/20/seasons/1?extended=full':
                return Response(200, body=[episode])
            if path.startswith('/shows/20/progress/watched?'):
                return Response(200, body={'seasons': [{'number': 1, 'episodes': [
                    {'number': 1, 'completed': False}]}]})
            if path.startswith('/sync/playback?'):
                return Response(200, body=[])
            return None
        self.intercept = series
        seasons = self.ui.seasons(self.library, 20)
        self.assertEqual(seasons.state, 'ready')
        self.assertEqual(len(seasons.rows), 1)
        episodes = self.ui.episodes(self.library, 20, 1)
        self.assertEqual(episodes.state, 'ready')
        self.assertEqual(episodes.rows[0]['trakt_id'], 21)
        self.assertFalse(episodes.rows[0]['watched'])
        self.assertTrue(episodes.rows[0]['aired_unwatched'])

    def test_cleanup_failure_discards_success_payload(self):
        def fail():
            raise RuntimeError('synthetic-private-path')
        self.on_close = fail
        result = self.ui.list(self.library, 'trakt-list:1')
        self.assertEqual((result.state, result.rows), ('failed', ()))
        self.assertNotIn('synthetic-private-path', result.message)
        self.assertEqual(sum(event == ('close',) for event in self.events), 1)
