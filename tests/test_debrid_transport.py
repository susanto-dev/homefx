"""Real HTTP framing through synthetic sockets; never contacts a service account."""
import http.client
import io
import json
import socket
import ssl
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.debrid_auth import DeviceLogin, GRANT_TYPE, refresh
from resources.lib.debrid_client import Client, DebridError
from resources.lib.debrid_transport import Transport, TransportError

class MemorySocket:
    def __init__(self, wire, tick=None, chunk=8192):
        self.wire, self.tick, self.chunk = wire, tick, chunk
        self.closed = False
        self.sent, self.timeouts = [], []

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, data):
        self.sent.append(bytes(data))

    def recv_into(self, target):
        if self.tick:
            self.tick()
        count = min(len(target), len(self.wire), self.chunk)
        target[:count] = self.wire[:count]
        self.wire = self.wire[count:]
        return count

    def makefile(self, mode, buffering=0):
        sock = self
        class Reader(io.RawIOBase):
            def readable(self):
                return True

            def readinto(self, target):
                return sock.recv_into(target)
        return Reader()

    def close(self):
        self.closed = True


def wire(body=b'{}', status=200, headers=None):
    entries = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    if headers is not None:
        entries = headers
    return ("HTTP/1.1 %s Fixture\r\n" % status +
            "".join(k + ": " + v + "\r\n" for k, v in entries) + "\r\n").encode() + body


class Connections:
    def __init__(self, responses, tick=None, chunk=8192, connect_hook=None):
        self.responses = list(responses)
        self.tick, self.chunk, self.connect_hook = tick, chunk, connect_hook
        self.calls, self.sockets = [], []

    def __call__(self, host, **kwargs):
        self.calls.append((host, kwargs))
        memory = MemorySocket(self.responses.pop(0), self.tick, self.chunk)
        self.sockets.append(memory)
        hook = self.connect_hook
        class Connection(http.client.HTTPSConnection):
            def connect(self):
                if hook:
                    hook()
                self.sock = memory
        return Connection(host, **kwargs)


HEADERS = {"Authorization": "Bearer synthetic-access"}
POST_HEADERS = dict(HEADERS, **{"Content-Type": "application/x-www-form-urlencoded"})


