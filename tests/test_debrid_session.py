"""Provider sessions use real temporary stores and fabricated network responses."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.debrid_auth import AuthError, Credentials, Tokens, VERIFY_URL
from resources.lib.debrid_client import DebridError, Response
from resources.lib.debrid_session import Session
from resources.lib.debrid_store import CredentialStore


class SessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = temporary.name
        self.now, self.tick = [1000], [0]
        self.store = CredentialStore(self.directory, clock=lambda: self.now[0], claim_ttl=30)
        self.oauth_calls, self.api_calls = [], []
        self.oauth_hook = self.api_hook = None
        self.bound = Credentials('synthetic-bound', 'synthetic-user-secret')
        self.session = self.make_session(self.store)

    def make_session(self, store):
        return Session(store, self.oauth, self.api, 'synthetic-public',
                       clock=lambda: self.now[0], monotonic=lambda: self.tick[0])

    def token_response(self):
        return Response(200, body=dict(access_token='synthetic-new-access',
            refresh_token='synthetic-new-refresh', token_type='Bearer', expires_in=3600))

    def oauth(self, method, path, body):
        self.oauth_calls.append((method, path, body))
        if self.oauth_hook:
            return self.oauth_hook(method, path, body)
        if path.endswith('/device/code'):
            return Response(200, body=dict(device_code='synthetic-device', user_code='DEMO',
                interval=5, expires_in=60, verification_url=VERIFY_URL))
        if path.endswith('/device/credentials'):
            return Response(200, body=dict(client_id=self.bound.client_id,
                                           client_secret=self.bound.client_secret))
        return self.token_response()

    def api(self, method, path, headers, body):
        self.api_calls.append((method, path, headers, body))
        if self.api_hook:
            return self.api_hook(method, path, headers, body)
        if path == '/rest/1.0/user':
            return Response(200, body=dict(type='premium', premium=3600,
                                           expiration='2030-01-01T00:00:00Z'))
        if path.startswith('/rest/1.0/downloads'):
            return Response(200, {'X-Total-Count': '0'}, [])
        return Response(200, body=dict(id='demo', filename='invented.mp4', filesize=100,
                                      download='https://cdn.example/private-demo'))

    def install(self, expires=5000, suffix='old'):
        self.store.install(self.bound, Tokens('synthetic-access-' + suffix,
                                             'synthetic-refresh-' + suffix, expires))

    def test_status_and_player_generation_never_refresh(self):
        self.install(expires=1050)
        self.assertEqual(self.session.status()['state'], 'refresh_required')
        self.assertEqual(self.session.current_generation(), 1)
        self.assertEqual(self.session.cache_key(), 1)
        self.now[0] = 1050
        with self.assertRaisesRegex(AuthError, 'session_changed'):
            self.session.current_generation()
        self.assertEqual(self.oauth_calls + self.api_calls, [])
        self.assertNotIn('synthetic', repr(self.session))
        self.assertNotIn('synthetic', repr(self.session.status()))

    def test_login_commits_user_bound_credentials_and_clears_memory(self):
        self.session.begin_login(expected_generation=0)
        self.assertEqual(self.session.login_timing(expected_generation=1),
                         dict(state='pending', next_poll=5, expires_at=60))
        self.assertEqual(self.session.poll_login(expected_generation=1), 'pending')
        self.tick[0] = 5
        self.assertEqual(self.session.poll_login(expected_generation=1), 'authorized')
        snapshot = CredentialStore(self.directory, clock=lambda: self.now[0]).snapshot()
        self.assertEqual(snapshot.credentials, self.bound)
        self.assertEqual(snapshot.tokens.access_token, 'synthetic-new-access')
        self.assertEqual(snapshot.generation, 2)
        self.assertEqual(self.session.login_timing()['state'], 'idle')
        self.assertEqual(len(self.oauth_calls), 3)

    def test_stale_confirmation_preserves_new_account_and_pending_login(self):
        self.install()
        stale = self.store.snapshot().generation
        self.session.begin_login()
        timing = self.session.login_timing()
        with self.assertRaisesRegex(AuthError, 'session_changed'):
            self.session.begin_login(expected_generation=stale)
        self.assertFalse(self.session.disconnect(expected_generation=stale))
        self.assertEqual(self.session.login_timing(), timing)
        self.assertEqual(len(self.oauth_calls), 1)

    def test_cancellation_after_token_response_cannot_install(self):
        self.session.begin_login()
        self.tick[0] = 5
        cancelled = [False]
        def hook(method, path, body):
            if path.endswith('/credentials'):
                return Response(200, body=dict(client_id='synthetic-bound', client_secret='synthetic-secret'))
            cancelled[0] = True
            return self.token_response()
        self.oauth_hook = hook
        self.assertEqual(self.session.poll_login(cancelled=lambda: cancelled[0]), 'cancelled')
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertIsNone(self.store.snapshot().tokens)
        self.assertEqual(self.session.login_timing()['state'], 'idle')

    def test_new_account_during_token_response_survives_old_login(self):
        self.session.begin_login()
        self.tick[0] = 5
        def hook(method, path, body):
            if path.endswith('/credentials'):
                return Response(200, body=dict(client_id='synthetic-bound', client_secret='synthetic-secret'))
            self.install(suffix='replacement')
            return self.token_response()
        self.oauth_hook = hook
        self.assertEqual(self.session.poll_login(), 'cancelled')
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-access-replacement')

    def test_login_callbacks_cannot_reenter_and_poll_replacement(self):
        self.session.begin_login()
        self.tick[0] = 5
        def cancelled():
            with self.assertRaisesRegex(AuthError, 'login_in_progress'):
                self.session.poll_login()
            with self.assertRaisesRegex(AuthError, 'login_in_progress'):
                self.session.begin_login()
            return False
        self.assertEqual(self.session.poll_login(cancelled=cancelled), 'authorized')
        self.assertEqual(len(self.oauth_calls), 3)

    def test_stale_pinned_poll_does_not_touch_new_attempt(self):
        self.session.begin_login()
        old = self.store.snapshot().generation
        self.session.begin_login(expected_generation=old)
        with self.assertRaisesRegex(AuthError, 'session_changed'):
            self.session.poll_login(expected_generation=old)
        self.assertEqual(self.session.login_timing()['state'], 'pending')
        self.assertEqual(len(self.oauth_calls), 2)

    def test_refresh_rotates_persisted_pair_once_and_preserves_bound_credentials(self):
        self.install(expires=1050)
        self.assertEqual(self.session.account().type, 'premium')
        self.assertEqual(len(self.oauth_calls), 1)
        form = self.oauth_calls[0][2]
        self.assertEqual(form['code'], 'synthetic-refresh-old')
        self.assertEqual(form['client_secret'], self.bound.client_secret)
        self.assertEqual(form['grant_type'], 'http://oauth.net/grant_type/device/1.0')
        snapshot = CredentialStore(self.directory, clock=lambda: self.now[0]).snapshot()
        self.assertEqual(snapshot.credentials, self.bound)
        self.assertEqual(snapshot.tokens.access_token, 'synthetic-new-access')
        self.assertEqual(snapshot.generation, 2)
        self.session.downloads()
        self.assertEqual(len(self.oauth_calls), 1)

    def test_competing_session_cannot_replay_inflight_refresh(self):
        self.install(expires=1050)
        competitor = self.make_session(CredentialStore(self.directory, clock=lambda: self.now[0]))
        def hook(*args):
            with self.assertRaisesRegex(AuthError, 'refresh_busy'):
                competitor.account()
            with self.assertRaisesRegex(AuthError, 'action_in_progress'):
                self.session.downloads()
            self.assertIsNone(self.store.snapshot().tokens)
            return self.token_response()
        self.oauth_hook = hook
        self.session.account()
        self.assertEqual(len(self.oauth_calls), 1)
        self.assertEqual(len(self.api_calls), 1)

    def test_lost_refresh_is_not_replayed_after_restart(self):
        self.install(expires=1050)
        def lost(*args):
            raise TimeoutError('private credential data')
        self.oauth_hook = lost
        with self.assertRaisesRegex(AuthError, '^transport_error$'):
            self.session.account()
        restarted = self.make_session(CredentialStore(self.directory, clock=lambda: self.now[0]))
        with self.assertRaisesRegex(AuthError, 'reauthentication_required'):
            restarted.account()
        self.assertEqual(self.store.snapshot().state, 'reauth')
        self.assertEqual(len(self.oauth_calls), 1)
        self.assertEqual(self.api_calls, [])

    def test_abandoned_claim_expires_and_late_refresh_cannot_restore_tokens(self):
        self.install(expires=1050)
        def hook(*args):
            self.now[0] += 31
            return self.token_response()
        self.oauth_hook = hook
        with self.assertRaisesRegex(AuthError, 'cancelled'):
            self.session.account()
        self.assertEqual(self.store.snapshot().state, 'reauth')
        self.assertIsNone(self.store.snapshot().credentials)

    def test_account_replacement_during_refresh_survives_old_completion(self):
        self.install(expires=1050)
        def hook(*args):
            self.install(suffix='replacement')
            return self.token_response()
        self.oauth_hook = hook
        with self.assertRaises(AuthError):
            self.session.account()
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-access-replacement')
        self.assertEqual(self.api_calls, [])

    def test_read_401_clears_only_its_generation(self):
        self.install()
        self.api_hook = lambda *args: Response(401, body={})
        with self.assertRaisesRegex(DebridError, 'reauthenticate'):
            self.session.account()
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.install()
        def late(*args):
            self.install(suffix='replacement')
            return Response(401, body={})
        self.api_hook = late
        with self.assertRaisesRegex(AuthError, 'session_changed'):
            self.session.account()
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-access-replacement')

    def test_resolution_reentry_blocked_and_uncertain_result_not_retried(self):
        self.install()
        def hook(*args):
            with self.assertRaisesRegex(AuthError, 'action_in_progress'):
                self.session.account()
            with self.assertRaisesRegex(AuthError, 'action_in_progress'):
                self.session.unrestrict('https://host.example/source')
            raise TimeoutError('private source URL')
        self.api_hook = hook
        with self.assertRaisesRegex(DebridError, 'uncertain'):
            self.session.unrestrict('https://host.example/source')
        self.assertEqual(len(self.api_calls), 1)
        self.assertEqual(self.session.data_revision, 2)
        self.assertEqual(self.store.snapshot().state, 'ready')

    def test_resolution_after_account_change_is_uncertain_without_new_account_clear(self):
        self.install()
        def hook(*args):
            self.install(suffix='replacement')
            return Response(401, body={})
        self.api_hook = hook
        with self.assertRaisesRegex(DebridError, 'uncertain'):
            self.session.unrestrict('https://host.example/source')
        self.assertEqual(len(self.api_calls), 1)
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-access-replacement')

    def test_invalid_link_rejected_before_refresh_or_profile_access(self):
        class NoStore:
            def snapshot(self):
                raise AssertionError('must not read profile')
        session = self.make_session(NoStore())
        with self.assertRaisesRegex(DebridError, 'invalid_url'):
            session.unrestrict('http://localhost/private')
        self.assertEqual(self.oauth_calls + self.api_calls, [])

    def test_parallel_resolution_has_one_callback_in_flight(self):
        self.install()
        entered, release = threading.Event(), threading.Event()
        errors = []
        def hook(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('synthetic test deadline')
            return Response(200, body=dict(id='demo', filename='invented.mp4', filesize=100,
                                          download='https://cdn.example/private-demo'))
        self.api_hook = hook
        def worker():
            try:
                self.session.unrestrict('https://host.example/source')
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            with self.assertRaisesRegex(AuthError, 'action_in_progress'):
                self.session.unrestrict('https://host.example/source')
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(self.api_calls), 1)

    def test_accepted_cancel_invalidates_installation_waiting_at_store_boundary(self):
        self.session.begin_login()
        self.tick[0] = 5
        generation = self.store.snapshot().generation
        entered, release = threading.Event(), threading.Event()
        original = self.store.install
        outcomes, errors = [], []

        def blocked_install(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('synthetic test deadline')
            return original(*args, **kwargs)

        self.store.install = blocked_install
        def poll():
            try:
                outcomes.append(self.session.poll_login(expected_generation=generation))
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=poll)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertTrue(self.session.cancel_login(expected_generation=generation))
            self.assertEqual(self.store.snapshot().generation, generation + 1)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outcomes, ['cancelled'])
        reopened = CredentialStore(self.directory, clock=lambda: self.now[0]).snapshot()
        self.assertEqual(reopened.state, 'disconnected')
        self.assertIsNone(reopened.credentials)
        self.assertIsNone(reopened.tokens)

    def test_cancel_after_installation_commit_is_not_reported_as_accepted(self):
        self.session.begin_login()
        self.tick[0] = 5
        generation = self.store.snapshot().generation
        entered, release = threading.Event(), threading.Event()
        original = self.store.install
        outcomes, errors = [], []

        def committed_install(*args, **kwargs):
            result = original(*args, **kwargs)
            entered.set()
            if not release.wait(3):
                raise TimeoutError('synthetic test deadline')
            return result

        self.store.install = committed_install
        def poll():
            try:
                outcomes.append(self.session.poll_login(expected_generation=generation))
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=poll)
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertFalse(self.session.cancel_login(expected_generation=generation))
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outcomes, ['authorized'])
        self.assertEqual(self.store.snapshot().state, 'ready')
        self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-new-access')
