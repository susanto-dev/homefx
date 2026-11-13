"""Token storage tests use temporary profiles and invented credentials only."""
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_tokens import RefreshClaim, TokenStore


def compete(profile):
    store = TokenStore(profile)
    return store.claim_refresh(1) is not None


class TokenStoreTests(unittest.TestCase):
    def test_cross_process_refresh_has_one_winner(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            store.install(TokenSet("synthetic-access", "synthetic-refresh", 10000))
            with ProcessPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(compete, [temp] * 8))
            self.assertEqual(sum(results), 1)
            self.assertEqual(store.snapshot().state, "refreshing")
            self.assertIsNone(store.snapshot().tokens)

    def test_interrupted_claim_expires_to_reauthentication(self):
        now = [100]
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp, lambda: now[0], claim_ttl=10)
            store.install(TokenSet("synthetic-access", "synthetic-refresh", 10000))
            claim = store.claim_refresh(1)
            reopened = TokenStore(temp, lambda: now[0], claim_ttl=10)
            self.assertIsNone(reopened.claim_refresh(1))
            now[0] = 110
            self.assertEqual(reopened.snapshot().state, "reauth")
            self.assertIsNone(reopened.claim_refresh(1))
            self.assertFalse(store.complete_refresh(claim, TokenSet("new-access", "new-refresh", 11000)))

    def test_disconnect_and_relogin_reject_stale_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            old = TokenSet("synthetic-access", "synthetic-refresh", 10000)
            new = TokenSet("new-access", "new-refresh", 11000)
            store.install(old)
            claim = store.claim_refresh(1)
            store.disconnect()
            self.assertFalse(store.complete_refresh(claim, new))
            self.assertEqual(store.snapshot().state, "disconnected")
            store.install(new)
            store.fail_refresh(claim)
            self.assertEqual(store.snapshot().tokens, new)
            self.assertFalse(store.complete_refresh(claim, old))
            self.assertEqual(store.snapshot().tokens, new)

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_private_permissions_and_no_secrets_in_repr(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            store.install(TokenSet("synthetic-access", "synthetic-refresh", 10000))
            self.assertEqual(stat.S_IMODE((Path(temp) / "trakt").stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((Path(temp) / "trakt/tokens.sqlite3").stat().st_mode), 0o600)
            for value in (repr(store), repr(store.snapshot()), repr(store.claim_refresh(1))):
                self.assertNotIn(temp, value)
                self.assertNotIn("synthetic", value)

    @unittest.skipUnless(os.name == "posix", "POSIX symlinks")
    def test_symlink_storage_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "target").mkdir()
            (root / "trakt").symlink_to(root / "target", target_is_directory=True)
            with self.assertRaisesRegex(AuthError, "^token_store_unavailable$"):
                TokenStore(temp)

    def test_conditional_install_and_disconnect_preserve_newer_account(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            old = TokenSet("synthetic-access", "synthetic-refresh", 10000)
            new = TokenSet("new-access", "new-refresh", 11000)
            self.assertTrue(store.install(old, expected_generation=0))
            self.assertTrue(store.disconnect(expected_generation=1))
            self.assertTrue(store.install(new, expected_generation=2))
            self.assertFalse(store.install(old, expected_generation=2))
            self.assertFalse(store.disconnect(expected_generation=2))
            self.assertEqual(store.snapshot().tokens, new)
            self.assertEqual(store.snapshot().generation, 3)
            with self.assertRaisesRegex(AuthError, "invalid_store_configuration"):
                store.disconnect(expected_generation=True)

    def test_empty_store_and_disconnect(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            self.assertEqual(store.snapshot().state, "disconnected")
            self.assertIsNone(store.snapshot().tokens)
            self.assertIsNone(store.claim_refresh(0))
            store.disconnect()
            self.assertEqual(store.snapshot().generation, 1)


class TokenStoreBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = [100]
        self.store = TokenStore(self.root, lambda: self.now[0], claim_ttl=10)
        self.path = self.root / "trakt/tokens.sqlite3"
        self.tokens = TokenSet("invented-access", "invented-refresh", 1)

    def change(self, sql, parameters=()):
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(sql, parameters)

    def operations(self):
        claim = RefreshClaim("a" * 32, 0, self.tokens)
        return (self.store.snapshot, lambda: self.store.install(self.tokens),
                self.store.disconnect, lambda: self.store.claim_refresh(0),
                lambda: self.store.complete_refresh(claim, self.tokens),
                lambda: self.store.fail_refresh(claim))

    def assert_unchanged_failure(self, operation, code):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(AuthError, "^" + code + "$"):
            operation()
        self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_schema_and_expired_access_remain_refreshable(self):
        # Construct the exact pre-hardening schema independently of TokenStore.
        self.path.unlink()
        self.change("CREATE TABLE credential (id INTEGER PRIMARY KEY CHECK(id=1), "
                    "generation INTEGER NOT NULL, state TEXT NOT NULL, owner TEXT, "
                    "deadline REAL, access TEXT, refresh TEXT, expires REAL)")
        self.change("INSERT INTO credential VALUES(1,7,'ready',NULL,NULL,?,?,1)",
                    (self.tokens.access_token, self.tokens.refresh_token))
        before = self.path.read_bytes()
        reopened = TokenStore(self.root, lambda: 100)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(reopened.snapshot().tokens, self.tokens)
        claim = reopened.claim_refresh(7)
        self.assertEqual(claim.tokens, self.tokens)
        self.assertEqual(reopened.snapshot().state, "refreshing")
        self.assertTrue(reopened.complete_refresh(claim, TokenSet("rotated-a", "rotated-r", 200)))
        self.assertEqual(reopened.snapshot().generation, 8)

    def test_existing_empty_missing_row_and_bad_schema_are_not_initialized(self):
        for damage in ("empty", "missing-row", "missing-table", "extra-column", "garbage"):
            with self.subTest(damage=damage):
                with tempfile.TemporaryDirectory() as temp:
                    TokenStore(temp, lambda: 100)
                    path = Path(temp) / "trakt/tokens.sqlite3"
                    if damage in ("empty", "garbage"):
                        path.write_bytes(b"" if damage == "empty" else b"invented corruption")
                    else:
                        with sqlite3.connect(str(path)) as conn:
                            conn.execute({"missing-row": "DELETE FROM credential",
                                          "missing-table": "DROP TABLE credential",
                                          "extra-column": "ALTER TABLE credential ADD COLUMN unexpected TEXT"}[damage])
                    before = path.read_bytes()
                    with self.assertRaisesRegex(AuthError, "^token_store_(invalid|unavailable)$"):
                        TokenStore(temp, lambda: 100)
                    self.assertEqual(path.read_bytes(), before)

    def test_every_operation_rejects_corrupt_rows_without_changes(self):
        corruptions = (("generation", -1), ("generation", float(2 ** 63)),
                       ("generation", "invented"), ("generation", 0.5),
                       ("state", "invented-secret"), ("owner", "a" * 32),
                       ("deadline", 50), ("access", "invented-secret"),
                       ("refresh", "invented-secret"), ("expires", 100))
        for column, value in corruptions:
            with self.subTest(column=column, value=value):
                self.change("UPDATE credential SET generation=0,state='disconnected',owner=NULL,"
                            "deadline=NULL,access=NULL,refresh=NULL,expires=NULL")
                self.change("UPDATE credential SET " + column + "=?", (value,))
                for operation in self.operations():
                    self.assert_unchanged_failure(operation, "token_store_invalid")
                self.assert_unchanged_failure(lambda: TokenStore(self.root, lambda: 100),
                                              "token_store_invalid")

    def test_ready_and_refreshing_invariants_are_validated_before_expiry(self):
        rows = (("ready", None, None, "", "refresh", 100),
                ("ready", None, None, "access", "refresh", float("inf")),
                ("ready", "a" * 32, None, "access", "refresh", 100),
                ("refreshing", None, 50, None, None, None),
                ("refreshing", "x" * 32, 50, None, None, None),
                ("refreshing", "a" * 32, float("inf"), None, None, None),
                ("refreshing", "a" * 32, float("nan"), None, None, None),
                ("refreshing", "a" * 32, -1, None, None, None),
                ("refreshing", "a" * 32, 50, "secret", None, None))
        for row in rows:
            with self.subTest(row=row):
                self.change("UPDATE credential SET state=?,owner=?,deadline=?,access=?,refresh=?,expires=?", row)
                for operation in self.operations():
                    self.assert_unchanged_failure(operation, "token_store_invalid")

    def test_duplicate_or_wrong_id_is_rejected_without_repair(self):
        for sql in ("INSERT INTO credential(id,generation,state) VALUES(2,0,'disconnected')",
                    "UPDATE credential SET id=2"):
            with self.subTest(sql=sql):
                with sqlite3.connect(str(self.path)) as conn:
                    conn.execute("PRAGMA ignore_check_constraints=ON")
                    conn.execute("DELETE FROM credential WHERE id<>1")
                    if not conn.execute("SELECT 1 FROM credential WHERE id=1").fetchone():
                        conn.execute("INSERT INTO credential(id,generation,state) VALUES(1,0,'disconnected')")
                    conn.execute(sql)
                for operation in self.operations():
                    self.assert_unchanged_failure(operation, "token_store_invalid")

    def test_missing_row_and_changed_schema_fail_on_existing_instance(self):
        self.change("DELETE FROM credential")
        for operation in self.operations():
            self.assert_unchanged_failure(operation, "token_store_invalid")
        self.change("DROP TABLE credential")
        for operation in self.operations():
            self.assert_unchanged_failure(operation, "token_store_invalid")

    def test_bad_clocks_and_ttl_fail_before_filesystem_work(self):
        for clock in (None, False, 4):
            with self.subTest(clock=clock):
                with self.assertRaisesRegex(AuthError, "^invalid_store_configuration$"):
                    TokenStore(self.root / "unused", clock=clock)
        for ttl in (True, 0, 601, float("nan"), float("inf"), "10"):
            with self.subTest(ttl=ttl):
                with self.assertRaisesRegex(AuthError, "^invalid_store_configuration$"):
                    TokenStore(self.root / "unused", claim_ttl=ttl)
        def broken_clock():
            raise RuntimeError("invented secret and private path")
        for clock in (broken_clock,) + tuple(lambda value=value: value for value in
                                            (None, True, "100", -1, float("nan"),
                                             float("inf"), 10 ** 12, 10 ** 1000)):
            with self.subTest(clock=clock):
                with self.assertRaisesRegex(AuthError, "^invalid_store_clock$"):
                    TokenStore(self.root / "unused", clock)
                self.store._clock = clock
                for operation in self.operations():
                    self.assert_unchanged_failure(operation, "invalid_store_clock")
        self.assertFalse((self.root / "unused").exists())

    def test_bad_generation_claim_and_mutated_token_inputs_do_not_write(self):
        for generation in (True, -1, 2 ** 63, 1.0, "0", [], float("nan")):
            for operation in (lambda: self.store.install(self.tokens, generation),
                              lambda: self.store.disconnect(generation),
                              lambda: self.store.claim_refresh(generation)):
                self.assert_unchanged_failure(operation, "invalid_store_configuration")
        damaged = TokenSet("invented-a", "invented-r", 100)
        object.__setattr__(damaged, "expires_at", float("nan"))
        claims = (None, object(), RefreshClaim("bad", 0, self.tokens),
                  RefreshClaim("a" * 32, True, self.tokens),
                  RefreshClaim("a" * 32, 2 ** 63, self.tokens),
                  RefreshClaim("a" * 32, 0, damaged))
        for claim in claims:
            for operation in (lambda: self.store.complete_refresh(claim, self.tokens),
                              lambda: self.store.fail_refresh(claim)):
                self.assert_unchanged_failure(operation, "invalid_store_claim")
        self.assert_unchanged_failure(lambda: self.store.install(damaged), "invalid_token_response")
        self.store.install(self.tokens)
        claim = self.store.claim_refresh(1)
        self.assert_unchanged_failure(lambda: self.store.complete_refresh(claim, damaged),
                                      "invalid_token_response")
        self.assertEqual(self.store.snapshot().state, "refreshing")

    def test_generation_exhaustion_is_atomic_and_stale_callers_stay_stale(self):
        self.change("UPDATE credential SET generation=?", (2 ** 63 - 2,))
        self.assertTrue(self.store.install(self.tokens))
        self.assertEqual(self.store.snapshot().generation, 2 ** 63 - 1)
        self.assertFalse(self.store.install(self.tokens, expected_generation=0))
        self.assertFalse(self.store.disconnect(expected_generation=0))
        for operation in (lambda: self.store.install(self.tokens), self.store.disconnect,
                          lambda: self.store.claim_refresh(2 ** 63 - 1)):
            self.assert_unchanged_failure(operation, "token_store_generation_exhausted")

    def test_deadline_arithmetic_is_bounded(self):
        calls = []
        def clock():
            calls.append(1)
            return 10 ** 12 - 600
        self.store._clock = clock
        self.store._ttl = 600
        self.store.install(self.tokens)
        self.assertEqual(len(calls), 2)
        self.store.claim_refresh(1)
        self.assertEqual(len(calls), 4)
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(conn.execute("SELECT deadline FROM credential").fetchone()[0], 10 ** 12)

    def test_claim_cannot_complete_after_expiring_while_waiting_for_lock(self):
        self.store.install(self.tokens)
        claim = self.store.claim_refresh(1)
        clock_called = threading.Event()
        results = []
        def clock():
            value = self.now[0]
            clock_called.set()
            return value
        def complete():
            try:
                results.append(self.store.complete_refresh(claim, self.tokens))
            except Exception as error:
                results.append(error)
        self.store._clock = clock
        conn = sqlite3.connect(str(self.path))
        try:
            conn.execute("BEGIN IMMEDIATE")
            worker = threading.Thread(target=complete, daemon=True)
            worker.start()
            self.assertTrue(clock_called.wait(2))
            self.now[0] = 111
        finally:
            conn.close()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [False])
        self.assertEqual(self.store.snapshot().state, "reauth")

    def test_reopen_does_not_expire_valid_claim_but_operation_does(self):
        self.store.install(self.tokens)
        self.store.claim_refresh(1)
        before = self.path.read_bytes()
        reopened = TokenStore(self.root, lambda: 110)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(reopened.snapshot().state, "reauth")


@unittest.skipUnless(os.name == "posix", "POSIX filesystem boundaries")
class TokenStorePathTests(unittest.TestCase):
    def assert_rejected_promptly(self, profile):
        # A subprocess timeout bounds special-file regressions without hanging the suite.
        source = ("import sys;sys.path.insert(0,sys.argv[1]);"
                  "from resources.lib.trakt_tokens import TokenStore;"
                  "from resources.lib.trakt_auth import AuthError\n"
                  "try: TokenStore(sys.argv[2])\n"
                  "except AuthError as error: print(str(error))\n")
        addon = Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"
        result = subprocess.run([sys.executable, "-c", source, str(addon), str(profile)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=5, check=True, text=True)
        self.assertEqual(result.stdout.strip(), "token_store_unavailable")
        self.assertEqual(result.stderr, "")

    def test_ancestor_symlinks_do_not_create_or_chmod_outside(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "outside"
            target.mkdir()
            target.chmod(0o755)
            (target / "profile").mkdir()
            (target / "profile").chmod(0o755)
            (root / "alias").symlink_to(target, target_is_directory=True)
            for profile in (root / "alias/profile", root / "alias/missing/profile"):
                self.assert_rejected_promptly(profile)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((target / "profile").stat().st_mode), 0o755)
            self.assertFalse((target / "profile/trakt").exists())
            self.assertFalse((target / "missing").exists())

    def test_files_and_all_sidecars_reject_links_and_special_files(self):
        for suffix in ("", "-journal", "-wal", "-shm"):
            for kind in ("symlink", "dangling", "hardlink", "fifo", "directory"):
                with self.subTest(suffix=suffix, kind=kind):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        (root / "trakt").mkdir()
                        target = root / "outside"
                        target.write_bytes(b"invented outside content")
                        target.chmod(0o640)
                        path = root / ("trakt/tokens.sqlite3" + suffix)
                        if kind == "symlink":
                            path.symlink_to(target)
                        elif kind == "dangling":
                            path.symlink_to(root / "absent")
                        elif kind == "hardlink":
                            os.link(str(target), str(path))
                        elif kind == "fifo":
                            os.mkfifo(str(path), 0o640)
                            path.chmod(0o640)
                        else:
                            path.mkdir(mode=0o750)
                        self.assert_rejected_promptly(root)
                        self.assertEqual(target.read_bytes(), b"invented outside content")
                        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
                        if kind == "fifo":
                            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_every_operation_rechecks_all_paths_and_missing_database(self):
        for suffix in ("", "-journal", "-wal", "-shm"):
            with self.subTest(suffix=suffix):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    store = TokenStore(root, lambda: 100)
                    database = root / "trakt/tokens.sqlite3"
                    original = database.read_bytes()
                    target = root / "outside"
                    target.write_bytes(b"invented outside content")
                    target.chmod(0o640)
                    path = Path(str(database) + suffix)
                    if not suffix:
                        database.unlink()
                    path.symlink_to(target)
                    tokens = TokenSet("invented-a", "invented-r", 100)
                    claim = RefreshClaim("a" * 32, 0, tokens)
                    for operation in (store.snapshot, lambda: store.install(tokens),
                                      store.disconnect, lambda: store.claim_refresh(0),
                                      lambda: store.complete_refresh(claim, tokens),
                                      lambda: store.fail_refresh(claim)):
                        with self.assertRaisesRegex(AuthError, "^token_store_unavailable$"):
                            operation()
                    self.assertEqual(target.read_bytes(), b"invented outside content")
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
                    if suffix:
                        self.assertEqual(database.read_bytes(), original)
                    else:
                        path.unlink()
                        with self.assertRaisesRegex(AuthError, "^token_store_unavailable$"):
                            store.snapshot()
                        self.assertFalse(database.exists())

    def test_sqlite_connection_does_not_recreate_a_removed_database(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp, lambda: 100)
            database = Path(temp) / "trakt/tokens.sqlite3"
            check = store._safe_paths
            def remove_after_check(*args, **kwargs):
                check(*args, **kwargs)
                database.unlink()
            with patch.object(store, "_safe_paths", remove_after_check):
                with self.assertRaisesRegex(AuthError, "^token_store_unavailable$"):
                    store.snapshot()
            self.assertFalse(database.exists())

    def test_post_open_parent_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "profile"
            store = TokenStore(profile, lambda: 100)
            profile.rename(root / "moved")
            profile.symlink_to(root / "moved", target_is_directory=True)
            before = (root / "moved/trakt/tokens.sqlite3").read_bytes()
            with self.assertRaisesRegex(AuthError, "^token_store_unavailable$"):
                store.disconnect()
            self.assertEqual((root / "moved/trakt/tokens.sqlite3").read_bytes(), before)
