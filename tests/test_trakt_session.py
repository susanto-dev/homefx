"""Session tests use temporary profiles and synthetic responses only."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore


def token_response(suffix="new", created=1000):
    return Response(200, body={"access_token": "synthetic-access-" + suffix,
        "refresh_token": "synthetic-refresh-" + suffix, "token_type": "bearer",
        "created_at": created, "expires_in": 3600})


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = TokenStore(self.temp.name)
        self.now, self.tick = [1000], [0]
        self.oauth_calls, self.api_calls = [], []
        self.oauth_reply = None
        self.api_reply = None

        def oauth(method, path, body):
            self.oauth_calls.append((method, path, body))
            if self.oauth_reply is not None:
                return self.oauth_reply(method, path, body)
            if path == "/oauth/device/code":
                return Response(200, body={"device_code": "synthetic-device",
                    "user_code": "DEMO", "verification_url": "https://trakt.tv/activate",
                    "interval": 5, "expires_in": 600})
            return token_response()

        def api(method, path, headers, body=None):
            self.api_calls.append((method, path, headers, body))
            return self.api_reply() if self.api_reply else Response(200, body={"limits": {}})

        self.session = Session(self.store, oauth, api, "synthetic-client",
                               "https://example.invalid/callback", clock=lambda: self.now[0],
                               monotonic=lambda: self.tick[0])

    def install(self, expires=5000):
        self.store.install(TokenSet("synthetic-access-old", "synthetic-refresh-old", expires))

    def test_confirmed_login_and_disconnect_reject_stale_generation(self):
        self.install()
        stale = self.store.snapshot().generation
        self.install()
        self.session.begin_login()
        current = self.session.login_timing()
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.session.begin_login(expected_generation=stale)
        self.assertFalse(self.session.disconnect(expected_generation=stale))
        self.assertEqual(self.session.login_timing(), current)
        self.assertEqual(len(self.oauth_calls), 1)

    def test_login_timing_excludes_codes_and_cancellation_during_poll_blocks_install(self):
        self.session.begin_login()
        timing = self.session.login_timing()
        self.assertEqual(timing, {"state": "pending", "next_poll": 5, "expires_at": 600})
        self.tick[0] = 5
        cancelled = [False]
        def reply(*args):
            cancelled[0] = True
            return token_response()
        self.oauth_reply = reply
        self.assertEqual(self.session.poll_login(cancelled=lambda: cancelled[0]), "cancelled")
        self.assertEqual(self.store.snapshot().state, "disconnected")
        self.assertEqual(self.session.login_timing()["state"], "idle")

    def test_status_never_refreshes_and_session_construction_has_no_io(self):
        class NoStore:
            def __getattr__(self, name):
                raise AssertionError("constructor must not access store")
        Session(NoStore(), None, None, "synthetic-client", "https://example.invalid/callback")
        self.install(expires=1001)
        self.assertEqual(self.session.status()["state"], "refresh_required")
        self.assertEqual(self.oauth_calls, [])
        self.assertEqual(self.api_calls, [])
        self.assertNotIn("synthetic", repr(self.session))

    def test_fresh_read_does_not_refresh(self):
        self.install()
        self.assertEqual(self.session.read("settings"), {"limits": {}})
        self.assertEqual(len(self.oauth_calls), 0)
        self.assertEqual(self.api_calls[0][2]["Authorization"], "Bearer synthetic-access-old")

    def test_expired_token_rotates_once_before_read(self):
        self.install(expires=900)
        self.session.read("settings")
        self.session.read("settings")
        self.assertEqual(len(self.oauth_calls), 1)
        self.assertEqual(self.oauth_calls[0][1], "/oauth/token")
        self.assertEqual(self.api_calls[0][2]["Authorization"], "Bearer synthetic-access-new")
        self.assertEqual(self.store.snapshot().generation, 2)

    def test_busy_refresh_and_ambiguous_refresh_do_not_read_or_retry(self):
        self.install(expires=900)
        self.store.claim_refresh(1)
        with self.assertRaisesRegex(AuthError, "refresh_busy"):
            self.session.read("settings")
        self.assertEqual(self.oauth_calls + self.api_calls, [])
        self.install(expires=900)
        def timeout(*args):
            raise OSError("synthetic-secret-transport-detail")
        self.oauth_reply = timeout
        for _ in range(2):
            with self.assertRaisesRegex(AuthError, "reauthentication_required"):
                self.session.read("settings")
        self.assertEqual(len(self.oauth_calls), 1)
        self.assertEqual(self.api_calls, [])

    def test_401_disconnects_without_retry_and_old_401_preserves_new_login(self):
        self.install()
        self.api_reply = lambda: Response(401)
        with self.assertRaisesRegex(ApiError, "reauthenticate"):
            self.session.read("settings")
        self.assertEqual(len(self.api_calls), 1)
        self.assertEqual(self.store.snapshot().state, "disconnected")
        self.install()
        def switch_account():
            self.store.install(TokenSet("synthetic-other-access", "synthetic-other-refresh", 5000))
            return Response(401)
        self.api_reply = switch_account
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.session.read("settings")
        self.assertEqual(self.store.snapshot().tokens.access_token, "synthetic-other-access")

    def test_login_poll_and_disconnect(self):
        self.install()
        prompt = self.session.begin_login()
        self.assertEqual(prompt.user_code, "DEMO")
        self.assertEqual(self.store.snapshot().state, "disconnected")
        self.assertEqual(self.session.poll_login(), "pending")
        self.tick[0] = 5
        self.assertEqual(self.session.poll_login(), "authorized")
        self.assertEqual(self.session.status()["state"], "ready")
        self.session.disconnect()
        self.assertIsNone(self.store.snapshot().tokens)

    def test_cancel_during_login_callback_does_not_install_result(self):
        self.session.begin_login()
        self.tick[0] = 5
        def cancel(*args):
            self.session.cancel_login()
            return token_response()
        self.oauth_reply = cancel
        self.assertEqual(self.session.poll_login(), "cancelled")
        self.assertIsNone(self.store.snapshot().tokens)

    def test_external_disconnect_during_login_callback_rejects_result(self):
        self.session.begin_login()
        self.tick[0] = 5
        def disconnect(*args):
            TokenStore(self.temp.name).disconnect()
            return token_response()
        self.oauth_reply = disconnect
        self.assertEqual(self.session.poll_login(), "cancelled")
        self.assertIsNone(self.store.snapshot().tokens)

    def test_new_login_replaces_old_attempt_without_old_result_winning(self):
        self.session.begin_login()
        self.tick[0] = 5
        def replace(method, path, body):
            self.oauth_reply = None
            self.session.begin_login()
            return token_response("old-attempt")
        self.oauth_reply = replace
        self.assertEqual(self.session.poll_login(), "cancelled")
        self.tick[0] = 10
        self.assertEqual(self.session.poll_login(), "authorized")
        self.assertEqual(self.store.snapshot().tokens.access_token, "synthetic-access-new")

    def test_expired_login_response_not_installed_and_config_is_required(self):
        self.session.begin_login()
        self.tick[0] = 5
        self.oauth_reply = lambda *args: token_response(created=1)
        self.now[0] = 5000
        with self.assertRaisesRegex(AuthError, "invalid_token_response"):
            self.session.poll_login()
        self.assertIsNone(self.store.snapshot().tokens)
        with self.assertRaisesRegex(AuthError, "invalid_client_identity"):
            Session(self.store, None, None, "synthetic-client", "")

    def test_read_result_discarded_if_other_invocation_disconnects(self):
        self.install()
        def disconnect():
            TokenStore(self.temp.name).disconnect()
            return Response(200, body={"private": "synthetic account data"})
        self.api_reply = disconnect
        with self.assertRaisesRegex(AuthError, "session_changed"):
            self.session.read("settings")
        self.assertEqual(len(self.api_calls), 1)


class SessionMutationTests(unittest.TestCase):
    install = SessionTests.install

    def setUp(self):
        SessionTests.setUp(self)
        self.writes = []
        self.write_reply = None
        def mutation(*args):
            self.writes.append(args)
            return self.write_reply() if self.write_reply else Response(200, body={
                'added': {'movies': 1, 'episodes': 0},
                'updated': {'movies': 0, 'episodes': 0}, 'not_found': {}})
        self.session._mutation = mutation

    def mark(self):
        from datetime import datetime, timezone
        return self.session.mutate('mark_watched', 'movie', 11,
                                   datetime(2026, 11, 12, tzinfo=timezone.utc))

    def test_disabled_and_invalid_actions_do_not_refresh_or_write(self):
        from resources.lib.trakt_client import ListRef
        self.install(expires=900)
        with self.assertRaisesRegex(ApiError, 'invalid_action'):
            self.session.mutate('add_movie_to_list', ListRef(7, 'other', 'Liked', False), 11)
        self.session._mutation = None
        self.assertEqual(self.mark().reason, 'writes_disabled')
        self.assertEqual(self.writes + self.oauth_calls, [])
        self.assertEqual(self.session.data_revision, 0)

    def test_refresh_before_write_and_revision_invalidation(self):
        self.install(expires=900)
        self.assertEqual(self.mark().outcome, 'confirmed')
        self.assertEqual(len(self.oauth_calls), 1)
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.writes[0][2]['Authorization'], 'Bearer synthetic-access-new')
        self.assertEqual(self.session.data_revision, 2)

    def test_uncertain_write_is_not_retried_or_installed_as_watched(self):
        self.install()
        before = self.store.snapshot()
        def timeout():
            raise OSError('synthetic-private-response')
        self.write_reply = timeout
        self.assertEqual(self.mark().outcome, 'uncertain')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.session.data_revision, 2)
        self.assertEqual(self.store.snapshot(), before)

    def test_stale_success_or_401_does_not_claim_or_disconnect_new_account(self):
        for status in (200, 401):
            self.install()
            def switch():
                self.store.install(TokenSet('synthetic-replacement', 'synthetic-new-refresh', 5000))
                return Response(status)
            self.write_reply = switch
            result = self.mark()
            self.assertEqual((result.outcome, result.reason), ('uncertain', 'session_changed'))
            self.assertEqual(self.store.snapshot().tokens.access_token, 'synthetic-replacement')
        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self.session.data_revision, 4)

    def test_current_401_disconnects_once_and_does_not_retry(self):
        self.install()
        self.write_reply = lambda: Response(401)
        result = self.mark()
        self.assertEqual(result.reason, 'reauthenticate')
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.session.data_revision, 2)


    def test_pending_action_rejects_reads_and_nested_mutation_then_clears(self):
        self.install()
        for uncertain in (False, True):
            def pending():
                for action in (lambda: self.session.read('settings'), self.session.cache_key, self.mark):
                    with self.assertRaisesRegex(AuthError, '^action_in_progress$'):
                        action()
                self.assertEqual(self.api_calls, [])
                if uncertain:
                    raise OSError('synthetic lost response')
                return Response(200, body={
                    'added': {'movies': 1, 'episodes': 0},
                    'updated': {'movies': 0, 'episodes': 0}, 'not_found': {}})
            self.write_reply = pending
            prior_revision = self.session.data_revision
            result = self.mark()
            self.assertEqual(result.outcome, 'uncertain' if uncertain else 'confirmed')
            self.assertEqual(self.session.data_revision, prior_revision + 2)
            self.assertFalse(self.session._mutation_pending)
            self.session.read('settings')
            self.assertEqual(len(self.api_calls), 1)
            self.api_calls.clear()
        self.assertEqual(len(self.writes), 2)

    def test_overlapping_reader_is_rejected_without_waiting_for_callback(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        self.install()
        entered, finish = Event(), Event()
        def pending():
            entered.set()
            if not finish.wait(3):
                raise AssertionError('Test did not release callback')
            raise OSError('synthetic lost response')
        self.write_reply = pending
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.mark)
            try:
                self.assertTrue(entered.wait(3))
                with self.assertRaisesRegex(AuthError, '^action_in_progress$'):
                    self.session.read('settings')
                with self.assertRaisesRegex(AuthError, '^action_in_progress$'):
                    self.mark()
            finally:
                finish.set()
            self.assertEqual(future.result(timeout=3).outcome, 'uncertain')
        self.session.read('settings')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(len(self.api_calls), 1)
        self.assertEqual(self.session.data_revision, 2)
