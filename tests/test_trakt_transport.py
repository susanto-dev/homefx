"""Exercise HTTPS framing with in-memory sockets; never use a service account."""
import http.client
import io
import socket
import ssl
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import DeviceLogin
from resources.lib.trakt_client import Client, ApiError
from resources.lib.trakt_transport import Transport, TransportError


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


HEADERS = {"Authorization": "Bearer synthetic-access", "trakt-api-key": "synthetic-client",
           "trakt-api-version": "2", "Content-Type": "application/json"}


class TransportTests(unittest.TestCase):
    def test_complete_movie_snapshot_endpoint_has_no_pagination_query(self):
        factory = Connections([wire(b'[]')])
        transport = Transport(connection_factory=factory)
        client = Client(transport.api_request, "synthetic-client", "synthetic-access")
        self.assertEqual(client.watched_movies(), ())
        self.assertIn(b"GET /users/me/watched/movies HTTP/1.1", b"".join(factory.sockets[0].sent))
        for suffix in ("?page=1", "?limit=100", "?extended=full"):
            with self.assertRaises(TransportError):
                transport.api_request("GET", "/users/me/watched/movies" + suffix, HEADERS)
        self.assertEqual(len(factory.calls), 1)

    def test_movie_snapshot_rejects_transport_pagination_markers(self):
        for header in ("X-Pagination-Item-Count", "X-Pagination-Custom"):
            with self.subTest(header=header):
                factory = Connections([wire(b'[]', headers=[
                    ("Content-Type", "application/json"), ("Content-Length", "2"),
                    (header, "42")])])
                client = Client(Transport(connection_factory=factory).api_request,
                                "synthetic-client", "synthetic-access")
                with self.assertRaises(ApiError):
                    client.watched_movies()
                self.assertEqual(len(factory.calls), 1)

    def test_real_http_framing_tls_hosts_and_callback_compatibility(self):
        responses = [wire(b'{"device_code":"synthetic-device","user_code":"DEMO",'
                          b'"verification_url":"https://trakt.tv/activate",'
                          b'"expires_in":600,"interval":5}'),
                     wire(b'{"token_type":"bearer","access_token":"synthetic-access",'
                          b'"refresh_token":"synthetic-refresh","created_at":1000,"expires_in":3600}'),
                     wire(b'{"user":{"ids":{"slug":"synthetic-user"}}}')]
        factory = Connections(responses)
        now = [0]
        transport = Transport(connection_factory=factory, clock=lambda: now[0])
        login = DeviceLogin(transport.oauth_request, "synthetic-client", lambda: now[0])
        login.begin()
        now[0] = 5
        self.assertEqual(login.poll(), "authorized")
        client = Client(transport.api_request, "synthetic-client", login.tokens.access_token)
        self.assertEqual(client.settings()["user"]["ids"]["slug"], "synthetic-user")
        self.assertEqual([host for host, _ in factory.calls], ["auth.trakt.tv", "auth.trakt.tv", "api.trakt.tv"])
        for _, kwargs in factory.calls:
            self.assertEqual(kwargs["port"], 443)
            self.assertEqual(kwargs["timeout"], 10)
            self.assertTrue(kwargs["context"].check_hostname)
            self.assertEqual(kwargs["context"].verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(all(sock.closed for sock in factory.sockets))
        sent = b"".join(factory.sockets[2].sent)
        self.assertIn(b"Host: api.trakt.tv\r\n", sent)
        self.assertIn(b"Authorization: Bearer synthetic-access\r\n", sent)
        self.assertNotIn(b"client_secret", b"".join(b"".join(s.sent) for s in factory.sockets))

    def test_invalid_targets_headers_and_methods_never_connect(self):
        factory = Connections([])
        transport = Transport(connection_factory=factory)
        paths = ["https://other.invalid/users/settings", "//other.invalid/path", "//[private",
                 "/users/settings#fragment", "/users/../settings", "/users/%2e%2e/settings",
                 "/users/settings?access_token=synthetic", "/users/settings?page=1&page=2",
                 "/users/settings?limit=101", "/users/settings?extended=secret", "/sync/history",
                 "/users/settings\r\nAuthorization: secret"]
        for path in paths:
            with self.subTest(path=path), self.assertRaisesRegex(TransportError, "^invalid_request$"):
                transport.api_request("GET", path, HEADERS)
        for headers in ({**HEADERS, "Host": "other.invalid"},
                        {**HEADERS, "Authorization": "Bearer secret\r\nvalue"},
                        {**HEADERS, "Authorization": "Bearer secret value"},
                        {**HEADERS, "Authorization": "Bearer "},
                        {**HEADERS, "trakt-api-key": "secret\nvalue"}):
            with self.assertRaisesRegex(TransportError, "^invalid_request$"):
                transport.api_request("GET", "/users/settings", headers)
        with self.assertRaises(TransportError):
            transport.api_request("POST", "/users/settings", HEADERS)
        with self.assertRaises(TransportError):
            transport.api_request("GET", "/users/settings", HEADERS, {})
        for path, body in [("/oauth/device/code", {"client_id": "synthetic", "client_secret": "forbidden"}),
                           ("/oauth/device/code", {"client_id": "secret\nvalue"}),
                           ("https://other.invalid/oauth/device/code", {"client_id": "synthetic"}),
                           ("/oauth/token", {"client_id": "synthetic", "redirect_uri": "urn:synthetic",
                                             "grant_type": "authorization_code", "refresh_token": "synthetic"})]:
            with self.assertRaises(TransportError):
                transport.oauth_request("POST", path, body)
        self.assertFalse(factory.calls)

    def test_valid_read_routes_preserve_pagination(self):
        paths = ["/users/me/lists?page=1&limit=100", "/users/likes/lists?page=2&limit=50",
                 "/users/synthetic-user/lists/123/items?extended=full&page=1&limit=100",
                 "/sync/playback?page=1&limit=100", "/shows/12/progress/watched?hidden=false&specials=false",
                 "/shows/12/seasons/1?extended=full"]
        factory = Connections([wire(b'[]') for _ in paths])
        transport = Transport(connection_factory=factory)
        for path in paths:
            self.assertEqual(transport.api_request("GET", path, HEADERS).body, [])
        for path, sock in zip(paths, factory.sockets):
            self.assertIn(("GET " + path + " HTTP/1.1\r\n").encode(), b"".join(sock.sent))

    def test_redirect_is_not_followed_or_exposed(self):
        factory = Connections([wire(b'private body', 302, [("Location", "https://other.invalid/secret")])])
        with self.assertRaisesRegex(TransportError, "^redirect_refused$"):
            Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS)
        self.assertEqual(len(factory.calls), 1)
        self.assertTrue(factory.sockets[0].closed)

    def test_error_response_keeps_only_safe_metadata_and_discards_html(self):
        factory = Connections([wire(b'<html>synthetic-private-body</html>', 429,
                             [("Retry-After", "120"), ("Authorization", "synthetic-private"),
                              ("Content-Type", "text/html")])])
        result = Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS)
        self.assertEqual(result.status, 429)
        self.assertEqual(result.headers, {"retry-after": "120"})
        self.assertIsNone(result.body)
        self.assertNotIn("private", repr(result))
        self.assertTrue(factory.sockets[0].closed)

    def test_strict_json_rejects_ambiguous_malformed_or_deep_bodies(self):
        payloads = [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e9999}',
                    b'[' * 33 + b']' * 33, b'{"a":' + b'9' * 129 + b'}', b'null', b'"secret"',
                    b'{"a":"\xff"}', b'{"synthetic-private":', b'{}{}']
        for body in payloads:
            with self.subTest(body=body[:30]):
                factory = Connections([wire(body)])
                with self.assertRaisesRegex(TransportError, "^invalid_json$"):
                    Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS)
                self.assertTrue(factory.sockets[0].closed)
        body = b'{"text":"[brackets] and \\"quoted\\"", "nested":[{"ok":true}]}'
        factory = Connections([wire(body)])
        self.assertTrue(Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS).body["nested"][0]["ok"])

    def test_size_limit_with_and_without_content_length(self):
        for headers in (None, [("Content-Type", "application/json")]):
            factory = Connections([wire(b'[' + b' ' * 1024 + b']', headers=headers)])
            with self.assertRaisesRegex(TransportError, "^response_too_large$"):
                Transport(connection_factory=factory, max_bytes=1024).api_request("GET", "/users/settings", HEADERS)
            self.assertTrue(factory.sockets[0].closed)

    def test_response_metadata_and_encoding_are_bounded(self):
        cases = [[("Content-Type", "text/html")], [("Content-Type", "application/json"), ("Content-Encoding", "gzip")],
                 [("Content-Type", "application/json"), ("Content-Length", "9999999999999")],
                 [("Content-Type", "application/json"), ("Retry-After", "1"), ("Retry-After", "2")],
                 [("Content-Type", "application/json"), ("X-Pagination-Page", "x" * 257)],
                 [("Content-Type", "application/json")] + [("X-Fixture-" + str(i), "ok") for i in range(64)]]
        for headers in cases:
            with self.subTest(headers=headers[:2]):
                factory = Connections([wire(headers=headers)])
                with self.assertRaisesRegex(TransportError, "^invalid_response$"):
                    Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS)
                self.assertTrue(factory.sockets[0].closed)

    def test_elapsed_deadline_applies_during_slow_header_receives(self):
        now = [0.0]
        def tick():
            now[0] += 0.6
        factory = Connections([wire()], tick=tick, chunk=1)
        with self.assertRaisesRegex(TransportError, "^timeout$"):
            Transport(connection_factory=factory, clock=lambda: now[0], total_timeout=1).api_request("GET", "/users/settings", HEADERS)
        self.assertEqual(now[0], 1.2)
        self.assertTrue(factory.sockets[0].closed)
        self.assertLess(factory.sockets[0].timeouts[-1], 1)

    def test_elapsed_deadline_applies_during_chunked_body(self):
        now = [0.0]
        body = b'4\r\n[1,2\r\n1\r\n]\r\n0\r\n\r\n'
        response = wire(body, headers=[("Content-Type", "application/json"), ("Transfer-Encoding", "chunked")])
        def tick():
            now[0] += 0.1
        factory = Connections([response], tick=tick, chunk=8)
        with self.assertRaisesRegex(TransportError, "^timeout$"):
            Transport(connection_factory=factory, clock=lambda: now[0], total_timeout=1.2).api_request("GET", "/users/settings", HEADERS)
        self.assertTrue(factory.sockets[0].closed)

    def test_cancel_before_connect_and_after_connected_read(self):
        factory = Connections([])
        with self.assertRaisesRegex(TransportError, "^cancelled$"):
            Transport(connection_factory=factory, cancelled=lambda: True).api_request("GET", "/users/settings", HEADERS)
        self.assertFalse(factory.calls)
        cancelled = [False]
        def tick():
            cancelled[0] = True
        factory = Connections([wire()], tick=tick)
        with self.assertRaisesRegex(TransportError, "^cancelled$"):
            Transport(connection_factory=factory, cancelled=lambda: cancelled[0]).api_request("GET", "/users/settings", HEADERS)
        self.assertTrue(factory.sockets[0].closed)

    def test_raw_connection_failures_are_redacted_and_not_retried(self):
        def fail():
            raise OSError("synthetic-access-secret in request")
        factory = Connections([wire()], connect_hook=fail)
        with self.assertRaisesRegex(TransportError, "^transport_failed$") as raised:
            Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS)
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertNotIn("secret", repr(raised.exception))
        self.assertEqual(len(factory.calls), 1)

    def test_connection_close_preserves_native_reader_until_body_consumed(self):
        for protocol in (b"HTTP/1.0", b"HTTP/1.1"):
            with self.subTest(protocol=protocol):
                reader, writer = socket.socketpair()
                try:
                    payload = wire(b'{"items":[1,2]}', headers=[
                        ("Content-Type", "application/json"), ("Connection", "close")])
                    writer.sendall(payload.replace(b"HTTP/1.1", protocol, 1))
                    writer.shutdown(socket.SHUT_WR)
                    class Connection(http.client.HTTPSConnection):
                        def connect(self):
                            self.sock = reader
                    result = Transport(connection_factory=Connection).api_request("GET", "/users/settings", HEADERS)
                    self.assertEqual(result.body, {"items": [1, 2]})
                    self.assertEqual(reader.fileno(), -1)
                finally:
                    reader.close()
                    writer.close()

    def test_untrusted_transport_exception_text_is_not_propagated(self):
        def fail():
            raise TransportError("synthetic-private-token")
        factory = Connections([wire()], connect_hook=fail)
        with self.assertRaisesRegex(TransportError, "^transport_failed$") as raised:
            Transport(connection_factory=factory).api_request("GET", "/users/settings", HEADERS)
        self.assertTrue(raised.exception.__suppress_context__)

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({"timeout": 0}, {"timeout": float("nan")}, {"total_timeout": 61},
                       {"max_bytes": 2}, {"max_bytes": True}, {"cancelled": None}):
            with self.assertRaisesRegex(TransportError, "^invalid_configuration$"):
                Transport(**kwargs)


