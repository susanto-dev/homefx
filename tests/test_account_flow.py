"""Account interactions with real private stores and synthetic service responses."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.account_flow import AccountFlow, FlowResult
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import Response
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_library import Library


class UI:
    def __init__(self):
        self.codes, self.closed = [], 0
        self.replace = self.disconnect = True

    def confirm_replace(self):
        return self.replace

    def confirm_disconnect(self):
        return self.disconnect

    def show_code(self, code, url):
        self.codes.append((code, url))

    def close(self):
        self.closed += 1


class AccountFlowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = TokenStore(temp.name)
        self.tick, self.cancel = 0, False
        self.calls, self.waits = [], []
        self.responses = [Response(200, body={
            'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh',
            'token_type': 'bearer', 'created_at': 1000, 'expires_in': 3600})]
        self.token_hook = None
        self.expires = 600

        def oauth(method, path, body):
            self.calls.append((path, self.tick))
            if path.endswith('/code'):
                return Response(200, body={'device_code': 'synthetic-private-code',
                    'user_code': 'DEMO', 'verification_url': 'https://trakt.tv/activate',
                    'interval': 5, 'expires_in': self.expires})
            if self.token_hook:
                self.token_hook()
            return self.responses.pop(0) if self.responses else Response(400)

        self.session = Session(self.store, oauth, None, 'synthetic-client',
            'https://example.invalid/callback', clock=lambda: 1000,
            monotonic=lambda: self.tick)
        self.ui = UI()
        self.library = Library(self.session)
        self.flow = AccountFlow(self.session, self.ui, self.wait,
            lambda: self.cancel, lambda: self.tick, self.library.disconnect)

    def wait(self, seconds):
        self.waits.append(seconds)
        self.tick += seconds
        return False

    def install(self):
        self.store.install(TokenSet('synthetic-new-access', 'synthetic-new-refresh', 5000))

    def test_authorization_polls_only_when_due_and_closes(self):
        self.assertEqual(self.flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(self.calls, [('/oauth/device/code', 0), ('/oauth/device/token', 5)])
        self.assertTrue(all(0 < delay <= 1 for delay in self.waits))
        self.assertEqual(self.ui.closed, 1)
        self.assertEqual(self.store.snapshot().state, 'ready')
        self.assertEqual(self.ui.codes, [('DEMO', 'https://trakt.tv/activate')])
        self.assertNotIn('synthetic', repr(self.flow))

    def test_declined_replacement_preserves_credentials_without_requests(self):
        self.install()
        before = self.store.snapshot()
        self.ui.replace = False
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.calls, [])

    def test_replacement_during_confirmation_is_preserved(self):
        self.install()
        def confirm():
            self.install()
            return True
        self.ui.confirm_replace = confirm
        self.assertEqual(self.flow.connect(), FlowResult.SESSION_CHANGED)
        self.assertEqual(self.store.snapshot().generation, 2)
        self.assertEqual(self.calls, [])

    def test_pending_and_rate_limit_respect_next_poll(self):
        success = self.responses[0]
        self.responses = [Response(400), Response(429, headers={'Retry-After': '20'}), success]
        self.assertEqual(self.flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual([tick for _, tick in self.calls], [0, 5, 10, 30])

    def test_terminal_responses_never_retry(self):
        for status, outcome in ((404, 'invalid'), (409, 'used'), (410, 'expired'),
                                (418, 'denied'), (500, 'failed')):
            with self.subTest(status=status):
                self.responses = [Response(status)]
                before = len(self.calls)
                self.assertEqual(self.flow.connect().value, outcome)
                self.assertEqual(len(self.calls) - before, 2)
                self.assertEqual(self.session.status()['login'], 'idle')

    def test_local_expiry_and_overall_timeout(self):
        self.expires = 2
        self.assertEqual(self.flow.connect(), FlowResult.EXPIRED)
        self.assertEqual(len(self.calls), 1)
        self.expires = 600
        self.flow.max_seconds = 2
        self.assertEqual(self.flow.connect(), FlowResult.TIMEOUT)
        self.assertEqual(len(self.calls), 2)

    def test_wait_cancellation_and_inflight_cancellation_do_not_install_tokens(self):
        self.flow.wait = lambda seconds: True
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(len(self.calls), 1)
        self.flow.wait = self.wait
        self.token_hook = lambda: setattr(self, 'cancel', True)
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertEqual(self.ui.closed, 2)

    def test_frozen_clock_fails_without_polling(self):
        self.flow.wait = lambda seconds: False
        self.assertEqual(self.flow.connect(), FlowResult.FAILED)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.session.status()['login'], 'idle')

    def test_ui_exception_is_redacted_and_attempt_closed(self):
        def failed(*args):
            raise OSError('synthetic-private-code /private/path')
        self.ui.show_code = failed
        result = self.flow.connect()
        self.assertEqual(result, FlowResult.FAILED)
        self.assertNotIn('synthetic', repr(result))
        self.assertEqual(self.ui.closed, 1)
        self.assertEqual(self.session.status()['login'], 'idle')

    def test_token_storage_failure_is_not_authorized(self):
        def failed(*args, **kwargs):
            raise OSError('synthetic-private-path')
        self.store.install = failed
        self.assertEqual(self.flow.connect(), FlowResult.FAILED)
        self.assertEqual(self.session.status()['login'], 'idle')

    def test_close_failure_does_not_undo_committed_authorization(self):
        def failed():
            self.install()
            raise OSError('synthetic-private-error')
        self.ui.close = failed
        self.assertEqual(self.flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-new-access')

    def test_disconnect_decline_then_confirm(self):
        self.install()
        self.ui.disconnect = False
        self.assertEqual(self.flow.disconnect(), FlowResult.CANCELLED)
        self.assertEqual(self.store.snapshot().state, 'ready')
        self.ui.disconnect = True
        self.assertEqual(self.flow.disconnect(), FlowResult.DISCONNECTED)
        self.assertEqual(self.store.snapshot().state, 'disconnected')

    def test_disconnect_stale_confirmation_preserves_replacement(self):
        self.install()
        def confirm():
            self.install()
            return True
        self.ui.confirm_disconnect = confirm
        self.assertEqual(self.flow.disconnect(), FlowResult.SESSION_CHANGED)
        self.assertEqual(self.store.snapshot().generation, 2)

    def test_disconnect_cleanup_failure_is_not_success(self):
        def failed(**kwargs):
            raise OSError('synthetic-private-path')
        self.flow.disconnect_callback = failed
        self.assertEqual(self.flow.disconnect(), FlowResult.FAILED)

    def test_cancellation_callback_failure_cannot_install_credentials(self):
        def token_hook():
            def failed():
                raise OSError('synthetic-private-error')
            self.flow.cancelled = failed
        self.token_hook = token_hook
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertEqual(self.ui.closed, 1)

    def test_backward_clock_and_wait_exception_end_attempt(self):
        def backwards(seconds):
            self.tick -= 1
            return False
        self.flow.wait = backwards
        self.assertEqual(self.flow.connect(), FlowResult.FAILED)
        def failed(seconds):
            raise OSError('synthetic-private-error')
        self.flow.wait = failed
        self.assertEqual(self.flow.connect(), FlowResult.FAILED)
        self.assertEqual(self.session.status()['login'], 'idle')
        self.assertEqual(len(self.calls), 2)

    def test_timeout_during_token_request_prevents_install(self):
        self.token_hook = lambda: setattr(self, 'tick', 601)
        self.assertEqual(self.flow.connect(), FlowResult.TIMEOUT)
        self.assertEqual(self.store.snapshot().state, 'disconnected')

    def test_cancelled_code_request_never_shows_code(self):
        original = self.session._oauth
        def request(*args):
            response = original(*args)
            self.cancel = True
            return response
        self.session._oauth = request
        self.assertEqual(self.flow.connect(), FlowResult.CANCELLED)
        self.assertEqual(self.ui.codes, [])
        self.assertEqual(self.session.status()['login'], 'idle')
