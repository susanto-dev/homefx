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
