"""Capability reporting uses injected local probes and never renders private input."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib import readiness


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.context = types.SimpleNamespace(
            verify_mode=2, check_hostname=True,
            cert_store_stats=lambda: {'x509_ca': 42, 'private': '/private/profile'})
        self.modules = {
            'sqlite3': types.SimpleNamespace(sqlite_version_info=(3, 45, 1)),
            'ssl': types.SimpleNamespace(OPENSSL_VERSION_INFO=(3, 0, 1, 0, 0),
                                         CERT_REQUIRED=2,
                                         create_default_context=lambda: self.context)}

    def report(self, **kwargs):
        params = dict(importer=self.modules.__getitem__, python_version=(3, 12, 2),
                      os_name='posix', private_file_mode=True)
        params.update(kwargs)
        return readiness.report(lambda: '0.4.0', lambda: '21.2 (21.2.0) Git:private',
                                lambda: '6.7.8', **params)

    def test_numeric_capabilities_and_explicit_limits(self):
        with patch('socket.create_connection', side_effect=AssertionError('network forbidden')):
            report = self.report()
        for text in ('HomeFX: 0.4.0', 'Kodi: 21.2', 'Python: 3.12.2',
                     'SQLite version: 3.45.1', 'OpenSSL version: 3.0.1',
                     'Trusted CA count: 42', 'prerequisites: available',
                     'handoff untested', 'No network, login, service or playback tests',
                     'does not establish TV compatibility'):
            self.assertIn(text, report)
        self.assertNotIn('private', report.replace('private-store', ''))
        self.assertLessEqual(len(report), readiness.MAX_REPORT_LENGTH)

    def test_missing_optional_modules_and_provider_are_safe(self):
        def missing(*args):
            raise ImportError('/private/account/secret')
        report = readiness.report(missing, missing, missing, importer=missing,
                                 os_name='nt', private_file_mode=False)
        self.assertIn('SQLite version: unavailable', report)
        self.assertIn('Verified default TLS context: unavailable', report)
        self.assertIn('Umbrella version: unavailable; handoff untested', report)
        self.assertIn('prerequisites: unavailable', report)
        self.assertNotIn('/private', report)

    def test_arbitrary_and_oversized_versions_are_never_echoed(self):
        for value in ('/private/secret', 'token-123', '127.0.0.1', '2.3\nsecret',
                      '2.3' + 'x' * 10000, None, True, {'token': 'secret'}):
            with self.subTest(value=type(value).__name__):
                report = readiness.report(lambda: value, lambda: value, lambda: value,
                                          importer=self.modules.__getitem__)
                self.assertIn('HomeFX: unavailable', report)
                self.assertNotIn('secret', report)
        report = readiness.report(lambda: '2.3 (/private/secret)', lambda: '21.2-private',
                                  lambda: '1.2+private', importer=self.modules.__getitem__)
        self.assertNotIn('/private', report)
        self.assertNotIn('+private', report)
        self.assertNotIn('-private', report)

    def test_unverified_context_and_invalid_numeric_fields_fail_closed(self):
        self.context.check_hostname = False
        self.modules['ssl'].OPENSSL_VERSION_INFO = ('secret', 0, 1)
        self.modules['sqlite3'].sqlite_version_info = (True, 2, 3)
        report = self.report(python_version=(3, 'secret', 1))
        self.assertIn('Verified default TLS context: unavailable', report)
        self.assertIn('Trusted CA count: unavailable', report)
        self.assertIn('OpenSSL version: unavailable', report)
        self.assertIn('SQLite version: unavailable', report)
        self.assertIn('Python: unavailable', report)
        self.assertNotIn('secret', report)

    def test_context_creation_failure_does_not_disclose_exception(self):
        def fail():
            raise OSError('/private/secret')
        self.modules['ssl'].create_default_context = fail
        report = self.report()
        self.assertIn('Verified default TLS context: unavailable', report)
        self.assertNotIn('secret', report)

    def test_invalid_ca_counts_do_not_render(self):
        for value in (True, -1, 100001, 'private'):
            self.context.cert_store_stats = lambda: {'x509_ca': value}
            self.assertIn('Trusted CA count: unavailable', self.report())


if __name__ == '__main__':
    unittest.main()