class MutationTransportTests(unittest.TestCase):
    def test_post_201_json_is_parsed_with_same_tls_and_close_guards(self):
        factory = Connections([wire(b'{"added":{"movies":1}}', status=201)])
        body = {'movies': [{'ids': {'trakt': 11}}]}
        result = Transport(connection_factory=factory).mutation_request(
            'POST', '/users/me/lists/7/items', HEADERS, body)
        self.assertEqual(result.status, 201)
        self.assertEqual(result.body, {'added': {'movies': 1}})
        self.assertEqual(factory.calls[0][0], 'api.trakt.tv')
        self.assertTrue(factory.calls[0][1]['context'].check_hostname)
        self.assertTrue(factory.sockets[0].closed)
        self.assertIn(b'POST /users/me/lists/7/items HTTP/1.1', b''.join(factory.sockets[0].sent))

    def test_only_single_explicit_history_or_owned_list_post_can_connect(self):
        factory = Connections([])
        transport = Transport(connection_factory=factory)
        good = {'movies': [{'ids': {'trakt': 11}}]}
        cases = [('DELETE', '/users/me/lists/7/items', good),
                 ('POST', '/sync/history/remove', good),
                 ('POST', '/users/other/lists/7/items', good),
                 ('POST', '/users/me/lists/7/items?secret=x', good),
                 ('POST', '/users/me/lists/7/items', {'movies': good['movies'] * 2}),
                 ('POST', '/users/me/lists/7/items', dict(good, client_secret='synthetic')),
                 ('POST', '/sync/history', good)]
        for method, path, body in cases:
            with self.subTest(path=path), self.assertRaisesRegex(TransportError, '^invalid_request$'):
                transport.mutation_request(method, path, HEADERS, body)
        with self.assertRaisesRegex(TransportError, '^invalid_request$'):
            transport.api_request('POST', '/users/me/lists/7/items', HEADERS, good)
        self.assertEqual(factory.calls, [])

    def test_history_post_json_and_429_safe_header(self):
        factory = Connections([wire(b'{"added":{}}'), wire(b'private', status=429,
                              headers=[('Retry-After', '90')])])
        body = {'episodes': [{'ids': {'trakt': 11}, 'watched_at': '2026-11-12T00:00:00Z'}]}
        transport = Transport(connection_factory=factory)
        self.assertEqual(transport.mutation_request('POST', '/sync/history', HEADERS, body).body,
                         {'added': {}})
        response = transport.mutation_request('POST', '/sync/history', HEADERS, body)
        self.assertEqual(response.headers, {'retry-after': '90'})
        self.assertIsNone(response.body)
        self.assertEqual(len(factory.calls), 2)
