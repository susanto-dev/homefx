"""Fabricated Real-Debrid contracts; no service calls or account secrets."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.debrid_client import Client, DebridError, Response, validate_url


def download(ident='1', url='https://cdn.example.invalid/private-file'):
    return {'id': ident, 'filename': 'Invented video.mp4', 'filesize': 123,
            'download': url}


class DebridClientTests(unittest.TestCase):
    def test_minimal_account_and_redaction(self):
        calls = []
        def request(*args):
            calls.append(args)
            return Response(200, body={'type': 'premium', 'premium': 500,
                'expiration': '2026-12-01T00:00:00Z', 'username': 'private-name',
                'email': 'private@example.invalid'})
        client = Client(request, 'fabricated-token')
        account = client.account()
        self.assertEqual(account.type, 'premium')
        self.assertEqual(account.premium_seconds, 500)
        self.assertFalse(hasattr(account, 'email'))
        self.assertEqual(calls[0], ('GET', '/rest/1.0/user',
                                   {'Authorization': 'Bearer fabricated-token'}, None))
        self.assertNotIn('fabricated-token', repr(client))
        self.assertNotIn('private-name', repr(account))

    def test_account_bad_entitlement_and_expiry(self):
        for changes in ({'type': []}, {'premium': True}, {'premium': -1},
                        {'expiration': '2026-01-01'}, {'expiration': 'bad'}):
            body = {'type': 'free', 'premium': 0, 'expiration': '2026-01-01T00:00:00Z'}
            body.update(changes)
            with self.subTest(changes=changes), self.assertRaises(DebridError):
                Client(lambda *a: Response(200, body=body), 'token').account()

    def test_downloads_pagination_and_private_fields(self):
        responses = [Response(200, {'X-Total-Count': '3'}, [download('1'), download('2')]),
                     Response(200, {'X-Total-Count': '3'}, [download('3')])]
        calls = []
        def request(*args):
            calls.append(args)
            return responses.pop(0)
        rows = Client(request, 'token', page_size=2).downloads()
        self.assertEqual([row.id for row in rows], ['1', '2', '3'])
        self.assertEqual(calls[1][1], '/rest/1.0/downloads?page=2&limit=2')
        self.assertNotIn('private-file', repr(rows))
        self.assertNotIn('Invented', repr(rows))
        self.assertEqual(Client(lambda *a: Response(200, {'X-Total-Count': '0'}, []),
                                'token').downloads(), ())

    def test_downloads_reject_missing_truncated_changing_and_duplicate_pages(self):
        cases = [
            [Response(200, {}, [])],
            [Response(200, {'X-Total-Count': '2'}, [download()])],
            [Response(200, {'X-Total-Count': '3'}, [download('1'), download('2')]),
             Response(200, {'X-Total-Count': '4'}, [download('3'), download('4')])],
            [Response(200, {'X-Total-Count': '3'}, [download('1'), download('2')]),
             Response(200, {'X-Total-Count': '3'}, [download('2')])],
            [Response(200, {'X-Total-Count': True}, [])],
            [Response(200, {'X-Total-Count': '99999999'}, [])],
        ]
        for responses in cases:
            with self.subTest(responses=responses), self.assertRaises(DebridError):
                Client(lambda *a: responses.pop(0), 'token', page_size=2).downloads()

    def test_single_explicit_unrestrict_form_and_redacted_result(self):
        calls = []
        def request(*args):
            calls.append(args)
            return Response(200, body=download())
        row = Client(request, 'token').unrestrict('https://host.example.invalid/authorized')
        self.assertEqual(row.url, download()['download'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ('POST', '/rest/1.0/unrestrict/link',
            {'Authorization': 'Bearer token', 'Content-Type': 'application/x-www-form-urlencoded'},
            {'link': 'https://host.example.invalid/authorized'}))
        self.assertNotIn(row.url, repr(row))

    def test_no_replay_when_post_response_is_lost_or_unusable(self):
        for response in (TimeoutError('sensitive-url'), Response(503, body={'error': 'sensitive-url'}),
                         Response(200, body=[]), Response(200, body={'download': 'http://127.0.0.1'}),
                         Response(200, body=dict(download(), alternative=[download('2')]))):
            calls = []
            def request(*args):
                calls.append(args)
                if isinstance(response, Exception):
                    raise response
                return response
            with self.subTest(response=response), self.assertRaises(DebridError) as caught:
                Client(request, 'token').unrestrict('https://host.example.invalid/file')
            self.assertEqual(caught.exception.kind, 'uncertain')
            self.assertNotIn('sensitive-url', str(caught.exception))
            self.assertEqual(len(calls), 1)

    def test_error_status_and_rate_delay_no_retry(self):
        for status, kind in ((401, 'reauthenticate'), (403, 'permission'),
                             (404, 'service'), (429, 'rate_limit')):
            calls = []
            def request(*args):
                calls.append(args)
                return Response(status, {'Retry-After': '99999'}, {'error': 'private-body'})
            with self.subTest(status=status), self.assertRaises(DebridError) as caught:
                Client(request, 'token').account()
            self.assertEqual(caught.exception.kind, kind)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('private-body', str(caught.exception))
            if status == 429:
                self.assertEqual(caught.exception.retry_after, 3600)

    def test_invalid_urls_never_reach_request(self):
        calls = []
        client = Client(lambda *a: calls.append(a), 'token')
        invalid = ['http://host.example/file', 'plugin://video/', 'file:///tmp/file',
                   'https://user:secret@host.example/file', 'https://localhost/file',
                   'https://localhost.local/file', 'https://127.0.0.1/file',
                   'https://[::1]/file', 'https://10.0.0.1/file', 'https://169.254.169.254/file',
                   'https://2130706433/file', 'https://127.1/file', 'https://0x7f.0.0.1/file', 'https://host.example:8443/file',
                   'https://host.example/file|Cookie=secret', 'https://host.example/%7CCookie=x',
                   'https://host.example/%250aHeader:x', 'https://host.example/a\\b',
                   'https://host.example/file#fragment', 'https://host.example/a\n',
                   'https://host.example./file', 'https://host.%65xample/file', None, {}, 'x' * 8193]
        for link in invalid:
            with self.subTest(link=link), self.assertRaises(DebridError):
                client.unrestrict(link)
        self.assertEqual(calls, [])
        self.assertEqual(validate_url('https://host.example.invalid/a?key=secret'),
                         'https://host.example.invalid/a?key=secret')

    def test_response_and_bounds_validation(self):
        for changes in ({'page_size': True}, {'max_pages': 0}, {'max_items': 10001}):
            with self.subTest(changes=changes), self.assertRaises(DebridError):
                Client(None, 'token', **changes)
        for response in (None, Response(True), Response(200, {'X': '1', 'x': '2'})):
            with self.subTest(response=response), self.assertRaises(DebridError):
                Client(lambda *a: response, 'token').account()
        for token in ('bad token', 'bad\nheader', '', None):
            with self.subTest(token=token), self.assertRaises(DebridError):
                Client(None, token)
