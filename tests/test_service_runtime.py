"""Explicit assemblies use temporary stores and fabricated HTTPS only."""
from datetime import datetime, timezone
import importlib
import os
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import service_runtime as runtime
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import ApiError
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.debrid_auth import Credentials, Tokens
from resources.lib.debrid_client import DebridError
from resources.lib.debrid_store import CredentialStore
from resources.lib.request_limits import RequestLimits
from test_trakt_transport import Connections, wire


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / "profile"
        self.now, self.elapsed = [1000], [0]
        self.factory = Connections([])

    def options(self, factory=None):
        return dict(clock=lambda: self.now[0], monotonic=lambda: self.elapsed[0],
                    connection_factory=self.factory if factory is None else factory)

    def trakt(self, **kwargs):
        options = self.options()
        options.update(kwargs)
        return runtime.build_trakt(self.profile, "synthetic-public", "urn:homefx:test", **options)

    def debrid(self, **kwargs):
        options = self.options()
        options.update(kwargs)
        return runtime.build_debrid(self.profile, "synthetic-public", **options)

    def seed(self):
        TokenStore(self.profile, clock=lambda: self.now[0]).install(
            TokenSet("synthetic-access", "synthetic-refresh", 5000))
        CredentialStore(self.profile, clock=lambda: self.now[0]).install(
            Credentials("synthetic-user-client", "synthetic-user-secret"),
            Tokens("synthetic-rd-access", "synthetic-rd-refresh", 5000))

    def test_import_and_construction_never_open_connections_or_authenticate(self):
        with patch.object(runtime.trakt_tokens, "TokenStore") as token, \
                patch.object(runtime.debrid_store, "CredentialStore") as provider:
            importlib.reload(runtime)
            token.assert_not_called()
            provider.assert_not_called()
        trakt, debrid = self.trakt(), self.debrid()
        self.assertEqual(self.factory.calls, [])
        self.assertEqual(trakt.session.status()["state"], "disconnected")
        self.assertEqual(debrid.session.status()["state"], "disconnected")
        for item in (trakt, debrid):
            self.assertNotIn(str(self.profile), repr(item))
            self.assertNotIn("synthetic", repr(item))
        for database in self.profile.rglob("*.sqlite3"):
            self.assertEqual(database.stat().st_mode & 0o777, 0o600)
            self.assertEqual(database.parent.stat().st_mode & 0o777, 0o700)

    def test_invalid_configuration_and_clock_fail_before_storage(self):
        def broken():
            raise ValueError("private synthetic data")
        cases = [dict(clock=lambda: 0), dict(clock=lambda: 10 ** 12 - 3600),
                 dict(clock=lambda: float("nan")), dict(clock=lambda: float("inf")),
                 dict(clock=broken), dict(monotonic=lambda: -1), dict(monotonic=lambda: False),
                 dict(monotonic=broken), dict(cancelled=lambda: "private"), dict(cancelled=broken),
                 dict(connection_factory=None), dict(clock=None), dict(cancelled=lambda: True)]
        for kwargs in cases:
            for build in (self.trakt, self.debrid):
                with self.subTest(kwargs=kwargs, provider=build.__name__):
                    with self.assertRaises(runtime.SetupError) as error:
                        build(**kwargs)
                    self.assertNotIn("private", str(error.exception))
                    self.assertFalse(self.profile.exists())
        for client in (None, "", "contains space", "x" * 257):
            with self.assertRaises(runtime.SetupError):
                runtime.build_trakt(self.profile, client, "urn:homefx:test", **self.options())
            with self.assertRaises(runtime.SetupError):
                runtime.build_debrid(self.profile, client, **self.options())
        for uri in ("relative", "", "https://", "https://user:secret@example.invalid", "urn:test#secret",
                    "https://example.invalid/a b", "https://example.invalid/%ZZ",
                    "https://example.invalid/partial%", "https://example.invalid/a\\b"):
            with self.assertRaises(runtime.SetupError):
                runtime.build_trakt(self.profile, "synthetic", uri, **self.options())
        with self.assertRaises(runtime.SetupError):
            self.debrid(pending_response="not trusted code")
        self.assertFalse(self.profile.exists())
        self.assertEqual(self.factory.calls, [])

    def test_registered_custom_or_https_redirect_syntax_is_not_a_network_target(self):
        for uri in ("urn:ietf:wg:oauth:2.0:oob", "homefx://callback", "https://example.invalid/callback",
                    "https://example.invalid/a%20b?value=%2F"):
            bundle = runtime.build_trakt(self.profile, "synthetic-public", uri, **self.options())
            self.assertEqual(bundle.session.status()["state"], "disconnected")
        self.assertEqual(self.factory.calls, [])

    def test_unsafe_profile_and_existing_files_fail_without_touching_targets(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        self.profile.symlink_to(outside, target_is_directory=True)
        for build in (self.trakt, self.debrid):
            with self.assertRaises(runtime.SetupError):
                build()
        self.assertEqual(list(outside.iterdir()), [])
        self.profile.unlink()
        (self.profile / "trakt").mkdir(parents=True)
        original = outside / "private"
        original.write_bytes(b"synthetic private bytes")
        target = self.profile / "trakt" / "tokens.sqlite3"
        os.link(original, target)
        with self.assertRaises(runtime.SetupError):
            self.trakt()
        self.assertEqual(original.read_bytes(), b"synthetic private bytes")
        self.assertFalse((self.profile / "limits").exists())
        target.unlink()
        os.mkfifo(target)
        with self.assertRaises(runtime.SetupError):
            self.trakt()
        self.assertFalse((self.profile / "limits").exists())
        with self.assertRaises(runtime.SetupError):
            runtime.build_debrid("relative", "synthetic", **self.options())

    def test_shared_provider_budget_and_provider_isolation_use_actual_transport(self):
        self.seed()
        limits = RequestLimits(self.profile, "realdebrid", clock=lambda: self.now[0])
        for _ in range(249):
            self.assertEqual(limits.reserve(), 0)
        response = wire(b'{"type":"premium","premium":3600,"expiration":"2030-01-01T00:00:00Z"}')
        factory = Connections([response])
        self.debrid(connection_factory=factory).session.account()
        with self.assertRaises(DebridError) as error:
            self.debrid().session.account()
        self.assertEqual(error.exception.kind, "rate_limit")
        self.assertEqual(self.factory.calls, [])
        other = Connections([wire(b"[]")])
        self.assertEqual(self.trakt(connection_factory=other).session.read("watched_movies"), ())
        context = other.calls[0][1]["context"]
        self.assertIs(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.now[0] += 60
        self.debrid(connection_factory=Connections([response])).session.account()

    def test_trakt_cooldown_is_shared_between_assemblies_and_expires(self):
        self.seed()
        factory = Connections([wire(status=429, headers=[("Retry-After", "60")])])
        first = self.trakt(connection_factory=factory)
        with self.assertRaises(ApiError) as error:
            first.session.read("watched_movies")
        self.assertEqual(error.exception.kind, "rate_limit")
        with self.assertRaises(ApiError):
            self.trakt().session.read("watched_movies")
        self.assertEqual(self.factory.calls, [])
        self.now[0] += 61
        self.assertEqual(self.trakt(connection_factory=Connections([wire(b"[]")])).session.read("watched_movies"), ())

    def test_disconnect_clears_trakt_choices_but_not_provider_and_writes_stay_disabled(self):
        self.seed()
        preferences = AccountPreferences(self.profile)
        preferences.save("synthetic-account", ["trakt-list:1"])
        bundle, other = self.trakt(), self.debrid()
        generation = bundle.session.status()["generation"]
        bundle.library._cache.put("test-entry", {"value": "synthetic"})
        self.assertFalse(bundle.disconnect(expected_generation=generation + 1))
        self.assertEqual(preferences.load("synthetic-account"), ["trakt-list:1"])
        result = bundle.session.mutate("mark_watched", "movie", 1, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(result.reason, "writes_disabled")
        self.assertTrue(bundle.disconnect(expected_generation=generation))
        self.assertEqual(preferences.load("synthetic-account"), [])
        self.assertEqual(bundle.library._cache.get("test-entry"), (False, None))
        self.assertEqual(bundle.session.status()["state"], "disconnected")
        self.assertEqual(other.session.status()["state"], "ready")
        self.assertTrue(other.disconnect(expected_generation=other.session.status()["generation"]))
        self.assertEqual(self.factory.calls, [])

    def test_setup_failures_are_fixed_without_credential_or_path_disclosure(self):
        with patch.object(runtime.trakt_preferences, "AccountPreferences", side_effect=OSError("private-path-secret")):
            with self.assertRaisesRegex(runtime.SetupError, "^runtime_setup_failed$"):
                self.trakt()
        self.assertEqual(self.factory.calls, [])
        self.assertEqual(TokenStore(self.profile).snapshot().state, "disconnected")
