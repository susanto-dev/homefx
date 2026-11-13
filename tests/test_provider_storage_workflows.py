"""Service assemblies fail closed on damaged local stores, using fabricated HTTPS."""
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.debrid_auth import Credentials, Tokens
from resources.lib.debrid_client import DebridError
from resources.lib.debrid_store import CredentialStore
from resources.lib.playback import PlaybackAttempt, PlaybackResult
from resources.lib.request_limits import RequestLimits
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import ApiError
from resources.lib.trakt_tokens import TokenStore
from test_trakt_transport import Connections, wire


def response(body):
    return wire(json.dumps(body).encode("utf-8"))


class ProviderStorageWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = Path(temporary.name) / "profile"
        self.now = 1000
        self.network = Connections([])
        # Another test reloads this module. Resolve its exception classes and
        # factory functions together rather than retaining stale imported types.
        self.runtime = importlib.import_module("resources.lib.service_runtime")

    def build(self, provider, network=None):
        options = dict(clock=lambda: self.now, monotonic=lambda: 0,
                       connection_factory=self.network if network is None else network)
        if provider == "trakt":
            return self.runtime.build_trakt(self.profile, "synthetic-public",
                                             "urn:homefx:test", **options)
        return self.runtime.build_debrid(self.profile, "synthetic-public", **options)

    def seed(self, expires=5000):
        trakt = TokenStore(self.profile, clock=lambda: self.now)
        trakt.install(TokenSet("synthetic-trakt-access", "synthetic-trakt-refresh", 5000))
        debrid = CredentialStore(self.profile, clock=lambda: self.now)
        debrid.install(Credentials("synthetic-bound-client", "synthetic-bound-secret"),
                       Tokens("synthetic-rd-access", "synthetic-rd-refresh", expires))
        return trakt, debrid

    def test_weakened_credential_schema_fails_without_changing_other_provider(self):
        self.seed()
        database = self.profile / "realdebrid" / "credentials.sqlite3"
        with sqlite3.connect(str(database)) as connection:
            connection.execute("ALTER TABLE credential RENAME TO old_credential")
            connection.execute("CREATE TABLE credential (id INTEGER, generation INTEGER, "
                               "state TEXT, owner TEXT, deadline REAL, client_id TEXT, "
                               "client_secret TEXT, access TEXT, refresh TEXT, expires REAL)")
            connection.execute("INSERT INTO credential SELECT * FROM old_credential")
            connection.execute("DROP TABLE old_credential")
        before = hashlib.sha256(database.read_bytes()).digest()
        with self.assertRaisesRegex(self.runtime.SetupError, "^runtime_setup_failed$"):
            self.build("realdebrid")
        self.assertEqual(hashlib.sha256(database.read_bytes()).digest(), before)
        self.assertEqual(self.network.calls, [])
        # The other provider's valid store can still be assembled and read.
        trakt = self.build("trakt", Connections([wire(b"[]")]))
        self.assertEqual(trakt.session.read("watched_movies"), ())

    def test_weakened_limit_schema_blocks_both_service_factories_without_repair(self):
        self.seed()
        RequestLimits(self.profile, "trakt", clock=lambda: self.now)
        database = self.profile / "limits" / "requests.sqlite3"
        with sqlite3.connect(str(database)) as connection:
            connection.execute("ALTER TABLE state RENAME TO old_state")
            connection.execute("CREATE TABLE state (provider TEXT, cooldown REAL, last REAL)")
            connection.execute("INSERT INTO state SELECT * FROM old_state")
            connection.execute("DROP TABLE old_state")
        before = hashlib.sha256(database.read_bytes()).digest()
        for provider in ("trakt", "realdebrid"):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(self.runtime.SetupError, "^runtime_setup_failed$"):
                    self.build(provider)
                self.assertEqual(hashlib.sha256(database.read_bytes()).digest(), before)
        self.assertEqual(self.network.calls, [])

    def test_deleted_shared_limits_block_existing_sessions_and_player_without_recreation(self):
        self.seed()
        trakt, debrid = self.build("trakt"), self.build("realdebrid")
        generation = debrid.session.current_generation()
        database = self.profile / "limits" / "requests.sqlite3"
        database.unlink()
        dispatched = []
        attempt = PlaybackAttempt(debrid.session.unrestrict,
            lambda *args: dispatched.append(args), lambda: False,
            debrid.session.current_generation, generation, clock=lambda: 0)
        self.assertEqual(attempt.run({"kind": "movie", "trakt_id": 10},
                                    "https://host.example/synthetic-source"),
                         PlaybackResult.RESOLVE_FAILED)
        with self.assertRaises(ApiError):
            trakt.session.read("watched_movies")
        self.assertEqual(dispatched, [])
        self.assertEqual(self.network.calls, [])
        self.assertFalse(database.exists())
        self.assertEqual(list(database.parent.iterdir()), [])

    def test_deleted_credentials_block_existing_playback_before_network_or_dispatch(self):
        self.seed()
        bundle = self.build("realdebrid")
        generation = bundle.session.current_generation()
        database = self.profile / "realdebrid" / "credentials.sqlite3"
        database.unlink()
        dispatched = []
        attempt = PlaybackAttempt(bundle.session.unrestrict,
            lambda *args: dispatched.append(args), lambda: False,
            bundle.session.current_generation, generation, clock=lambda: 0)
        self.assertEqual(attempt.run({"kind": "movie", "trakt_id": 10},
                                    "https://host.example/synthetic-source"),
                         PlaybackResult.STATE_UNAVAILABLE)
        self.assertEqual(dispatched, [])
        self.assertEqual(self.network.calls, [])
        self.assertFalse(database.exists())
        self.assertEqual(list(database.parent.iterdir()), [])

    def test_baseline_refresh_retains_identity_and_issued_budget_across_reassembly(self):
        trakt_store, debrid_store = self.seed(expires=1020)
        trakt_before = trakt_store.snapshot()
        credentials = debrid_store.snapshot().credentials
        limits = RequestLimits(self.profile, "realdebrid", clock=lambda: self.now)
        for _ in range(248):
            self.assertEqual(limits.reserve(), 0)
        network = Connections([
            response(dict(access_token="synthetic-rotated", refresh_token="synthetic-next",
                          expires_in=3600, token_type="Bearer")),
            response(dict(type="premium", premium=3600, expiration="2030-01-01T00:00:00Z")),
        ])
        first = self.build("realdebrid", network)
        self.assertEqual(first.session.account().type, "premium")
        after = debrid_store.snapshot()
        self.assertEqual(after.credentials, credentials)
        self.assertEqual(after.tokens.access_token, "synthetic-rotated")
        self.assertEqual(after.generation, 2)
        self.assertEqual(trakt_store.snapshot(), trakt_before)
        self.assertEqual(len(network.calls), 2)
        sent = [b"".join(sock.sent) for sock in network.sockets]
        self.assertIn(b"client_id=synthetic-bound-client", sent[0])
        self.assertIn(b"client_secret=synthetic-bound-secret", sent[0])
        self.assertIn(b"Authorization: Bearer synthetic-rotated", sent[1])
        # Both refresh and REST consumed the remaining two attempts. Reopening or
        # disconnecting one account must not reset the shared provider budget.
        second = self.build("realdebrid")
        with self.assertRaises(DebridError) as error:
            second.session.account()
        self.assertEqual(error.exception.kind, "rate_limit")
        self.assertTrue(second.disconnect(expected_generation=2))
        self.assertGreater(limits.reserve(), 0)
        self.assertEqual(self.network.calls, [])
        self.assertEqual(self.build("trakt", Connections([wire(b"[]")]))
                         .session.read("watched_movies"), ())
        self.assertEqual(trakt_store.snapshot(), trakt_before)

    def test_baseline_cooldown_survives_factory_reopen_and_other_provider_refresh(self):
        self.seed(expires=1020)
        limits = RequestLimits(self.profile, "trakt", clock=lambda: self.now)
        limits.observe(429, {"Retry-After": "60"})
        network = Connections([
            response(dict(access_token="synthetic-rotated", refresh_token="synthetic-next",
                          expires_in=3600, token_type="Bearer")),
            response(dict(type="premium", premium=3600, expiration="2030-01-01T00:00:00Z")),
        ])
        self.assertEqual(self.build("realdebrid", network).session.account().type, "premium")
        with self.assertRaises(ApiError) as error:
            self.build("trakt").session.read("watched_movies")
        self.assertEqual(error.exception.kind, "rate_limit")
        self.assertEqual(self.network.calls, [])
        self.now = 1061
        self.assertEqual(self.build("trakt", Connections([wire(b"[]")]))
                         .session.read("watched_movies"), ())
        self.assertEqual(len(network.calls), 2)
