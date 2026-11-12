"""Combined account preferences/actions use fabricated service state only."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


class WorkflowTests(unittest.TestCase):
    def test_saved_selection_refresh_and_uncertain_write_reconciliation(self):
        clock = [1000]
        watched = [False]
        lose_response = [False]
        writes, refreshes, reads = [], [], []
        active_library = [None]

        def api(method, path, headers, body=None):
            self.assertEqual(method, 'GET')
            reads.append(path)
            if path == '/users/settings':
                return Response(200, body={'user': {'ids': {'uuid': 'synthetic-account-uuid'}}})
            if path.startswith('/users/me/lists?'):
                return Response(200, body=[{'ids': {'trakt': 42}, 'name': 'Synthetic owned list'}])
            if path.startswith('/users/likes/lists?'):
                return Response(200, body=[])
            if '/seasons/' in path:
                return Response(200, body=[{'ids': {'trakt': 101}, 'title': 'Synthetic episode',
                    'season': 1, 'number': 1, 'first_aired': '2026-11-01T00:00:00Z'}])
            if '/progress/' in path:
                return Response(200, body={'seasons': [{'number': 1, 'episodes': [
                    {'number': 1, 'completed': watched[0]}]}]})
            self.assertTrue(path.startswith('/sync/playback?'))
            return Response(200, body=[])

        def oauth(method, path, body):
            self.assertEqual((method, path), ('POST', '/oauth/token'))
            refreshes.append(path)
            return Response(200, body={'access_token': 'synthetic-rotated-access',
                'refresh_token': 'synthetic-rotated-refresh', 'token_type': 'bearer',
                'created_at': clock[0], 'expires_in': 3600})

        def mutate(method, path, headers, body=None):
            self.assertEqual((method, path), ('POST', '/sync/history'))
            self.assertEqual(body['episodes'][0]['ids'], {'trakt': 101})
            writes.append(path)
            before_read = len(reads)
            with self.assertRaisesRegex(AuthError, 'action_in_progress'):
                active_library[0].episode_view(10, 1, NOW)
            self.assertEqual(len(reads), before_read)
            watched[0] = True  # Fabricated service applies the action before responding.
            if lose_response[0]:
                raise TimeoutError('synthetic response loss')
            return Response(200, body={'added': {'movies': 0, 'episodes': 1},
                                      'updated': {'movies': 0, 'episodes': 0}, 'not_found': {}})

        with tempfile.TemporaryDirectory() as profile:
            store = TokenStore(profile, clock=lambda: clock[0])
            store.install(TokenSet('synthetic-access', 'synthetic-refresh', 1100))
            preferences = AccountPreferences(profile)
            session = Session(store, oauth, api, 'synthetic-client', 'https://example.invalid/callback',
                              clock=lambda: clock[0], mutation_request=mutate)
            library = Library(session, preferences=preferences)
            active_library[0] = library
            library.select_lists(['trakt-list:42'])
            self.assertFalse(library.episode_view(10, 1, NOW)[0]['watched'])
            reads_before_action = len(reads)
            result = session.mutate('mark_watched', 'episode', 101, NOW)
            self.assertEqual(result.outcome, 'confirmed')
            self.assertEqual(len(writes), 1)
            first_revision = session.data_revision
            self.assertGreater(first_revision, 0)
            self.assertTrue(library.episode_view(10, 1, NOW)[0]['watched'])
            self.assertGreater(len(reads), reads_before_action)
            self.assertEqual([ref.key for ref in library.selected_lists()], ['trakt-list:42'])

            clock[0] = 1050
            self.assertEqual([ref.key for ref in library.selected_lists()], ['trakt-list:42'])
            self.assertEqual(len(refreshes), 1)
            reopened = Library(session, preferences=AccountPreferences(profile))
            active_library[0] = reopened
            self.assertEqual([ref.key for ref in reopened.selected_lists()], ['trakt-list:42'])

            watched[0] = False
            reopened.clear()
            self.assertFalse(reopened.episode_view(10, 1, NOW)[0]['watched'])
            lose_response[0] = True
            uncertain = session.mutate('mark_watched', 'episode', 101, NOW)
            self.assertEqual(uncertain.outcome, 'uncertain')
            self.assertEqual(len(writes), 2)  # One attempt per explicit action, no replay.
            self.assertGreater(session.data_revision, first_revision)
            self.assertTrue(reopened.episode_view(10, 1, NOW)[0]['watched'])
            self.assertEqual(len(writes), 2)  # Reconciliation reads, not another write.
            reopened.disconnect()
            self.assertEqual(preferences.load('synthetic-account-uuid'), [])
            self.assertIsNone(store.snapshot().tokens)
