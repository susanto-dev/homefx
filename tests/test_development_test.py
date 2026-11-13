"""Separate Development test wiring, with fabricated responses and private temp stores."""
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'addons/script.homefx.development'
sys.path.insert(0, str(ROOT / 'addons/plugin.video.homefx'))
from test_trakt_journey_integration import FramedService

spec = importlib.util.spec_from_file_location('resources.lib.development_test',
    SOURCE / 'resources/lib/development_test.py')
development = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = development
spec.loader.exec_module(development)
CONFIG = {'schema': 1, 'environment': 'Development', 'client_id': 'synthetic-public',
          'redirect_uri': 'urn:homefx:synthetic'}


class Screen:
    def __init__(self, service):
        self.action, self.confirm, self.abort, self.cancel = 0, True, False, False
        self.service = service
        self.messages, self.prompts, self.codes = [], [], []
        self.closed = 0

    def select(self, title, labels): return self.action
    def yesno(self, title, message):
        self.prompts.append(message)
        return self.confirm
    def textviewer(self, title, text): self.messages.append(text)
    def abortRequested(self): return self.abort
    def iscanceled(self): return self.cancel
    def waitForAbort(self, seconds):
        self.service.elapsed += seconds
        return self.abort
    def create(self, title, text): self.codes.append(text)
    def update(self, percent): pass
    def close(self): self.closed += 1


class DevelopmentTestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.install = self.root / 'install'
        (self.install / 'resources').mkdir(parents=True)
        self.config_path = self.install / 'resources/development.json'
        self.config_path.write_text(json.dumps(CONFIG))
        self.profile = self.root / 'development-profile'
        self.service = FramedService(self)
        self.screen = Screen(self.service)
        self.info_calls = []
        owner = self
        class Addon:
            def getAddonInfo(self, key):
                owner.info_calls.append(key)
                return {'id': development.ADDON_ID, 'path': str(owner.install),
                        'profile': str(owner.profile)}[key]
        self.addon = Addon()
        self.network = []
        for target in ('socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('Real network forbidden'))
            self.network.append(blocker.start())
            self.addCleanup(blocker.stop)

    def tearDown(self):
        for callback in self.network:
            callback.assert_not_called()

    def factory(self, profile, config, cancelled):
        return development.assemble(profile, config, cancelled, clock=self.service.wall,
            monotonic=lambda: self.service.elapsed, connection_factory=self.service)

    def local_factory(self, profile, config):
        return development._local_runtime(profile, config, clock=self.service.wall)

    def run_action(self, action, **kwargs):
        self.screen.action = action
        return development.run(self.addon, self.screen, lambda: self.screen, self.screen,
                        lambda path: path, factory=self.factory, local_factory=self.local_factory,
                        clock=lambda: self.service.elapsed,
                        **kwargs)

    def test_cancel_denial_and_abort_do_not_access_config_profile_or_network(self):
        for action, confirm, abort in ((-1, True, False), (2, False, False), (2, True, True)):
            with self.subTest(action=action, confirm=confirm, abort=abort):
                self.screen.confirm, self.screen.abort = confirm, abort
                self.run_action(action)
                self.assertEqual(self.info_calls, [])
                self.assertFalse(self.profile.exists())
                self.assertEqual(self.service.requests, [])

    def test_missing_invalid_duplicate_or_secret_configuration_fails_before_profile(self):
        for content in ('{}', json.dumps(dict(CONFIG, client_secret='synthetic-secret')),
                        json.dumps(dict(CONFIG, environment='Production')),
                        '{"schema":1,"schema":1}', 'x' * 4097):
            with self.subTest(content_length=len(content)):
                self.config_path.write_text(content)
                self.run_action(2)
                self.assertFalse(self.profile.exists())
                self.assertEqual(self.service.requests, [])
                self.assertIn(development.FAILURE, self.screen.messages[-1])
                self.assertNotIn('synthetic-secret', self.screen.messages[-1])
        self.config_path.unlink()
        self.run_action(2)
        self.assertFalse(self.profile.exists())

    def test_configuration_reader_rejects_symlinks_and_boolean_schema(self):
        self.assertEqual(development.validate_config(CONFIG), CONFIG)
        with self.assertRaises(development.DevelopmentError):
            development.validate_config(dict(CONFIG, schema=True))
        link = self.root / 'link.json'
        link.symlink_to(self.config_path)
        with self.assertRaises(development.DevelopmentError):
            development.load_config(link)
        directory_link = self.root / 'alias'
        directory_link.symlink_to(self.install, target_is_directory=True)
        with self.assertRaises(development.DevelopmentError):
            development.load_config(directory_link / 'resources/development.json')

    def test_private_scope_changes_with_public_identity_and_rejects_unsafe_paths(self):
        first = development.scoped_profile(self.profile, CONFIG)
        second = development.scoped_profile(self.profile, dict(CONFIG, client_id='other-synthetic'))
        third = development.scoped_profile(self.profile, dict(CONFIG, redirect_uri='urn:other:synthetic'))
        self.assertEqual(first, development.scoped_profile(self.profile, dict(CONFIG)))
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(first.parent, self.profile)
        self.assertNotIn(CONFIG['client_id'], first.name)
        with self.assertRaises(Exception):
            development.scoped_profile('relative', CONFIG)
        first.mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        (first / 'trakt').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(Exception):
            development.scoped_profile(self.profile, CONFIG)
        self.assertEqual(list(outside.iterdir()), [])

    def test_storage_gate_prevents_credential_store_and_live_request(self):
        self.run_action(2, probe=lambda path: 'Overall: not passed\nTemporary cleanup: passed')
        self.assertEqual(self.screen.messages[-1], 'Overall: not passed\nTemporary cleanup: passed')
        self.assertEqual(self.service.requests, [])
        self.assertFalse(self.profile.exists())
        self.run_action(3, probe=lambda path: 'Overall: not passed')
        self.assertFalse(self.profile.exists())

    def test_storage_only_creates_no_credentials_or_network(self):
        self.run_action(0)
        self.assertIn('Overall: passed', self.screen.messages[-1])
        self.assertFalse(list(self.profile.rglob('*.sqlite3')))
        self.assertEqual(self.service.requests, [])

    def test_login_restart_refresh_and_disconnect_use_only_oauth(self):
        self.run_action(2)
        self.assertIn('Connection test: authorized.', self.screen.messages[-1])
        self.assertTrue(any('SYNTHETIC-CODE' in code for code in self.screen.codes))
        self.assertFalse(any('SYNTHETIC-CODE' in message for message in self.screen.messages))
        before = len(self.service.requests)
        self.run_action(1)
        self.assertIn('Local status: credentials stored', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before)
        self.run_action(3)
        self.assertIn('Refresh rotation: passed', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before + 1)
        self.assertEqual(self.service.requests[-1][2], '/oauth/token')
        self.run_action(4)
        self.assertIn('Connection test: disconnected', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before + 1)
        self.run_action(1)
        self.assertIn('Local status: disconnected', self.screen.messages[-1])
        self.assertTrue(all(host == 'auth.trakt.tv' and method == 'POST'
                            for host, method, _, _ in self.service.requests))
        for message in self.screen.messages:
            self.assertNotIn(str(self.profile), message)
            self.assertNotIn('synthetic-access', message)
            self.assertNotIn('synthetic-refresh', message)
        self.assertTrue(all(socket.closed for socket in self.service.sockets))

    def test_changed_configuration_does_not_reuse_old_test_credentials(self):
        self.run_action(2)
        self.config_path.write_text(json.dumps(dict(CONFIG, client_id='other-synthetic')))
        before = len(self.service.requests)
        self.run_action(1)
        self.assertIn('Local status: disconnected', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before)
        self.config_path.write_text(json.dumps(CONFIG))
        self.run_action(1)
        self.assertIn('Local status: credentials stored', self.screen.messages[-1])

    def test_cancelled_login_stores_no_tokens_and_discloses_no_codes_in_result(self):
        self.screen.cancel = True
        self.run_action(2)
        self.assertIn('Connection test: cancelled', self.screen.messages[-1])
        self.run_action(1)
        self.assertIn('Local status: disconnected', self.screen.messages[-1])
        self.assertNotIn('SYNTHETIC-CODE', self.screen.messages[-1])

    def test_failed_refresh_requires_login_and_never_retries(self):
        self.run_action(2)
        self.service.hook = lambda host, method, path: (500, {}) if path == '/oauth/token' else None
        before = len(self.service.requests)
        self.run_action(3)
        self.assertIn('failed refresh may require login again', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before + 1)
        self.run_action(1)
        self.assertIn('Local status: login required', self.screen.messages[-1])
        self.run_action(3)
        self.assertIn('Refresh not run', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before + 1)

    def test_too_short_rotated_token_is_not_a_pass_and_requires_login(self):
        self.run_action(2)
        self.service.hook = lambda host, method, path: (200, {
            'access_token': 'synthetic-short-access', 'refresh_token': 'synthetic-short-refresh',
            'token_type': 'bearer', 'created_at': self.service.wall(), 'expires_in': 10,
        }) if path == '/oauth/token' else None
        before = len(self.service.requests)
        self.run_action(3)
        self.assertIn('Refresh not completed', self.screen.messages[-1])
        self.assertNotIn('Refresh rotation: passed', self.screen.messages[-1])
        self.assertEqual(len(self.service.requests), before + 1)
        self.run_action(1)
        self.assertIn('Local status: disconnected', self.screen.messages[-1])

    def test_concurrent_replacement_after_rotation_is_not_a_pass_or_erased(self):
        self.run_action(2)
        actual_factory = self.factory
        seen = []
        def reentrant_factory(profile, config, cancelled):
            runtime = actual_factory(profile, config, cancelled)
            original_status = runtime.session.status
            calls = 0
            def status():
                nonlocal calls
                calls += 1
                if calls == 2:
                    current = runtime.store.snapshot()
                    runtime.store.disconnect(expected_generation=current.generation)
                    from resources.lib.trakt_auth import TokenSet
                    runtime.store.install(TokenSet('synthetic-new-access', 'synthetic-new-refresh',
                                                  self.service.wall() + 3600),
                                          expected_generation=current.generation + 1)
                result = original_status()
                seen.append(result)
                return result
            runtime.session.status = status
            return runtime
        self.factory = reentrant_factory
        self.run_action(3)
        self.assertIn('Refresh not completed', self.screen.messages[-1])
        self.assertGreater(seen[-1]['generation'], seen[0]['generation'] + 1)
        self.factory = actual_factory
        self.run_action(1)
        self.assertIn('Local status: credentials stored', self.screen.messages[-1])

    def test_refresh_cleanup_failure_replaces_success_with_fixed_outcome(self):
        self.run_action(2)
        with patch.object(self.screen, 'close', side_effect=RuntimeError('private-token-path')):
            self.assertTrue(self.run_action(3))
        self.assertEqual(self.screen.messages[-1], development.CLEANUP_FAILURE)
        self.assertNotIn('passed', self.screen.messages[-1])
        self.assertNotIn('private-token-path', self.screen.messages[-1])

    def test_ui_cleanup_failure_replaces_local_status(self):
        with patch.object(development.TestUI, 'close', side_effect=RuntimeError('private-token-path')):
            self.assertTrue(self.run_action(1))
        self.assertEqual(self.screen.messages[-1], development.CLEANUP_FAILURE)

    def test_cancelled_refresh_cleanup_failure_is_not_silent(self):
        self.screen.cancel = True
        with patch.object(self.screen, 'close', side_effect=RuntimeError('private-token-path')):
            self.assertTrue(self.run_action(3))
        self.assertEqual(self.screen.messages[-1], development.CLEANUP_FAILURE)
        self.assertEqual(self.service.requests, [])

    def test_result_viewer_failure_returns_false_without_private_exception(self):
        with patch.object(self.screen, 'textviewer', side_effect=RuntimeError('private-token-path')):
            self.assertFalse(self.run_action(1))
            self.assertFalse(self.run_action(0))

    def test_entry_fallback_delivery_status_and_redaction(self):
        def unavailable(): raise RuntimeError('private-token-path')
        modules = {name: types.SimpleNamespace(**members) for name, members in {
            'xbmc': {'Monitor': unavailable}, 'xbmcaddon': {'Addon': unavailable},
            'xbmcgui': {'Dialog': lambda: self.screen, 'DialogProgress': unavailable},
            'xbmcvfs': {'translatePath': unavailable}}.items()}
        with patch.dict(sys.modules, modules):
            entry = runpy.run_path(str(SOURCE / 'default.py'), run_name='development_entry_fixture')
            self.assertTrue(entry['main']())
            self.assertEqual(self.screen.messages[-1], 'Test unavailable. No success is established.')
            with patch.object(self.screen, 'textviewer', side_effect=RuntimeError('private-token-path')):
                self.assertFalse(entry['main']())

    def test_entry_import_does_not_open_ui_or_touch_addon(self):
        def forbidden(*args, **kwargs): self.fail('Import must not invoke Kodi')
        modules = {name: types.SimpleNamespace(**members) for name, members in {
            'xbmc': {'Monitor': forbidden}, 'xbmcaddon': {'Addon': forbidden},
            'xbmcgui': {'Dialog': forbidden, 'DialogProgress': forbidden},
            'xbmcvfs': {'translatePath': forbidden}}.items()}
        with patch.dict(sys.modules, modules):
            runpy.run_path(str(SOURCE / 'default.py'), run_name='development_entry_fixture')


    def test_current_activation_url_works_through_actual_assembly(self):
        def response(host, method, path):
            if path == '/oauth/device/code':
                return 200, {'device_code': 'synthetic-device-code', 'user_code': 'SYNTHETIC-CODE',
                             'verification_url': 'https://auth.trakt.tv/activate',
                             'interval': 5, 'expires_in': 600}
        self.service.hook = response
        self.run_action(2)
        self.assertIn('Connection test: authorized', self.screen.messages[-1])
        self.assertIn('https://auth.trakt.tv/activate', self.screen.codes[0])
        self.assertNotIn('SYNTHETIC-CODE', self.screen.messages[-1])
        self.assertEqual([request[2] for request in self.service.requests],
                         ['/oauth/device/code', '/oauth/device/token'])

    def test_non_success_device_response_has_fixed_diagnostics_and_no_retry(self):
        self.service.hook = lambda *args: (403, {'error': 'PRIVATE-BODY-CODE-TOKEN'})
        self.run_action(2)
        result = self.screen.messages[-1]
        self.assertIn('Connection test: failed', result)
        self.assertIn('Last stage: device response validation', result)
        self.assertIn('Category: request status rejected', result)
        self.assertIn('Response status: 403', result)
        self.assertNotIn('PRIVATE', result)
        self.assertNotIn('Authorization does not validate', result)
        self.assertEqual(len(self.service.requests), 1)
        self.assertEqual(self.screen.codes, [])

    def test_malformed_successful_response_is_not_authorization(self):
        self.service.hook = lambda *args: (200, {'private': 'PRIVATE-BODY'})
        self.run_action(2)
        result = self.screen.messages[-1]
        self.assertIn('Last stage: device response validation', result)
        self.assertIn('Response status: 200', result)
        self.assertIn('No successful authorization', result)
        self.assertEqual(len(self.service.requests), 1)
        self.assertEqual(self.screen.codes, [])
        self.assertNotIn('PRIVATE', result)

    def test_transport_categories_are_allowlisted_and_do_not_echo_exceptions(self):
        for category in ('timeout', 'invalid_json', 'redirect_refused', 'transport_failed',
                         'PRIVATE-TOKEN-PATH'):
            with self.subTest(category=category):
                with patch.object(development.trakt_transport.Transport, 'oauth_request',
                                  side_effect=development.trakt_transport.TransportError(category)) as request:
                    self.run_action(2)
                request.assert_called_once()
                result = self.screen.messages[-1]
                self.assertIn('Last stage: device code request', result)
                self.assertIn('Response status: unavailable', result)
                self.assertNotIn('PRIVATE', result)
                self.assertNotIn('SYNTHETIC-CODE', result)
                expected = development.LoginDiagnostics.CATEGORIES.get(category, 'unavailable')
                self.assertIn('Category: ' + expected, result)
        self.assertEqual(self.service.requests, [])

    def test_local_account_failure_is_not_reported_as_a_network_failure(self):
        with patch.object(development.trakt_tokens.TokenStore, 'disconnect',
                          side_effect=OSError('PRIVATE-PATH')):
            self.run_action(2)
        result = self.screen.messages[-1]
        self.assertIn('Last stage: local account preparation', result)
        self.assertIn('Response status: unavailable', result)
        self.assertNotIn('PRIVATE', result)
        self.assertEqual(self.service.requests, [])

    def test_code_dialog_failure_is_distinct_and_redacted(self):
        with patch.object(self.screen, 'create', side_effect=RuntimeError('PRIVATE-CODE-TOKEN')):
            self.run_action(2)
        result = self.screen.messages[-1]
        self.assertIn('Last stage: authorization dialog', result)
        self.assertIn('Category: code display unavailable', result)
        self.assertNotIn('PRIVATE', result)
        self.assertNotIn('SYNTHETIC-CODE', result)
        self.assertEqual(len(self.service.requests), 1)

    def test_cancel_after_code_dialog_is_cancelled_without_poll_or_diagnostics(self):
        def create(title, text):
            self.screen.codes.append(text)
            self.screen.cancel = True
        with patch.object(self.screen, 'create', side_effect=create):
            self.run_action(2)
        result = self.screen.messages[-1]
        self.assertIn('Connection test: cancelled', result)
        self.assertNotIn('Last stage:', result)
        self.assertNotIn('SYNTHETIC-CODE', result)
        self.assertEqual(len(self.service.requests), 1)
        self.run_action(1)
        self.assertIn('Local status: disconnected', self.screen.messages[-1])


if __name__ == '__main__':
    unittest.main()
