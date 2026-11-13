"""Synthetic OAuth responses only; never contacts a service or uses account data."""
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError, DeviceLogin, TokenSet, refresh_tokens
from resources.lib.trakt_tokens import TokenStore


def token_body(suffix="one"):
    return {"access_token": "synthetic-access-" + suffix,
            "refresh_token": "synthetic-refresh-" + suffix,
            "token_type": "bearer", "created_at": 1000, "expires_in": 3600}


def response(status=200, body=None, headers=None):
    return SimpleNamespace(status=status, body=body or {}, headers=headers or {})


def device_body(**changes):
    body = {"device_code": "synthetic-device-code", "user_code": "DEMO-CODE",
            "verification_url": "https://trakt.tv/activate", "expires_in": 60, "interval": 5}
    body.update(changes)
    return body


class FakeRequest:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, path, body):
        self.calls.append((method, path, body))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class DeviceLoginTests(unittest.TestCase):
    def setUp(self):
        self.now = 10

    def login(self, *responses, **changes):
        request = FakeRequest(response(body=device_body(**changes)), *responses)
        login = DeviceLogin(request, "synthetic-client", lambda: self.now)
        login.begin()
        return login, request

    def test_pending_obeys_interval_then_authorizes(self):
        login, request = self.login(response(400), response(body=token_body()))
        self.assertEqual(login.poll(), "pending")
        self.assertEqual(len(request.calls), 1)
        self.now = 15
        self.assertEqual(login.poll(), "pending")
        self.assertEqual(login.next_poll, 20)
        self.now = 20
        self.assertEqual(login.poll(), "authorized")
        self.assertEqual(login.tokens.expires_at, 4600)
        self.assertIsNone(login.prompt)
        self.assertIsNone(login._code)
        self.assertEqual(login.poll(), "authorized")
        self.assertEqual(len(request.calls), 3)
        self.assertEqual(request.calls[1][1], "/oauth/device/token")
        self.assertNotIn("client_secret", request.calls[1][2])

    def test_current_and_legacy_activation_urls_preserve_exact_prompt_and_authorize(self):
        for url in ('https://auth.trakt.tv/activate', 'https://trakt.tv/activate'):
            with self.subTest(url=url):
                self.now = 10
                login, request = self.login(response(body=token_body()), verification_url=url)
                self.assertEqual(login.prompt.verification_url, url)
                self.assertEqual(login.prompt.user_code, 'DEMO-CODE')
                self.assertNotIn('DEMO-CODE', repr(login.prompt))
                self.assertNotIn('synthetic-device-code', repr(login))
                self.now = 15
                self.assertEqual(login.poll(), 'authorized')
                self.assertEqual(len(request.calls), 2)

    def test_activation_url_variants_and_lookalikes_fail_without_retaining_codes(self):
        for base in ('https://auth.trakt.tv/activate', 'https://trakt.tv/activate'):
            urls = (base + '/', base + '?code=PRIVATE', base + '#PRIVATE',
                    base.replace('/activate', '/other'),
                    base.replace('https://', 'http://'),
                    base.replace('https://', 'https://name:PRIVATE@'),
                    base.replace('/activate', ':443/activate'),
                    base.replace('/activate', ':8443/activate'),
                    base.replace('.tv/', '.tv.evil.invalid/'),
                    base.replace('/activate', '/%61ctivate'),
                    base + '\nPRIVATE')
            for url in urls:
                with self.subTest(url=url):
                    request = FakeRequest(response(body=device_body(verification_url=url)))
                    login = DeviceLogin(request, 'synthetic-client', lambda: self.now)
                    with self.assertRaisesRegex(AuthError, '^device_code_failed$') as caught:
                        login.begin()
                    self.assertEqual(login.state, 'failed')
                    self.assertIsNone(login.prompt)
                    self.assertIsNone(login._code)
                    self.assertEqual(len(request.calls), 1)
                    for value in (str(caught.exception), repr(login)):
                        self.assertNotIn('PRIVATE', value)
                        self.assertNotIn('DEMO-CODE', value)
                        self.assertNotIn('synthetic-device-code', value)

    def test_terminal_statuses_never_retry(self):
        for status, expected in ((404, "invalid"), (409, "used"), (410, "expired"),
                                 (418, "denied"), (500, "failed")):
            with self.subTest(status=status):
                self.now = 10
                login, request = self.login(response(status))
                self.now = 15
                self.assertEqual(login.poll(), expected)
                self.assertEqual(login.poll(), expected)
                self.assertEqual(len(request.calls), 2)

    def test_cancel_and_expiry_prevent_requests(self):
        login, request = self.login()
        login.cancel()
        self.now = 100
        self.assertEqual(login.poll(), "cancelled")
        self.assertEqual(len(request.calls), 1)
        login, request = self.login()
        self.now = 160
        self.assertEqual(login.poll(), "expired")
        self.assertEqual(len(request.calls), 1)

    def test_throttle_honors_header_and_expiry(self):
        login, request = self.login(response(429, headers={"Retry-After": "20"}), response(400))
        self.now = 15
        login.poll()
        self.assertEqual(login.next_poll, 35)
        self.now = 34
        login.poll()
        self.assertEqual(len(request.calls), 2)
        self.now = 35
        login.poll()
        self.assertEqual(login.next_poll, 55)
        self.now = 70
        self.assertEqual(login.poll(), "expired")
        self.assertEqual(len(request.calls), 3)

    def test_bad_throttle_header_slows_polling(self):
        for value in ("nan", "-1", "bad", "inf"):
            self.now = 10
            login, unused = self.login(response(429, headers={"retry-after": value}))
            self.now = 15
            login.poll()
            self.assertEqual(login.next_poll, 25)

    def test_invalid_prompt_is_rejected_without_leaking_values(self):
        for changes in ({"interval": 0}, {"expires_in": True},
                        {"verification_url": "https://trakt.tv.evil.example/"},
                        {"verification_url": "http://trakt.tv/activate"},
                        {"verification_url": "https://name:secret@trakt.tv/activate"},
                        {"device_code": "bad\ncode"}):
            request = FakeRequest(response(body=device_body(**changes)))
            login = DeviceLogin(request, "synthetic-client", lambda: self.now)
            with self.assertRaisesRegex(AuthError, "^device_code_failed$"):
                login.begin()
            self.assertEqual(login.state, "failed")

    def test_transport_and_malformed_tokens_fail_closed(self):
        for value in (RuntimeError("synthetic-device-code leaked transport"),
                      response(body={})):
            self.now = 10
            login, request = self.login(value)
            self.now = 15
            self.assertEqual(login.poll(), "failed")
            self.assertNotIn("synthetic", repr(login))
            self.assertIsNone(login.tokens)
            self.assertIsNone(login.prompt)

    def test_sensitive_objects_have_redacted_repr(self):
        login, unused = self.login()
        for value in (repr(login), repr(login.prompt), repr(TokenSet.from_response(token_body()))):
            self.assertNotIn("DEMO-CODE", value)
            self.assertNotIn("synthetic", value)
        with self.assertRaises(AuthError) as caught:
            TokenSet.from_response({"access_token": "secret-invalid"})
        self.assertNotIn("secret-invalid", str(caught.exception))

    def test_cancel_during_request_cannot_authorize_or_fail_cancelled_attempt(self):
        for fail in (False, True):
            login, unused = self.login()
            def request(method, path, body):
                login.cancel()
                if fail:
                    raise RuntimeError("synthetic-sensitive-error")
                return response(body=token_body())
            login._request = request
            self.now = 15
            self.assertEqual(login.poll(), "cancelled")
            self.assertIsNone(login.tokens)
            self.assertIsNone(login.prompt)
            self.now = 10

    def test_cancel_during_code_issuance_discards_prompt(self):
        login = None
        def request(method, path, body):
            login.cancel()
            return response(body=device_body())
        login = DeviceLogin(request, "synthetic-client", lambda: self.now)
        self.assertIsNone(login.begin())
        self.assertEqual(login.state, "cancelled")
        self.assertIsNone(login.prompt)

    def test_token_validation_rejects_bad_fields(self):
        for key, value in (("token_type", "basic"), ("access_token", ""),
                           ("refresh_token", "x\ny"), ("created_at", float("nan")),
                           ("expires_in", True), ("expires_in", -1)):
            body = token_body()
            body[key] = value
            with self.subTest(key=key), self.assertRaises(AuthError):
                TokenSet.from_response(body)


