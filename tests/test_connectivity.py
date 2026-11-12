"""Exercise transport/session/library contracts through fabricated HTTP bodies."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_transport import Transport
from resources.lib.trakt_session import Session
from resources.lib.trakt_library import Library
from resources.lib.trakt_tokens import TokenStore


class WireResponse:
    status = 200

    def __init__(self, value):
        self.data = json.dumps(value).encode('utf-8')
        self.stream = io.BytesIO(self.data)

    def getheaders(self):
        return [('Content-Type', 'application/json'), ('Content-Length', str(len(self.data)))]

    def read(self, count):
        return self.stream.read(count)

    def close(self):
        self.stream.close()


@unittest.skipUnless(os.name == 'posix', 'Private profile requires POSIX permissions')
class ConnectivityTests(unittest.TestCase):
    def test_device_login_refresh_and_account_isolated_list_cache(self):
        wall, mono = [1000], [0]
        requests = []
        owner = self

        class Connection:
            def __init__(self, host, port, timeout, context):
                self.host = host
                self.sock = object()  # Fake connection never performs socket I/O.
                owner.assertEqual(port, 443)
                owner.assertTrue(context.check_hostname)

            def connect(self):
                pass

            def request(self, method, path, body=None, headers=None):
                requests.append((self.host, method, path))
                if self.host == 'auth.trakt.tv':
                    payload = json.loads(body)
                    owner.assertNotIn('client_secret', payload)
                    if path == '/oauth/device/code':
                        self.value = {'device_code': 'synthetic-device', 'user_code': 'DEMO',
                                      'verification_url': 'https://trakt.tv/activate',
                                      'expires_in': 600, 'interval': 5}
                    else:
                        refresh = path == '/oauth/token'
                        if refresh:
                            owner.assertEqual(payload['refresh_token'], 'synthetic-refresh-one')
                            owner.assertEqual(payload['redirect_uri'], 'https://example.invalid/callback')
                        suffix = 'two' if refresh else 'one'
                        self.value = {'access_token': 'synthetic-access-' + suffix,
                                      'refresh_token': 'synthetic-refresh-' + suffix,
                                      'token_type': 'bearer', 'created_at': wall[0], 'expires_in': 100}
                else:
                    owner.assertEqual(self.host, 'api.trakt.tv')
                    owner.assertEqual(method, 'GET')
                    if path.startswith('/users/me/lists?'):
                        second = headers['Authorization'] == 'Bearer synthetic-other-account'
                        self.value = [{'ids': {'trakt': 2 if second else 1},
                                       'name': 'Second demo list' if second else 'First demo list'}]
                    elif path.startswith('/users/likes/lists?'):
                        self.value = []
                    else:
                        owner.fail('Unexpected endpoint')

            def getresponse(self):
                return WireResponse(self.value)

            def close(self):
                pass

        transport = Transport(connection_factory=Connection, clock=lambda: mono[0])
        with tempfile.TemporaryDirectory() as profile:
            store = TokenStore(profile, clock=lambda: wall[0])
            session = Session(store, transport.oauth_request, transport.api_request,
                              'synthetic-client', 'https://example.invalid/callback',
                              clock=lambda: wall[0], monotonic=lambda: mono[0])
            library = Library(session)
            self.assertEqual(session.status()['state'], 'disconnected')
            self.assertEqual(requests, [])
            session.begin_login()
            self.assertEqual(session.poll_login(), 'pending')
            mono[0] = 5
            self.assertEqual(session.poll_login(), 'authorized')
            self.assertEqual([r.key for r in library.lists()], ['trakt-list:1'])
            count = len(requests)
            library.select_lists(['trakt-list:1'])
            self.assertEqual([r.name for r in library.selected_lists()], ['First demo list'])
            self.assertEqual(len(requests), count)

            wall[0] = 1050  # Token is inside the safety margin: rotate once.
            self.assertEqual([r.key for r in library.lists()], ['trakt-list:1'])
            self.assertEqual(store.snapshot().tokens.access_token, 'synthetic-access-two')
            self.assertEqual(sum(path == '/oauth/token' for _, _, path in requests), 1)
            library.select_lists(['trakt-list:1'])

            other = TokenStore(profile, clock=lambda: wall[0])
            other.install(TokenSet('synthetic-other-account', 'synthetic-other-refresh', 10000))
            self.assertEqual(library.selected_lists(), [])
            self.assertEqual([r.name for r in library.lists()], ['Second demo list'])
            library.disconnect()
            self.assertEqual(session.status()['state'], 'disconnected')
            self.assertIsNone(store.snapshot().tokens)
