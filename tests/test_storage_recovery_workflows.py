"""Exercise private store recovery boundaries through real, inactive services."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.debrid_auth import Credentials, Tokens
from resources.lib.debrid_store import CredentialStore
from resources.lib import service_runtime
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError
from resources.lib.trakt_tokens import TokenStore
from test_trakt_transport import Connections, wire


def response(body):
    return wire(json.dumps(body).encode("utf-8"))


def library_responses():
    return [response({"user": {"ids": {"uuid": "synthetic-account"}}}),
            response([{"ids": {"trakt": 4}, "name": "Synthetic list"}]), response([])]


class StorageRecoveryWorkflows(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = Path(temporary.name)
        self.now = [1000]

    def assemble(self, connections):
        return service_runtime.build_trakt(self.profile, "synthetic-client", "https://example.invalid/callback",
                           clock=lambda: self.now[0], monotonic=lambda: 0,
                           connection_factory=connections)

    def seed(self, expires=5000):
        tokens = TokenStore(self.profile, clock=lambda: self.now[0])
        tokens.install(TokenSet("synthetic-private-access", "synthetic-private-refresh", expires))
        preferences = AccountPreferences(self.profile)
        preferences.save("synthetic-account", ["trakt-list:4"])
        preferences.save("synthetic-other-account", ["trakt-list:8"])
        provider = CredentialStore(self.profile, clock=lambda: self.now[0])
        provider.install(Credentials("synthetic-bound", "synthetic-secret"),
                         Tokens("synthetic-provider-access", "synthetic-provider-refresh", 5000))
        return tokens, preferences, provider

    def assert_private_error(self, error, category):
        self.assertEqual(str(error), category)
        for private in (str(self.profile), "synthetic-private-access", "synthetic-private-refresh",
                        "synthetic-account", "synthetic-invalid-private"):
            self.assertNotIn(private, str(error) + repr(error))

    def test_baseline_sqlite_formats_reopen_through_factory_without_replacement(self):
        # These are the credential and preference schemas shipped before hardening.
        directory = self.profile / "trakt"
        directory.mkdir()
        with sqlite3.connect(str(directory / "tokens.sqlite3")) as conn:
            conn.execute("CREATE TABLE credential (id INTEGER PRIMARY KEY CHECK(id=1), "
                         "generation INTEGER NOT NULL, state TEXT NOT NULL, owner TEXT, "
                         "deadline REAL, access TEXT, refresh TEXT, expires REAL)")
            conn.execute("INSERT INTO credential VALUES(1,17,'ready',NULL,NULL,?,?,5000)",
                         ("synthetic-private-access", "synthetic-private-refresh"))
        preference_path = directory / "preferences.sqlite3"
        account = hashlib.sha256(b"homefx-trakt-account:synthetic-account").hexdigest()
        for version in (1, 2):
            with self.subTest(version=version):
                if preference_path.exists():
                    preference_path.unlink()
                with sqlite3.connect(str(preference_path)) as conn:
                    conn.execute("CREATE TABLE selections (account TEXT PRIMARY KEY, "
                                 "selected TEXT NOT NULL, revision INTEGER NOT NULL)")
                    conn.execute("INSERT INTO selections VALUES(?,?,9)", (account, '["trakt-list:4"]'))
                    if version == 2:
                        conn.execute("CREATE TABLE preference_state (id INTEGER PRIMARY KEY "
                                     "CHECK(id=1), epoch INTEGER NOT NULL CHECK(epoch>=0))")
                        conn.execute("INSERT INTO preference_state VALUES(1,6)")
                    conn.execute("PRAGMA user_version=" + str(version))
                connections = Connections(library_responses())
                bundle = self.assemble(connections)
                self.assertEqual(connections.calls, [])
                self.assertEqual(bundle.session.status(), {"state": "ready", "generation": 17, "login": "idle"})
                self.assertEqual([ref.key for ref in bundle.library.selected_lists()], ["trakt-list:4"])
                self.assertEqual(len(connections.calls), 3)
                self.assertEqual(AccountPreferences(self.profile).snapshot("synthetic-account"),
                                 (0 if version == 1 else 6, ["trakt-list:4"]))
                with sqlite3.connect(str(directory / "tokens.sqlite3")) as conn:
                    self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 0)
                    self.assertEqual([row[1] for row in conn.execute("PRAGMA table_info(credential)")],
                                     ["id", "generation", "state", "owner", "deadline", "access", "refresh", "expires"])

    def test_refresh_rotates_generation_and_restores_account_choices_read_only(self):
        tokens, preferences, provider = self.seed(expires=1010)
        before = tokens.snapshot()
        provider_before = provider.snapshot()
        connections = Connections([response(dict(access_token="synthetic-rotated-access",
            refresh_token="synthetic-rotated-refresh", token_type="bearer", created_at=1000,
            expires_in=3600))] + library_responses())
        bundle = self.assemble(connections)
        self.assertEqual(bundle.session.status()["state"], "refresh_required")
        self.assertEqual(connections.calls, [])
        self.assertEqual([ref.key for ref in bundle.library.selected_lists()], ["trakt-list:4"])
        after = tokens.snapshot()
        self.assertEqual((after.state, after.generation), ("ready", before.generation + 1))
        self.assertEqual(after.tokens.refresh_token, "synthetic-rotated-refresh")
        self.assertEqual(preferences.load("synthetic-other-account"), ["trakt-list:8"])
        self.assertEqual(provider.snapshot(), provider_before)
        self.assertEqual(len(connections.calls), 4)
        mutation = bundle.session.mutate("mark_watched", "movie", 7,
                                        datetime(2026, 11, 13, tzinfo=timezone.utc))
        self.assertEqual((mutation.outcome, mutation.reason), ("failed", "writes_disabled"))
        self.assertEqual(len(connections.calls), 4)

    def test_stale_disconnect_keeps_replacement_generation_and_all_choices(self):
        tokens, preferences, provider = self.seed()
        connections = Connections([])
        bundle = self.assemble(connections)
        old_generation = bundle.session.status()["generation"]
        tokens.install(TokenSet("synthetic-replacement-access", "synthetic-replacement-refresh", 5000))
        replacement, provider_before = tokens.snapshot(), provider.snapshot()
        self.assertFalse(bundle.disconnect(expected_generation=old_generation))
        self.assertEqual(tokens.snapshot(), replacement)
        self.assertEqual(preferences.load("synthetic-account"), ["trakt-list:4"])
        self.assertEqual(preferences.load("synthetic-other-account"), ["trakt-list:8"])
        self.assertTrue(bundle.disconnect(expected_generation=replacement.generation))
        self.assertEqual(tokens.snapshot().generation, replacement.generation + 1)
        self.assertEqual(tokens.snapshot().state, "disconnected")
        self.assertEqual(preferences.load("synthetic-account"), [])
        self.assertEqual(preferences.load("synthetic-other-account"), [])
        self.assertEqual(provider.snapshot(), provider_before)
        self.assertEqual(connections.calls, [])

    def test_malformed_token_state_fails_assembly_without_cleanup_or_requests(self):
        _, preferences, provider = self.seed()
        provider_before = provider.snapshot()
        path = self.profile / "trakt/tokens.sqlite3"
        with sqlite3.connect(str(path)) as conn:
            conn.execute("UPDATE credential SET state='synthetic-invalid-private'")
        retained = path.read_bytes()
        connections = Connections([])
        with self.assertRaises(service_runtime.SetupError) as caught:
            self.assemble(connections)
        self.assert_private_error(caught.exception, "runtime_setup_failed")
        self.assertEqual(path.read_bytes(), retained)
        self.assertEqual(preferences.load("synthetic-account"), ["trakt-list:4"])
        self.assertEqual(preferences.load("synthetic-other-account"), ["trakt-list:8"])
        self.assertEqual(provider.snapshot(), provider_before)
        self.assertEqual(connections.calls, [])

    def test_malformed_preferences_fail_assembly_preserving_credentials_and_other_accounts(self):
        tokens, _, provider = self.seed()
        token_before, provider_before = tokens.snapshot(), provider.snapshot()
        path = self.profile / "trakt/preferences.sqlite3"
        account = hashlib.sha256(b"homefx-trakt-account:synthetic-account").hexdigest()
        with sqlite3.connect(str(path)) as conn:
            conn.execute("UPDATE selections SET selected='synthetic-invalid-private' WHERE account=?", (account,))
        retained = path.read_bytes()
        connections = Connections([])
        with self.assertRaises(service_runtime.SetupError) as caught:
            self.assemble(connections)
        self.assert_private_error(caught.exception, "runtime_setup_failed")
        self.assertEqual(path.read_bytes(), retained)
        self.assertEqual(tokens.snapshot(), token_before)
        self.assertEqual(provider.snapshot(), provider_before)
        with sqlite3.connect(str(path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM selections").fetchone()[0], 2)
        self.assertEqual(connections.calls, [])

    def test_token_sidecar_replacement_after_factory_blocks_session_before_network(self):
        tokens, preferences, provider = self.seed()
        before, provider_before = tokens.snapshot(), provider.snapshot()
        connections = Connections([])
        bundle = self.assemble(connections)
        outside = self.profile / "retained-private-file"
        outside.write_bytes(b"synthetic-private-retained")
        outside.chmod(0o640)
        retained = outside.stat()
        sidecar = self.profile / "trakt/tokens.sqlite3-journal"
        sidecar.symlink_to(outside)
        with self.assertRaises(AuthError) as caught:
            bundle.session.read("settings")
        self.assert_private_error(caught.exception, "token_store_unavailable")
        self.assertEqual(outside.read_bytes(), b"synthetic-private-retained")
        self.assertEqual(outside.stat().st_mode, retained.st_mode)
        self.assertTrue(sidecar.is_symlink())
        self.assertEqual(connections.calls, [])
        sidecar.unlink()
        self.assertEqual(tokens.snapshot(), before)
        self.assertEqual(preferences.load("synthetic-other-account"), ["trakt-list:8"])
        self.assertEqual(provider.snapshot(), provider_before)

    def test_preference_sidecar_replacement_blocks_cached_library_save(self):
        tokens, preferences, provider = self.seed()
        before, provider_before = tokens.snapshot(), provider.snapshot()
        connections = Connections(library_responses())
        bundle = self.assemble(connections)
        self.assertEqual([ref.key for ref in bundle.library.selected_lists()], ["trakt-list:4"])
        outside = self.profile / "retained-private-file"
        outside.write_bytes(b"synthetic-private-retained")
        outside.chmod(0o640)
        retained = outside.stat()
        sidecar = self.profile / "trakt/preferences.sqlite3-wal"
        sidecar.symlink_to(outside)
        with self.assertRaises(PreferencesError) as caught:
            bundle.library.select_lists([])
        self.assert_private_error(caught.exception, "preferences_unavailable")
        self.assertEqual(len(connections.calls), 3)
        self.assertEqual(outside.read_bytes(), b"synthetic-private-retained")
        self.assertEqual(outside.stat().st_mode, retained.st_mode)
        self.assertTrue(sidecar.is_symlink())
        sidecar.unlink()
        self.assertEqual(preferences.load("synthetic-account"), ["trakt-list:4"])
        self.assertEqual(preferences.load("synthetic-other-account"), ["trakt-list:8"])
        self.assertEqual(tokens.snapshot(), before)
        self.assertEqual(provider.snapshot(), provider_before)


if __name__ == "__main__":
    unittest.main()
