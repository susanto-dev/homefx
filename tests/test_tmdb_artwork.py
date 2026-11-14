"""Fabricated TMDB wire responses; never access an account or real artwork."""
import json
import time
from email.utils import formatdate
from pathlib import Path
import ssl
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.tmdb_artwork import Client, Artwork, ArtworkError
from resources.lib.trakt_views import browse_list
from test_trakt_transport import Connections, wire


class ArtworkTests(unittest.TestCase):
    def test_fixed_host_bearer_headers_id_match_and_only_paths_retained(self):
        factory = Connections([wire(json.dumps({'id': 7, 'poster_path': '/FakePoster.jpg',
            'backdrop_path': '/FakeBackdrop.png', 'overview': 'not persisted',
            'account': 'not persisted'}).encode())])
        client = Client('synthetic-application-token', connection_factory=factory)
        self.assertEqual(client.fetch(('show', 7, 'en-US')), Artwork('/FakePoster.jpg', '/FakeBackdrop.png'))
        self.assertEqual(factory.calls[0][0], 'api.themoviedb.org')
        context = factory.calls[0][1]['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        sent = b''.join(factory.sockets[0].sent)
        self.assertTrue(sent.startswith(b'GET /3/tv/7?language=en-US HTTP/1.1\r\n'))
        self.assertIn(b'Authorization: Bearer synthetic-application-token\r\n', sent)
        self.assertNotIn(b'api_key=', sent)
        self.assertNotIn('synthetic', repr(client))
        self.assertNotIn('FakePoster', repr(Artwork('/FakePoster.jpg')))
        self.assertTrue(factory.sockets[0].closed)

    def test_bad_identity_or_image_path_is_not_a_successful_negative_result(self):
        for body in ({'id': 8, 'poster_path': None, 'backdrop_path': None},
                     {'id': True, 'poster_path': None, 'backdrop_path': None},
                     {'id': 7}, {'id': 7, 'poster_path': 'https://other.invalid/a.jpg', 'backdrop_path': None},
                     {'id': 7, 'poster_path': '/../a.jpg', 'backdrop_path': None},
                     {'id': 7, 'poster_path': '/a.jpg?secret=value', 'backdrop_path': None}):
            client = Client('synthetic-application-token', connection_factory=Connections([wire(json.dumps(body).encode())]))
            with self.assertRaisesRegex(ArtworkError, '^unavailable$'):
                client.fetch(('movie', 7, 'en-US'))

    def test_status_mapping_and_no_redirects_or_error_body_exposure(self):
        for status, category in ((401, 'unauthorized'), (403, 'unauthorized'),
                                 (429, 'limited'), (500, 'unavailable'), (302, 'unavailable')):
            factory = Connections([wire(b'private-response', status=status,
                headers=[('Content-Type', 'application/json'), ('Retry-After', '120'), ('Location', 'https://other.invalid/')])])
            client = Client('synthetic-application-token', connection_factory=factory)
            with self.assertRaises(ArtworkError) as caught:
                client.fetch(('movie', 7, 'en-US'))
            self.assertEqual(caught.exception.category, category)
            self.assertNotIn('private', repr(caught.exception))
            if status == 429:
                self.assertEqual(caught.exception.wait, 120)
            self.assertEqual(len(factory.calls), 1)
        client = Client('synthetic-application-token', connection_factory=Connections([wire(status=404)]))
        self.assertEqual(client.fetch(('movie', 7, 'en-US')), Artwork())

    def test_retry_after_http_date_preserves_long_cooldown(self):
        stamp = formatdate(time.time() + 86400, usegmt=True)
        factory = Connections([wire(status=429, headers=[('Retry-After', stamp)])])
        with self.assertRaises(ArtworkError) as caught:
            Client('synthetic-application-token', connection_factory=factory).fetch(('movie', 7, 'en-US'))
        self.assertGreater(caught.exception.wait, 86000)
        self.assertLessEqual(caught.exception.wait, 86400)

    def test_invalid_requests_and_cancellation_never_connect(self):
        factory = Connections([])
        client = Client('synthetic-application-token', connection_factory=factory)
        for lookup in (('person', 1, 'en-US'), ('movie', True, 'en-US'), ('movie', 1, '../'),
                       ('movie', 1), ('movie', 2**63, 'en-US'), None):
            with self.assertRaises(ArtworkError):
                client.fetch(lookup)
        with self.assertRaisesRegex(ArtworkError, 'cancelled'):
            Client('synthetic-application-token', cancelled=lambda: True,
                   connection_factory=factory).fetch(('movie', 1, 'en-US'))
        self.assertEqual(factory.calls, [])

    def test_optional_tmdb_identity_never_replaces_trakt_or_title_matching(self):
        for tmdb in (7, None, '7', True, -1, 2**63):
            row = browse_list([{'type': 'movie', 'movie': {'title': 'Synthetic',
                    'ids': {'trakt': 123, 'tmdb': tmdb}}}])['items'][0]
            self.assertEqual(row['trakt_id'], 123)
            self.assertFalse(row['playable'])
            self.assertEqual(row.get('tmdb_id'), 7 if type(tmdb) is int and tmdb == 7 else None)
