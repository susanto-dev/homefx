"""Fabricated provider-to-player workflow; no network or Kodi player is created."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.debrid_auth import DeviceLogin, VERIFY_URL
from resources.lib.debrid_client import Client, Response
from resources.lib.playback import PlaybackAttempt, PlaybackResult


class DebridWorkflowTests(unittest.TestCase):
    def test_device_grant_resolution_and_player_acceptance_are_separate(self):
        clock = [0]
        responses = iter([
            Response(200, body=dict(device_code='synthetic-code', user_code='DEMO',
                interval=5, expires_in=60, verification_url=VERIFY_URL)),
            Response(200, body=dict(client_id='synthetic-user-client',
                                   client_secret='synthetic-user-secret')),
            Response(200, body=dict(access_token='synthetic-access',
                refresh_token='synthetic-refresh', expires_in=3600, token_type='Bearer')),
        ])
        flow = DeviceLogin(lambda *args: next(responses), 'synthetic-public-client',
                           clock=lambda: clock[0], wall_clock=lambda: 1000)
        flow.begin()
        self.assertEqual(flow.poll(), 'pending')
        clock[0] = 5
        self.assertEqual(flow.poll(), 'authorized')
        calls, started = [], []

        def request(method, path, headers, body):
            calls.append((method, path))
            self.assertEqual(headers['Authorization'], 'Bearer synthetic-access')
            self.assertEqual(body, {'link': 'https://host.example/authorized-source'})
            return Response(200, body=dict(id='demo', filename='invented.mp4',
                filesize=100, download='https://cdn.example/private-demo-link'))

        client = Client(request, flow.tokens.access_token)

        def player(url, identity, resume):
            started.append((url, identity, resume))
            return True

        attempt = PlaybackAttempt(client.unrestrict, player, lambda: False, lambda: 7, 7)
        identity = {'kind': 'episode', 'show_trakt_id': 10, 'season': 1, 'episode': 2}
        self.assertEqual(attempt.run(identity, 'https://host.example/authorized-source', 42),
                         PlaybackResult.ACCEPTED)
        self.assertEqual(started, [('https://cdn.example/private-demo-link', identity, 42)])
        self.assertEqual(calls, [('POST', '/rest/1.0/unrestrict/link')])
        self.assertEqual(attempt.run(identity, 'https://host.example/authorized-source'),
                         PlaybackResult.ALREADY_ATTEMPTED)
        self.assertEqual(len(calls), 1)

    def test_account_change_after_resolution_prevents_player_and_retry(self):
        generation, calls, starts = [1], [], []

        def request(method, path, headers, body):
            calls.append(path)
            generation[0] = 2
            return Response(200, body=dict(id='demo', filename='invented.mp4',
                filesize=100, download='https://cdn.example/private-demo-link'))

        attempt = PlaybackAttempt(Client(request, 'synthetic-access').unrestrict,
            lambda *args: starts.append(args), lambda: False, lambda: generation[0], 1)
        self.assertEqual(attempt.run({'kind': 'movie', 'trakt_id': 10},
                                    'https://host.example/authorized-source'),
                         PlaybackResult.SESSION_CHANGED)
        self.assertEqual(starts, [])
        self.assertEqual(attempt.run({'kind': 'movie', 'trakt_id': 10},
                                    'https://host.example/authorized-source'),
                         PlaybackResult.ALREADY_ATTEMPTED)
        self.assertEqual(len(calls), 1)


class DurableProviderWorkflowTests(unittest.TestCase):
    def test_grant_restart_refresh_resolution_uses_one_private_provider_store(self):
        import json
        import tempfile
        from resources.lib.debrid_store import CredentialStore
        from resources.lib.debrid_session import Session
        from resources.lib.debrid_transport import Transport
        from tests.test_debrid_transport import Connections, wire

        clock, monotonic = [1000], [0]
        bodies = [
            dict(device_code='synthetic-code', user_code='DEMO', interval=5,
                 expires_in=60, verification_url=VERIFY_URL),
            dict(client_id='synthetic-bound', client_secret='synthetic-secret'),
            dict(access_token='synthetic-first', refresh_token='synthetic-refresh',
                 expires_in=120, token_type='Bearer'),
            dict(access_token='synthetic-rotated', refresh_token='synthetic-next',
                 expires_in=3600, token_type='Bearer'),
            dict(type='premium', premium=100, expiration='2026-12-01T00:00:00Z'),
            dict(id='demo', filename='invented.mp4', filesize=100,
                 download='https://cdn.example/private-demo-link'),
        ]
        connections = Connections([wire(json.dumps(body).encode()) for body in bodies])
        transport = Transport(connection_factory=connections, clock=lambda: monotonic[0])
        with tempfile.TemporaryDirectory() as profile:
            store = CredentialStore(profile, clock=lambda: clock[0])
            session = Session(store, transport.oauth_request, transport.api_request,
                'synthetic-public', clock=lambda: clock[0], monotonic=lambda: monotonic[0])
            session.begin_login()
            monotonic[0] = 5
            self.assertEqual(session.poll_login(), 'authorized')
            self.assertEqual(len(connections.calls), 3)
            reopened = CredentialStore(profile, clock=lambda: clock[0])
            session = Session(reopened, transport.oauth_request, transport.api_request,
                'synthetic-public', clock=lambda: clock[0], monotonic=lambda: monotonic[0])
            clock[0] = 1090
            self.assertEqual(session.status()['state'], 'refresh_required')
            self.assertEqual(len(connections.calls), 3)  # Local status never refreshes.
            self.assertEqual(session.account().type, 'premium')
            generation = session.current_generation()
            self.assertEqual(reopened.snapshot().tokens.access_token, 'synthetic-rotated')
            accepted = []

            def player(url, identity, resume):
                accepted.append((url, identity, resume))
                return True

            attempt = PlaybackAttempt(session.unrestrict, player, lambda: False,
                                      session.current_generation, generation)
            self.assertEqual(attempt.run({'kind': 'movie', 'trakt_id': 10},
                                        'https://host.example/authorized-source'),
                             PlaybackResult.ACCEPTED)
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(connections.calls), 6)
            self.assertTrue(all(host == 'api.real-debrid.com' for host, _ in connections.calls))
            self.assertTrue(all(sock.closed for sock in connections.sockets))
            self.assertIn(b'Authorization: Bearer synthetic-rotated',
                          b''.join(connections.sockets[-1].sent))
            self.assertFalse((Path(profile) / 'trakt').exists())
            self.assertTrue(session.disconnect(expected_generation=generation))
            self.assertEqual(reopened.snapshot().state, 'disconnected')
            self.assertIsNone(reopened.snapshot().credentials)
            self.assertIsNone(reopened.snapshot().tokens)
