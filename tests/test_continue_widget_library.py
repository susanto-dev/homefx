"""Account-wide widget joins use fabricated metadata and temporary preferences."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError
from resources.lib.trakt_client import ApiError
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError


class FeedSession:
    def __init__(self):
        self.generation, self.data_revision = 1, 0
        self.account, self.connected = 'synthetic-a', True
        self.calls, self.hook = [], None
        self.responses = {
            ('paused',): [
                {'type': 'movie', 'progress': 40, 'paused_at': '2020-01-02T00:00:00Z',
                 'movie': {'ids': {'trakt': 1}}},
                {'type': 'episode', 'progress': 30, 'paused_at': '2020-01-03T00:00:00Z',
                 'show': {'ids': {'trakt': 20}},
                 'episode': {'ids': {'trakt': 11}, 'season': 1, 'number': 1}}],
            ('watched_movies',): (),
            ('movie_details', 1): {'ids': {'trakt': 1}, 'title': 'Synthetic movie', 'released': '2019-01-01'},
            ('episode_details', 20, 1, 1): {'show_id': 20, 'episode': {
                'ids': {'trakt': 11}, 'title': 'Synthetic episode', 'season': 1, 'number': 1,
                'first_aired': '2019-01-01T00:00:00Z'}},
            ('show_progress', 20, False): {'show_id': 20, 'progress': {'seasons': [
                {'number': 1, 'episodes': [{'number': 1, 'completed': False}]}]}},
        }

    def cache_key(self):
        self.assert_current(self.generation)
        return self.generation

    def assert_current(self, generation):
        if not self.connected or generation != self.generation:
            raise AuthError('session_changed')

    def read(self, operation, *args):
        self.assert_current(self.generation)
        key = (operation,) + args
        self.calls.append(key)
        if self.hook:
            self.hook(key)
        if operation == 'settings':
            return {'user': {'ids': {'uuid': self.account}}}
        return deepcopy(self.responses[key])

    def disconnect(self):
        self.connected = False
        self.generation += 1


class ContinueWidgetLibraryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.preferences = AccountPreferences(self.profile)
        self.session = FeedSession()
        self.library = self.reopen()

    def reopen(self):
        return Library(self.session, preferences=AccountPreferences(self.profile))

    def source(self):
        return self.library.widget_continue_sources()['items'][0]['ref']

    def test_source_needs_no_list_selection_and_reads_only_verified_identity(self):
        result = self.library.widget_continue_sources()
        self.assertEqual(self.session.calls, [('settings',)])
        self.assertEqual(len(result['items']), 1)
        self.assertRegex(result['items'][0]['ref'], r'^[a-f0-9]{64}$')
        self.assertEqual(self.preferences.snapshot('synthetic-a')[1], [])
        result['guard']()
        self.assertEqual(self.session.calls, [('settings',)])

    def test_mixed_join_order_identity_details_and_reopen_have_no_list_reads(self):
        ref = self.source()
        result = self.library.widget_continue(ref)
        rows = result['items']
        self.assertEqual([row['trakt_id'] for row in rows], [11, 1])
        self.assertTrue(all(row['playable'] is False for row in rows))
        self.assertEqual(rows[0]['show_trakt_id'], 20)
        self.assertNotIn('show_title', rows[0])
        self.assertTrue(all('resume' not in row for row in rows))
        self.assertEqual(self.library.widget_continue_details(ref, rows[0]['item_ref'])['items'], [rows[0]])
        self.library = self.reopen()
        self.assertEqual(self.source(), ref)
        self.assertEqual(self.library.widget_continue(ref)['items'], rows)
        self.assertFalse(any('list' in call[0] for call in self.session.calls))

    def test_unknown_episode_progress_is_preserved_and_watched_movie_excluded(self):
        self.session.responses[('watched_movies',)] = (1,)
        self.session.responses[('show_progress', 20, False)]['progress']['seasons'] = []
        rows = self.library.widget_continue(self.source())['items']
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['watched'])
        self.assertFalse(rows[0]['aired_unwatched'])

    def test_empty_pauses_are_success_without_details_or_history_reads(self):
        self.session.responses[('paused',)] = []
        result = self.library.widget_continue(self.source())
        self.assertEqual(result['items'], [])
        self.assertEqual(self.session.calls, [('settings',), ('paused',)])
        result['guard']()

    def test_bad_or_foreign_ref_fails_before_pauses_and_invalid_items_before_identity(self):
        for value in (None, True, 'private-id', 'A' * 64):
            with self.subTest(value_type=type(value)), self.assertRaises(ApiError):
                self.library.widget_continue(value)
        with self.assertRaises(ApiError):
            self.library.widget_continue_details('a' * 64, 'private-id')
        self.assertEqual(self.session.calls, [])
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.library.widget_continue('0' * 64)
        self.assertEqual(self.session.calls, [('settings',)])

    def test_failure_and_mismatched_metadata_never_produce_partial_rows(self):
        ref = self.source()
        for mode in ('failure', 'identity'):
            with self.subTest(mode=mode):
                self.library = self.reopen()
                if mode == 'failure':
                    def hook(key):
                        if key[0] == 'episode_details':
                            raise ApiError('service_unavailable')
                    self.session.hook = hook
                else:
                    self.session.hook = None
                    self.session.responses[('episode_details', 20, 1, 1)]['episode']['ids']['trakt'] = 99
                with self.assertRaises(ApiError):
                    self.library.widget_continue(ref)
                self.assertEqual(len(self.library._cache._entries), 0)

    def test_replaced_account_rejects_old_feed_before_history_and_old_guard(self):
        source = self.library.widget_continue_sources()
        ref = source['items'][0]['ref']
        self.session.account = 'synthetic-b'
        self.session.generation += 1
        with self.assertRaises(AuthError):
            source['guard']()
        self.session.calls.clear()
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.reopen().widget_continue(ref)
        self.assertEqual(self.session.calls, [('settings',)])
        self.assertNotEqual(self.reopen().widget_continue_sources()['items'][0]['ref'], ref)

    def test_rotation_same_account_preserves_ref_but_invalidates_old_render_guard(self):
        old = self.library.widget_continue_sources()
        self.session.generation += 1
        with self.assertRaises(AuthError):
            old['guard']()
        self.assertEqual(self.reopen().widget_continue_sources()['items'][0]['ref'], old['items'][0]['ref'])

    def test_disconnect_and_clear_epoch_invalidate_feed_and_pending_render(self):
        result = self.library.widget_continue(self.source())
        ref = self.source()
        self.preferences.clear_all()
        with self.assertRaises(PreferencesError):
            result['guard']()
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.reopen().widget_continue(ref)
        current = self.reopen().widget_continue_sources()['items'][0]['ref']
        self.library.disconnect()
        before = len(self.session.calls)
        with self.assertRaises(AuthError):
            self.reopen().widget_continue(current)
        self.assertEqual(len(self.session.calls), before)

    def test_selection_changes_do_not_revoke_account_feed(self):
        result = self.library.widget_continue_sources()
        ref = result['items'][0]['ref']
        self.preferences.save('synthetic-a', ['trakt-list:1'])
        result['guard']()
        self.assertEqual(self.reopen().widget_continue_sources()['items'][0]['ref'], ref)

    def test_removed_pause_cannot_be_opened_by_stale_item_ref(self):
        ref = self.source()
        item = self.library.widget_continue(ref)['items'][0]['item_ref']
        self.session.responses[('paused',)] = []
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.reopen().widget_continue_details(ref, item)

    def test_revision_and_account_changes_during_join_fail_final_guard(self):
        ref = self.source()
        for mode in ('revision', 'account', 'epoch'):
            with self.subTest(mode=mode):
                self.library = self.reopen()
                def hook(key):
                    if key[0] == 'episode_details':
                        if mode == 'revision':
                            self.session.data_revision += 1
                        elif mode == 'account':
                            self.session.generation += 1
                        else:
                            self.preferences.clear_all()
                self.session.hook = hook
                with self.assertRaises((AuthError, ApiError)):
                    self.library.widget_continue(ref)
                self.assertEqual(len(self.library._cache._entries), 0)
        self.session.hook = None

    def test_revision_change_after_load_invalidates_render_and_store_is_required(self):
        result = self.library.widget_continue(self.source())
        self.session.data_revision += 1
        with self.assertRaisesRegex(ApiError, 'data_changed'):
            result['guard']()
        with self.assertRaisesRegex(PreferencesError, 'widget_storage_required'):
            Library(self.session).widget_continue_sources()

    def test_epoch_change_while_refs_are_issued_cannot_return_rows(self):
        ref = self.source()
        original = self.library._preferences.widget_feed_item_refs
        def changed(*args, **kwargs):
            values = original(*args, **kwargs)
            self.preferences.clear_all()
            return values
        with patch.object(self.library._preferences, 'widget_feed_item_refs', side_effect=changed):
            with self.assertRaises(PreferencesError):
                self.library.widget_continue(ref)
