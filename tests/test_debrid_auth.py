"""Fabricated device grant exchanges; no credentials or live service calls."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.debrid_auth import (AuthError, Credentials, DeviceLogin, GRANT_TYPE,
                                       Tokens, VERIFY_URL, refresh)


def response(body, status=200):
    return SimpleNamespace(status=status, body=body)


class DeviceGrantTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.calls = []
        self.device = dict(device_code='synthetic-device', user_code='SYNTHETIC',
                           interval=5, expires_in=30, verification_url=VERIFY_URL)
        self.credentials = dict(client_id='synthetic-bound-id', client_secret='synthetic-secret')
        self.tokens = dict(access_token='synthetic-access', refresh_token='synthetic-refresh',
                           expires_in=3600, token_type='Bearer')
        self.responses = [response(self.device), response(self.credentials), response(self.tokens)]

    def request(self, method, path, parameters):
        self.calls.append((method, path, parameters))
        result = self.responses.pop(0)
        if callable(result):
            return result()
        return result

    def login(self, **kwargs):
        return DeviceLogin(self.request, 'synthetic-public', clock=lambda: self.now,
                           wall_clock=lambda: 1000, **kwargs)

    def test_complete_grant_uses_user_bound_credentials_and_form_contract(self):
        flow = self.login()
        prompt = flow.begin()
        self.assertEqual(prompt.verification_url, VERIFY_URL)
        self.assertEqual(self.calls[0], ('GET', '/oauth/v2/device/code',
            {'client_id': 'synthetic-public', 'new_credentials': 'yes'}))
        self.assertEqual(flow.poll(), 'pending')
        self.assertEqual(len(self.calls), 1)
        self.now = 5
        self.assertEqual(flow.poll(), 'authorized')
        self.assertEqual(self.calls[1], ('GET', '/oauth/v2/device/credentials',
            {'client_id': 'synthetic-public', 'code': 'synthetic-device'}))
        self.assertEqual(self.calls[2], ('POST', '/oauth/v2/token',
            dict(self.credentials, code='synthetic-device', grant_type=GRANT_TYPE)))
        self.assertEqual(flow.tokens.expires_at, 4600)
        self.assertEqual(flow.credentials.client_id, 'synthetic-bound-id')
        self.assertIsNone(flow.prompt)
        self.assertIsNone(flow._code)
        self.assertEqual(flow.poll(), 'authorized')
        self.assertEqual(len(self.calls), 3)
        for private in (flow, prompt, flow.credentials, flow.tokens):
            self.assertNotIn('synthetic', repr(private))
        with self.assertRaisesRegex(AuthError, 'attempt_already_started'):
            flow.begin()

    def test_pending_error_requires_explicit_classifier_and_honors_interval(self):
        self.responses.insert(1, response({'error': 'synthetic-not-ready'}, 403))
        flow = self.login(pending_response=lambda r: r.body == {'error': 'synthetic-not-ready'})
        flow.begin()
        self.now = 5
        self.assertEqual(flow.poll(), 'pending')
        self.assertEqual(flow.next_poll, 10)
        self.now = 9
        self.assertEqual(flow.poll(), 'pending')
        self.assertEqual(len(self.calls), 2)
        self.now = 10
        self.assertEqual(flow.poll(), 'authorized')
        self.assertEqual(len(self.calls), 4)

    def test_unknown_error_fails_closed_without_retry(self):
        self.responses[1] = response({'error': 'private arbitrary response'}, 403)
        flow = self.login()
        flow.begin()
        self.now = 5
        with self.assertRaisesRegex(AuthError, '^authorization_failed$'):
            flow.poll()
        self.assertEqual(flow.poll(), 'failed')
        self.assertEqual(len(self.calls), 2)
        self.assertIsNone(flow.credentials)

    def test_classifier_cannot_override_rate_limit_or_token_error(self):
        for index, status in ((1, 429), (2, 403)):
            with self.subTest(index=index):
                self.setUp()
                self.responses[index] = response({'error': 'synthetic'}, status)
                classified = []
                flow = self.login(pending_response=lambda r: classified.append(r) or True)
                flow.begin()
                self.now = 5
                with self.assertRaises(AuthError):
                    flow.poll()
                self.assertEqual(classified, [])
                self.assertEqual(flow.poll(), 'failed')
                self.assertIsNone(flow.tokens)

    def test_classifier_exception_is_redacted_and_terminal(self):
        self.responses[1] = response({'error': 'synthetic'}, 403)
        def classifier(_):
            raise RuntimeError('secret response text')
        flow = self.login(pending_response=classifier)
        flow.begin()
        self.now = 5
        with self.assertRaisesRegex(AuthError, '^invalid_pending_response$'):
            flow.poll()
        self.assertEqual(flow.poll(), 'failed')

    def test_expiry_prevents_request_and_expired_token_response_not_installed(self):
        flow = self.login()
        flow.begin()
        self.now = 30
        self.assertEqual(flow.poll(), 'expired')
        self.assertEqual(len(self.calls), 1)
        self.setUp()
        flow = self.login()
        def late_token():
            self.now = 30
            return response(self.tokens)
        self.responses[2] = late_token
        flow.begin()
        self.now = 5
        self.assertEqual(flow.poll(), 'expired')
        self.assertIsNone(flow.credentials)
        self.assertIsNone(flow.tokens)

    def test_cancellation_during_each_request_discards_all_sensitive_results(self):
        for index in (0, 1, 2):
            with self.subTest(index=index):
                self.setUp()
                flow = self.login()
                original = self.responses[index]
                def cancel_response():
                    flow.cancel()
                    return original
                self.responses[index] = cancel_response
                flow.begin()
                self.now = 5
                self.assertEqual(flow.poll(), 'cancelled')
                self.assertEqual(len(self.calls), index + 1)
                self.assertIsNone(flow.credentials)
                self.assertIsNone(flow.tokens)
                self.assertIsNone(flow.prompt)

    def test_cancel_callback_cannot_hide_explicit_cancel_with_false_return(self):
        flow = self.login()
        def cancel_then_false():
            flow.cancel()
            return False
        self.assertIsNone(flow.begin(cancelled=cancel_then_false))
        self.assertEqual(flow.state, 'cancelled')
        self.assertEqual(self.calls, [])

    def test_external_cancellation_after_callback_is_honored(self):
        stopped = [False]
        def returned():
            stopped[0] = True
            return response(self.tokens)
        self.responses[2] = returned
        flow = self.login()
        flow.begin()
        self.now = 5
        self.assertEqual(flow.poll(cancelled=lambda: stopped[0]), 'cancelled')
        self.assertIsNone(flow.tokens)

    def test_token_timeout_is_single_attempt_and_redacted(self):
        def lost():
            raise TimeoutError('secret-token-and-url')
        self.responses[2] = lost
        flow = self.login()
        flow.begin()
        self.now = 5
        with self.assertRaisesRegex(AuthError, '^transport_error$'):
            flow.poll()
        self.assertEqual(flow.poll(), 'failed')
        self.assertEqual(len(self.calls), 3)
        self.assertIsNone(flow.credentials)

    def test_cancel_callback_reentry_observes_without_running_exchange(self):
        flow = self.login()
        flow.begin()
        nested = []
        def pump():
            nested.append(flow.poll())
            return False
        self.assertEqual(flow.poll(cancelled=pump), 'pending')
        self.assertEqual(len(self.calls), 1)
        self.now = 5
        self.assertEqual(flow.poll(cancelled=pump), 'authorized')
        self.assertEqual(len(self.calls), 3)
        self.assertNotIn('authorized', nested)
        self.assertEqual(flow.poll(), 'authorized')

    def test_clock_callback_reentry_observes_without_running_exchange(self):
        nested = []
        flow = None
        def clock():
            nested.append(flow.poll())
            return self.now
        flow = DeviceLogin(self.request, 'synthetic-public', clock=clock,
                           wall_clock=lambda: 1000)
        flow.begin()
        self.assertEqual(flow.poll(), 'pending')
        self.assertEqual(len(self.calls), 1)
        self.now = 5
        self.assertEqual(flow.poll(), 'authorized')
        self.assertEqual(len(self.calls), 3)
        self.assertNotIn('authorized', nested)

    def test_reentrant_poll_does_not_duplicate_exchange(self):
        flow = self.login()
        original = self.responses[2]
        def during_token():
            self.assertEqual(flow.poll(), 'exchanging')
            return original
        self.responses[2] = during_token
        flow.begin()
        self.now = 5
        self.assertEqual(flow.poll(), 'authorized')
        self.assertEqual(len(self.calls), 3)

    def test_invalid_device_shapes_and_verification_urls_fail_closed(self):
        changes = ({'interval': True}, {'interval': float('inf')}, {'expires_in': 0},
                   {'verification_url': VERIFY_URL + '?token=private'},
                   {'verification_url': 'https://real-debrid.com.evil.invalid/device'},
                   {'device_code': []}, {'user_code': 'bad\ncode'})
        for change in changes:
            with self.subTest(change=change):
                self.setUp()
                self.device.update(change)
                flow = self.login()
                with self.assertRaisesRegex(AuthError, '^invalid_device_response$'):
                    flow.begin()
                self.assertEqual(flow.state, 'failed')
                self.assertIsNone(flow.prompt)

    def test_invalid_token_response_and_backward_clock_fail_closed(self):
        for change in ({'token_type': 'unexpected'}, {'expires_in': float('nan')},
                       {'refresh_token': {}}, {'expires_in': True}, {'expires_in': 10 ** 1000}):
            with self.subTest(change=change):
                self.setUp()
                self.tokens.update(change)
                flow = self.login()
                flow.begin()
                self.now = 5
                with self.assertRaises(AuthError):
                    flow.poll()
                self.assertIsNone(flow.credentials)
                self.assertIsNone(flow.tokens)
        self.setUp()
        self.now = 2
        flow = self.login()
        flow.begin()
        self.now = 1
        with self.assertRaisesRegex(AuthError, '^invalid_clock$'):
            flow.poll()
        self.assertEqual(flow.state, 'failed')

    def test_refresh_contract_and_cancellation_after_response(self):
        credentials = Credentials(**self.credentials)
        self.responses = [response(self.tokens)]
        token = refresh(self.request, credentials, 'synthetic-old-refresh', clock=lambda: 2000)
        self.assertEqual(token.expires_at, 5600)
        self.assertEqual(self.calls, [('POST', '/oauth/v2/token', dict(self.credentials,
            code='synthetic-old-refresh', grant_type=GRANT_TYPE))])
        stopped = [False]
        def late_response():
            stopped[0] = True
            return response(self.tokens)
        self.responses = [late_response]
        with self.assertRaisesRegex(AuthError, '^cancelled$'):
            refresh(self.request, credentials, 'synthetic-refresh', clock=lambda: 2000,
                    cancelled=lambda: stopped[0])
        self.assertEqual(len(self.calls), 2)

    def test_refresh_transport_failure_and_invalid_inputs_never_retry(self):
        credentials = Credentials(**self.credentials)
        def lost():
            raise RuntimeError('private request')
        self.responses = [lost]
        with self.assertRaisesRegex(AuthError, '^transport_error$'):
            refresh(self.request, credentials, 'synthetic-refresh')
        self.assertEqual(len(self.calls), 1)
        for invalid in (None, {}, '', 'bad\nvalue'):
            with self.assertRaisesRegex(AuthError, '^invalid_refresh_input$'):
                refresh(self.request, credentials, invalid)
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(AuthError):
            Tokens('synthetic', 'synthetic', float('nan'))


if __name__ == '__main__':
    unittest.main()