class DebridTransportTests(unittest.TestCase):
    def test_device_credentials_token_refresh_and_rest_callbacks_use_real_http_framing(self):
        token = dict(access_token="synthetic-access", refresh_token="synthetic-refresh",
                     expires_in=3600, token_type="Bearer")
        bodies = [dict(device_code="synthetic&device", user_code="DEMO", interval=5,
                       expires_in=60, verification_url="https://real-debrid.com/device"),
                  dict(client_id="bound+id", client_secret="private&secret"), token, token,
                  dict(type="premium", premium=100, expiration="2026-12-01T00:00:00Z"),
                  dict(id="demo", filename="invented.mp4", filesize=100,
                       download="https://cdn.example/private-demo")]
        factory = Connections([wire(json.dumps(body).encode()) for body in bodies])
        now = [0]
        transport = Transport(connection_factory=factory, clock=lambda: now[0])
        flow = DeviceLogin(transport.oauth_request, "public+id", clock=lambda: now[0],
                           wall_clock=lambda: 1000)
        flow.begin()
        now[0] = 5
        self.assertEqual(flow.poll(), "authorized")
        refreshed = refresh(transport.oauth_request, flow.credentials, flow.tokens.refresh_token,
                            clock=lambda: 1000)
        client = Client(transport.api_request, refreshed.access_token)
        self.assertEqual(client.account().type, "premium")
        self.assertEqual(client.unrestrict("https://host.example/file?a=1&b=2").id, "demo")
        sent = [b"".join(sock.sent) for sock in factory.sockets]
        self.assertIn(b'GET /oauth/v2/device/code?client_id=public%2Bid&new_credentials=yes HTTP/1.1', sent[0])
        self.assertIn(b'GET /oauth/v2/device/credentials?client_id=public%2Bid&code=synthetic%26device HTTP/1.1', sent[1])
        token_form = (b'client_id=bound%2Bid&client_secret=private%26secret&code=synthetic%26device'
                      b'&grant_type=http%3A%2F%2Foauth.net%2Fgrant_type%2Fdevice%2F1.0')
        self.assertTrue(sent[2].endswith(token_form))
        self.assertIn(b'code=synthetic-refresh&grant_type=', sent[3])
        self.assertIn(b'Authorization: Bearer synthetic-access\r\n', sent[4])
        self.assertTrue(sent[5].endswith(b'link=https%3A%2F%2Fhost.example%2Ffile%3Fa%3D1%26b%3D2'))
        self.assertTrue(all(sock.closed for sock in factory.sockets))
        for host, kwargs in factory.calls:
            self.assertEqual(host, 'api.real-debrid.com')
            self.assertEqual(kwargs['port'], 443)
            self.assertTrue(kwargs['context'].check_hostname)
            self.assertEqual(kwargs['context'].verify_mode, ssl.CERT_REQUIRED)

    def test_download_pagination_header_reaches_client(self):
        item = dict(id='demo', filename='invented.mp4', filesize=1,
                    download='https://cdn.example/demo')
        body = json.dumps([item]).encode()
        factory = Connections([wire(body, headers=[('Content-Type', 'application/json'),
                  ('Content-Length', str(len(body))), ('X-Total-Count', '1')])])
        transport = Transport(connection_factory=factory)
        rows = Client(transport.api_request, 'synthetic-access').downloads()
        self.assertEqual(len(rows), 1)
        self.assertIn(b'GET /rest/1.0/downloads?page=1&limit=100 HTTP/1.1', b''.join(factory.sockets[0].sent))

    def test_error_json_is_bounded_and_opaque_repr_and_html_is_discarded(self):
        factory = Connections([wire(b'{"error":"synthetic-private"}', 403),
                               wire(b'<html>private</html>', 429, [('Content-Type', 'text/html'),
                                    ('Retry-After', '90'), ('Authorization', 'private')]),
                               wire(b'', 401)])
        transport = Transport(connection_factory=factory)
        response = transport.oauth_request('GET', '/oauth/v2/device/credentials',
                                           {'client_id': 'public', 'code': 'synthetic-code'})
        self.assertEqual(response.body, {'error': 'synthetic-private'})
        self.assertNotIn('private', repr(response))
        with self.assertRaises(DebridError) as caught:
            Client(transport.api_request, 'synthetic-token').account()
        self.assertEqual((caught.exception.kind, caught.exception.retry_after), ('rate_limit', 90))
        response = transport.api_request('GET', '/rest/1.0/user', HEADERS)
        self.assertEqual(response.body, {})
        self.assertTrue(all(sock.closed for sock in factory.sockets))

    def test_invalid_target_routes_fields_headers_and_methods_never_connect(self):
        factory = Connections([])
        transport = Transport(connection_factory=factory)
        paths = ['https://other.invalid/rest/1.0/user', '//other.invalid/a', '//[private',
                 '/rest/1.0/user#x', '/rest/1.0/user?access_token=private', '/rest/1.0/torrents',
                 '/rest/1.0/downloads', '/rest/1.0/downloads?page=1&page=2',
                 '/rest/1.0/downloads?page=1&limit=101', '/rest/1.0/downloads?page=%31&limit=1',
                 '/rest/1.0/downloads?page=1&limit=1&remote=1', '/rest/1.0/user\r\nprivate']
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(TransportError, '^invalid_request$'):
                transport.api_request('GET', path, HEADERS)
        for headers in ({'Authorization': 'Bearer private\r\nHost: other.invalid'},
                        dict(HEADERS, Host='other.invalid'), {'Authorization': 'Bearer '},
                        {'Authorization': 'Bearer private value'}):
            with self.assertRaisesRegex(TransportError, '^invalid_request$'):
                transport.api_request('GET', '/rest/1.0/user', headers)
        for body in ({'link': 'https://host.example/x', 'remote': 1},
                     {'link': 'http://host.example/x'}, {'link': 'https://127.0.0.1/x'}):
            with self.assertRaisesRegex(TransportError, '^invalid_request$'):
                transport.api_request('POST', '/rest/1.0/unrestrict/link', POST_HEADERS, body)
        for method, path, body in [('POST', '/oauth/v2/device/code', {'client_id': 'public', 'new_credentials': 'yes'}),
                                  ('GET', '/oauth/v2/device/code', {'client_id': 'public', 'new_credentials': 'no'}),
                                  ('GET', '/oauth/v2/device/credentials', {'client_id': 'public', 'code': 'private', 'extra': 'x'}),
                                  ('POST', '/oauth/v2/token', {'client_id': 'public', 'client_secret': 'private', 'code': 'code', 'grant_type': 'refresh_token'})]:
            with self.assertRaisesRegex(TransportError, '^invalid_request$'):
                transport.oauth_request(method, path, body)
        self.assertEqual(factory.calls, [])

    def test_redirect_and_failure_are_redacted_single_attempt_and_closed(self):
        factory = Connections([wire(b'private', 302, [('Location', 'https://private.example/token')])])
        with self.assertRaisesRegex(TransportError, '^redirect_refused$'):
            Transport(connection_factory=factory).api_request('GET', '/rest/1.0/user', HEADERS)
        self.assertEqual(len(factory.calls), 1)
        self.assertTrue(factory.sockets[0].closed)
        def fail():
            raise OSError('private-token private-source')
        factory = Connections([wire()], connect_hook=fail)
        with self.assertRaisesRegex(DebridError, 'uncertain') as caught:
            Client(Transport(connection_factory=factory).api_request, 'synthetic-token').unrestrict('https://host.example/file')
        self.assertNotIn('private', repr(caught.exception))
        self.assertEqual(len(factory.calls), 1)

    def test_invalid_json_and_response_bounds_are_enforced_for_errors_too(self):
        payloads = [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e9999}', b'null',
                    b'[' * 33 + b']' * 33, b'{"a":' + b'9' * 129 + b'}', b'{}{}']
        for status in (200, 403):
            for body in payloads:
                factory = Connections([wire(body, status)])
                with self.subTest(status=status, body=body[:10]), self.assertRaisesRegex(TransportError, '^invalid_json$'):
                    Transport(connection_factory=factory).api_request('GET', '/rest/1.0/user', HEADERS)
                self.assertTrue(factory.sockets[0].closed)
            for headers in (None, [('Content-Type', 'application/json')]):
                factory = Connections([wire(b'[' + b' ' * 1024 + b']', status, headers)])
                with self.assertRaisesRegex(TransportError, '^response_too_large$'):
                    Transport(connection_factory=factory, max_bytes=1024).api_request('GET', '/rest/1.0/user', HEADERS)

    def test_metadata_compression_framing_and_safe_headers_are_strict(self):
        cases = [[('Content-Type', 'text/html')], [('Content-Type', 'application/json'), ('Content-Encoding', 'gzip')],
                 [('Content-Type', 'application/json'), ('X-Total-Count', '1'), ('x-total-count', '2')],
                 [('Content-Type', 'application/json'), ('Retry-After', 'x' * 257)],
                 [('Content-Type', 'application/json'), ('Content-Length', '9999999999999')],
                 [('Content-Type', 'application/json'), ('Transfer-Encoding', 'chunked'), ('Content-Length', '2')],
                 [('Content-Type', 'application/json'), ('Transfer-Encoding', 'gzip')],
                 [('Content-Type', 'application/json')] + [('X-Test-' + str(i), 'ok') for i in range(64)]]
        for headers in cases:
            factory = Connections([wire(headers=headers)])
            with self.subTest(headers=headers[:2]), self.assertRaisesRegex(TransportError, '^invalid_response$'):
                Transport(connection_factory=factory).api_request('GET', '/rest/1.0/user', HEADERS)
            self.assertTrue(factory.sockets[0].closed)

    def test_deadline_includes_slow_headers_and_chunked_body(self):
        for payload, step, chunk, total in [(wire(), 0.6, 1, 1),
                (wire(b'4\r\n[1,2\r\n1\r\n]\r\n0\r\n\r\n', headers=[('Content-Type', 'application/json'),
                    ('Transfer-Encoding', 'chunked')]), 0.1, 8, 1.2)]:
            now = [0.0]
            def tick():
                now[0] += step
            factory = Connections([payload], tick=tick, chunk=chunk)
            with self.assertRaisesRegex(TransportError, '^timeout$'):
                Transport(connection_factory=factory, clock=lambda: now[0], total_timeout=total).api_request('GET', '/rest/1.0/user', HEADERS)
            self.assertTrue(factory.sockets[0].closed)

    def test_cancellation_before_connect_during_read_and_invalid_clock(self):
        factory = Connections([])
        with self.assertRaisesRegex(TransportError, '^cancelled$'):
            Transport(connection_factory=factory, cancelled=lambda: True).api_request('GET', '/rest/1.0/user', HEADERS)
        self.assertFalse(factory.calls)
        stopped = [False]
        def tick():
            stopped[0] = True
        factory = Connections([wire()], tick=tick)
        with self.assertRaisesRegex(TransportError, '^cancelled$'):
            Transport(connection_factory=factory, cancelled=lambda: stopped[0]).api_request('GET', '/rest/1.0/user', HEADERS)
        self.assertTrue(factory.sockets[0].closed)
        for clock in (lambda: float('nan'), lambda: float('inf'), lambda: True, lambda: 10 ** 400):
            with self.assertRaisesRegex(TransportError, '^transport_failed$'):
                Transport(connection_factory=Connections([]), clock=clock).api_request('GET', '/rest/1.0/user', HEADERS)

    def test_native_socket_reader_survives_connection_close_until_consumed(self):
        for protocol in (b'HTTP/1.0', b'HTTP/1.1'):
            reader, writer = socket.socketpair()
            try:
                payload = wire(b'{"items":[1,2]}', headers=[('Content-Type', 'application/json'), ('Connection', 'close')])
                writer.sendall(payload.replace(b'HTTP/1.1', protocol, 1))
                writer.shutdown(socket.SHUT_WR)
                class Connection(http.client.HTTPSConnection):
                    def connect(self):
                        self.sock = reader
                result = Transport(connection_factory=Connection).api_request('GET', '/rest/1.0/user', HEADERS)
                self.assertEqual(result.body, {'items': [1, 2]})
                self.assertEqual(reader.fileno(), -1)
            finally:
                reader.close()
                writer.close()

    def test_configuration_rejects_nonfinite_or_excessive_limits(self):
        for kwargs in ({'timeout': 0}, {'timeout': float('nan')}, {'total_timeout': float('inf')},
                       {'timeout': 10 ** 400}, {'max_bytes': True}, {'cancelled': None}):
            with self.assertRaisesRegex(TransportError, '^invalid_configuration$'):
                Transport(**kwargs)