class RefreshTests(unittest.TestCase):
    def test_atomic_rotation_and_stale_generation_no_request(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            store.install(TokenSet.from_response(token_body()))
            generation = store.snapshot().generation
            request = FakeRequest(response(body=token_body("two")))
            tokens = refresh_tokens(store, request, "synthetic-client", "synthetic:registered", generation)
            self.assertEqual(store.snapshot().tokens, tokens)
            self.assertEqual(store.snapshot().generation, generation + 1)
            self.assertIsNone(refresh_tokens(store, request, "synthetic-client", "synthetic:registered", generation))
            self.assertEqual(len(request.calls), 1)
            self.assertNotIn("client_secret", request.calls[0][2])
            self.assertEqual(request.calls[0][2]["redirect_uri"], "synthetic:registered")

    def test_ambiguous_failure_never_retries_consumed_refresh_token(self):
        for failure in (RuntimeError("synthetic-refresh-one"), response(429), response(500),
                        response(body={}), response(body=token_body())):
            with tempfile.TemporaryDirectory() as temp:
                store = TokenStore(temp)
                store.install(TokenSet.from_response(token_body()))
                generation = store.snapshot().generation
                request = FakeRequest(failure)
                with self.assertRaisesRegex(AuthError, "^reauthentication_required$"):
                    refresh_tokens(store, request, "synthetic-client", "synthetic:registered", generation)
                self.assertEqual(store.snapshot().state, "reauth")
                self.assertIsNone(store.snapshot().tokens)
                self.assertIsNone(refresh_tokens(store, request, "synthetic-client", "synthetic:registered", generation))
                self.assertEqual(len(request.calls), 1)

    def test_missing_redirect_configuration_never_consumes_token(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            store.install(TokenSet.from_response(token_body()))
            with self.assertRaises(AuthError):
                refresh_tokens(store, FakeRequest(), "synthetic-client", "", 1)
            self.assertEqual(store.snapshot().state, "ready")

    def test_disconnect_during_refresh_cannot_restore_session(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            store.install(TokenSet.from_response(token_body()))
            def request(method, path, body):
                store.disconnect()
                return response(body=token_body("two"))
            with self.assertRaisesRegex(AuthError, "^reauthentication_required$"):
                refresh_tokens(store, request, "synthetic-client", "synthetic:registered", 1)
            self.assertEqual(store.snapshot().state, "disconnected")
            self.assertIsNone(store.snapshot().tokens)

    def test_storage_failure_does_not_expose_transport_exception(self):
        class BrokenStore:
            def claim_refresh(self, generation):
                return SimpleNamespace(tokens=TokenSet.from_response(token_body()))
            def fail_refresh(self, claim):
                raise RuntimeError("synthetic-store-secret")
        with self.assertRaisesRegex(AuthError, "^reauthentication_required$") as caught:
            refresh_tokens(BrokenStore(), FakeRequest(RuntimeError("synthetic-transport-secret")),
                           "synthetic-client", "synthetic:registered", 1)
        import traceback
        rendered = "".join(traceback.format_exception(type(caught.exception), caught.exception,
                                                      caught.exception.__traceback__))
        self.assertNotIn("synthetic-store-secret", rendered)
        self.assertNotIn("synthetic-transport-secret", rendered)
