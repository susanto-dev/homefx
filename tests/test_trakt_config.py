"""Public configuration preflight uses fabricated values and performs no service work."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import socket
import sqlite3
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("trakt_config_check", ROOT / "tools/check_trakt_config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class TraktConfigurationTests(unittest.TestCase):
    def environment(self, **changes):
        result = {"HOMEFX_TRAKT_ENVIRONMENT": "Development",
                  "TRAKT_CLIENT_ID": "synthetic-public-client",
                  "TRAKT_REDIRECT_URI": "urn:homefx:synthetic-callback"}
        result.update(changes)
        return result

    def output(self, environment):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = config.main(environment)
        return result, stream.getvalue()

    def test_both_environments_use_public_syntax_without_service_or_profile_access(self):
        with patch.object(config.service_runtime, 'build_trakt', side_effect=AssertionError('No assembly')), \
                patch.object(socket, 'create_connection', side_effect=AssertionError('No network')), \
                patch.object(sqlite3, 'connect', side_effect=AssertionError('No storage')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('No output')):
            for selected in ('Development', 'Production'):
                with self.subTest(environment=selected):
                    environment = self.environment(HOMEFX_TRAKT_ENVIRONMENT=selected)
                    status, text = self.output(environment)
                    self.assertEqual(status, 0)
                    self.assertIn('syntax passed', text)
                    self.assertIn('live activation are not verified', text)
                    self.assertNotIn(environment['TRAKT_CLIENT_ID'], text)
                    self.assertNotIn(environment['TRAKT_REDIRECT_URI'], text)

    def test_required_inputs_do_not_fall_back_to_app_mode_or_guessed_redirect(self):
        for key in self.environment():
            with self.subTest(missing=key):
                environment = self.environment(TRAKT_APP_MODE='Development')
                del environment[key]
                status, text = self.output(environment)
                self.assertEqual(status, 1)
                self.assertIn('configuration check failed', text)
        for selected in ('development', 'production', 'github-pages', '', None, True):
            with self.subTest(selected=selected):
                self.assertEqual(self.output(self.environment(HOMEFX_TRAKT_ENVIRONMENT=selected))[0], 1)

    def test_client_id_uses_runtime_bounds_without_assuming_hex_format(self):
        for value in ('synthetic-public-client', 'a' * 256):
            with self.subTest(valid=value[:20]):
                self.assertEqual(self.output(self.environment(TRAKT_CLIENT_ID=value))[0], 0)
        for value in ('', 'a' * 257, None, 123, 'two words', 'line\nbreak', 'a\x00b'):
            with self.subTest(invalid=type(value).__name__):
                self.assertEqual(self.output(self.environment(TRAKT_CLIENT_ID=value))[0], 1)

    def test_redirect_contract_accepts_explicit_registered_uri_forms_without_opening(self):
        for value in ('urn:homefx:synthetic-callback', 'homefx://callback',
                      'https://example.invalid/callback', 'http://localhost:8000/callback'):
            with self.subTest(valid=value):
                self.assertEqual(self.output(self.environment(TRAKT_REDIRECT_URI=value))[0], 0)
        for value in ('', None, 'callback', 'https://', 'https://user@example.invalid/callback',
                      'https://example.invalid/#fragment', 'https://example.invalid/%zz',
                      'https://example.invalid:abc/callback', 'urn:callback\\bad',
                      'urn:callback with space', 'urn:callback\nnewline', 'a' * 2049):
            with self.subTest(invalid=repr(value)):
                self.assertEqual(self.output(self.environment(TRAKT_REDIRECT_URI=value))[0], 1)

    def test_diagnostics_never_emit_values_or_workflow_commands(self):
        marker = 'sensitive-fixture\n::error::injected'
        for key, category in [('HOMEFX_TRAKT_ENVIRONMENT', 'invalid_environment'),
                              ('TRAKT_CLIENT_ID', 'invalid_public_client_id'),
                              ('TRAKT_REDIRECT_URI', 'invalid_redirect_uri')]:
            with self.subTest(key=key):
                status, text = self.output(self.environment(**{key: marker}))
                self.assertEqual(status, 1)
                self.assertEqual(text, 'Public Trakt configuration check failed: ' + category + '.\n')
                self.assertNotIn('sensitive-fixture', text)
                self.assertNotIn('::error::', text)

    def test_ambient_secret_and_legacy_mode_do_not_replace_required_public_configuration(self):
        environment = self.environment(TRAKT_CLIENT_SECRET='unused-secret-fixture',
                                       TRAKT_APP_MODE='Production')
        status, text = self.output(environment)
        self.assertEqual(status, 0)
        self.assertNotIn('unused-secret-fixture', text)
        del environment['TRAKT_CLIENT_ID']
        self.assertEqual(self.output(environment)[0], 1)

    def test_main_reads_only_supplied_environment_when_explicit(self):
        with patch.dict(config.os.environ, self.environment(), clear=True):
            self.assertEqual(self.output({})[0], 1)
            stream = io.StringIO()
            with redirect_stdout(stream):
                self.assertEqual(config.main(), 0)
            self.assertIn('syntax passed', stream.getvalue())


if __name__ == '__main__':
    unittest.main()
