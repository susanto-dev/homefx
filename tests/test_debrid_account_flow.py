"""Provider account interaction through real sessions/stores; no service traffic."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.account_flow import AccountFlow, FlowResult
from resources.lib.debrid_auth import Credentials, Tokens, VERIFY_URL
from resources.lib.debrid_client import Response
from resources.lib.debrid_session import Session
from resources.lib.debrid_store import CredentialStore


class UI:
    def __init__(self):
        self.codes, self.closed = [], 0
        self.replace = self.disconnect = True
        self.show_hook = self.close_hook = None

    def confirm_replace(self):
        return self.replace

    def confirm_disconnect(self):
        return self.disconnect

    def show_code(self, code, url):
        self.codes.append((code, url))
        if self.show_hook:
            self.show_hook()

    def close(self):
        self.closed += 1
        if self.close_hook:
            self.close_hook()


class ProviderFlowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tick, self.cancel = 0, False
        self.calls, self.waits = [], []
        self.expires, self.credential_responses = 60, []
        self.credentials_hook = self.token_hook = None
        self.store = CredentialStore(directory.name, clock=lambda: 1000)
        self.bound = Credentials('synthetic-bound', 'synthetic-user-secret')
        self.ui = UI()
        self.session = Session(self.store, self.oauth, self.no_api, 'synthetic-public',
                               clock=lambda: 1000, monotonic=lambda: self.tick)
        self.flow = AccountFlow(self.session, self.ui, self.wait,
                                lambda: self.cancel, lambda: self.tick, self.session.disconnect)

    def no_api(self, *args):
        self.fail('Authorization must not imply an account/entitlement request')

    def oauth(self, method, path, body):
        self.calls.append((method, path, self.tick))
        if path.endswith('/device/code'):
            return Response(200, body=dict(device_code='synthetic-device', user_code='DEMO',
                interval=5, expires_in=self.expires, verification_url=VERIFY_URL))
        if path.endswith('/device/credentials'):
            if self.credentials_hook:
                self.credentials_hook()
            if self.credential_responses:
                return self.credential_responses.pop(0)
            return Response(200, body=dict(client_id=self.bound.client_id,
                                           client_secret=self.bound.client_secret))
        if self.token_hook:
            self.token_hook()
        return Response(200, body=dict(access_token='synthetic-access',
            refresh_token='synthetic-refresh', token_type='Bearer', expires_in=3600))

    def wait(self, seconds):
        self.waits.append(seconds)
        self.tick += seconds
        return False

    def install(self):
        self.store.install(self.bound, Tokens('synthetic-replacement', 'synthetic-refresh-new', 5000))

    def test_authorized_stores_user_bound_grant_without_entitlement_or_read_calls(self):
        self.assertEqual(self.flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(self.store.snapshot().credentials, self.bound)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-access')
        self.assertEqual([(path, tick) for _, path, tick in self.calls], [
            ('/oauth/v2/device/code', 0), ('/oauth/v2/device/credentials', 5), ('/oauth/v2/token', 5)])
        self.assertEqual(self.ui.codes, [('DEMO', VERIFY_URL)])
        self.assertEqual(self.ui.closed, 1)
        self.assertTrue(all(0 < delay <= 1 for delay in self.waits))
        self.assertNotIn('synthetic', repr(self.flow))
        self.assertEqual(self.session.status()['login'], 'idle')

    def test_pending_requires_explicit_classifier_and_respects_poll_interval(self):
        self.session = Session(self.store, self.oauth, self.no_api, 'synthetic-public',
            clock=lambda: 1000, monotonic=lambda: self.tick,
            pending_response=lambda response: response.body == {'fixture_pending': True})
        self.flow.session = self.session
        self.flow.disconnect_callback = self.session.disconnect
        self.credential_responses = [Response(403, body={'fixture_pending': True})]
        self.assertEqual(self.flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual([tick for _, path, tick in self.calls if path.endswith('/credentials')], [5, 10])

    def test_unknown_refusal_is_failed_not_guessed_pending_or_denied(self):
        for status in (400, 403, 429, 500):
            with self.subTest(status=status):
                before = len(self.calls)
                self.credential_responses = [Response(status)]
                self.assertEqual(self.flow.connect(), FlowResult.FAILED)
                self.assertEqual(len(self.calls) - before, 2)
                self.assertEqual(self.store.snapshot().state, 'disconnected')
                self.assertEqual(self.session.status()['login'], 'idle')

    def test_expiry_and_timeout_never_poll_or_exchange(self):
        self.expires = 2
        self.assertEqual(self.flow.connect(), FlowResult.EXPIRED)
        self.assertEqual(len(self.calls), 1)
        self.expires = 60
        self.flow.max_seconds = 2
        self.assertEqual(self.flow.connect(), FlowResult.TIMEOUT)
        self.assertEqual(len(self.calls), 2)

    def test_declined_replace_and_stale_disconnect_preserve_replacement(self):
        self.install()
        self.ui.replace = False
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(self.calls, [])
        previous = self.store.snapshot().generation
        def confirm():
            self.install()
            return True
        self.ui.confirm_disconnect = confirm
        self.assertEqual(self.flow.disconnect(), FlowResult.SESSION_CHANGED)
        self.assertEqual(self.store.snapshot().generation, previous + 1)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-replacement')

    def test_account_replaced_while_showing_code_reports_session_change(self):
        self.ui.show_hook = self.install
        self.assertEqual(self.flow.connect(), FlowResult.SESSION_CHANGED)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-replacement')
        self.assertEqual(self.ui.closed, 1)

    def test_account_replaced_during_poll_never_overwrites_new_grant(self):
        self.credentials_hook = self.install
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-replacement')
        self.assertEqual(self.ui.closed, 1)

    def test_wait_and_inflight_cancellation_never_install_grant(self):
        self.flow.wait = lambda seconds: True
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(len(self.calls), 1)
        self.flow.wait = self.wait
        self.token_hook = lambda: setattr(self, 'cancel', True)
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertEqual(self.ui.closed, 2)

    def test_prompt_failure_is_redacted_and_close_failure_preserves_committed_grant(self):
        def failed():
            raise OSError('synthetic-secret /private/path')
        self.ui.show_hook = failed
        result = self.flow.connect()
        self.assertEqual(result, FlowResult.FAILED)
        self.assertNotIn('synthetic', repr(result))
        self.assertEqual(self.ui.closed, 1)
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.ui.show_hook = None
        self.ui.close_hook = failed
        self.assertEqual(self.flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-access')

    def test_confirmed_disconnect_clears_only_local_grant_without_network(self):
        self.install()
        self.assertEqual(self.flow.disconnect(), FlowResult.DISCONNECTED)
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertEqual(self.calls, [])
