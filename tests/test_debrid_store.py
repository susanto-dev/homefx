"""Private provider storage tests use fabricated credentials and real SQLite."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import math
import os
import sqlite3
import stat
import sys
import tempfile
from threading import Barrier, Event, Thread
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.debrid_auth import AuthError, Credentials, Tokens
from resources.lib.debrid_store import CredentialStore, RefreshClaim

CREDENTIALS = Credentials('synthetic-client', 'synthetic-secret')
TOKENS = Tokens('synthetic-access', 'synthetic-refresh', 5000)
ROTATED = Tokens('synthetic-next-access', 'synthetic-next-refresh', 9000)
LEGACY_SCHEMA = ("CREATE TABLE credential (id INTEGER PRIMARY KEY CHECK(id=1), "
                 "generation INTEGER NOT NULL, state TEXT NOT NULL, owner TEXT, "
                 "deadline REAL, client_id TEXT, client_secret TEXT, access TEXT, "
                 "refresh TEXT, expires REAL)")


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name)
        self.clock = [1000]
        self.store = CredentialStore(self.profile, clock=lambda: self.clock[0], claim_ttl=30)
        self.path = self.profile / 'realdebrid' / 'credentials.sqlite3'

    def reopen(self):
        return CredentialStore(self.profile, clock=lambda: self.clock[0], claim_ttl=30)

    @staticmethod
    def operations(store):
        claim = RefreshClaim('a' * 32, 0, CREDENTIALS, TOKENS)
        return (store.snapshot, lambda: store.install(CREDENTIALS, TOKENS), store.disconnect,
                lambda: store.claim_refresh(0), lambda: store.complete_refresh(claim, ROTATED),
                lambda: store.fail_refresh(claim))

    def test_legacy_schema_preserves_credentials_and_expired_access_can_refresh(self):
        self.path.unlink()
        expired = Tokens('synthetic-access', 'synthetic-refresh', 1)
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(LEGACY_SCHEMA)
            conn.execute("INSERT INTO credential VALUES(1,7,'ready',NULL,NULL,?,?,?,?,?)",
                         (CREDENTIALS.client_id, CREDENTIALS.client_secret, expired.access_token,
                          expired.refresh_token, expired.expires_at))
        before = self.path.read_bytes()
        store = self.reopen()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual((store.snapshot().credentials, store.snapshot().tokens), (CREDENTIALS, expired))
        claim = store.claim_refresh(7)
        self.assertEqual((claim.credentials, claim.tokens), (CREDENTIALS, expired))
        self.assertTrue(store.complete_refresh(claim, ROTATED))
        self.assertEqual((store.snapshot().generation, store.snapshot().tokens), (8, ROTATED))

    def test_incompatible_schemas_are_rejected_on_reopen_and_every_operation(self):
        for schema in (LEGACY_SCHEMA.replace('PRIMARY KEY CHECK(id=1)', ''),
                       LEGACY_SCHEMA.replace('generation INTEGER NOT NULL', 'generation INTEGER'),
                       LEGACY_SCHEMA.replace('state TEXT NOT NULL', 'state TEXT'),
                       LEGACY_SCHEMA.replace('expires REAL)', 'expires REAL, extra TEXT)')):
            with self.subTest(schema=schema):
                with sqlite3.connect(str(self.path)) as conn:
                    conn.execute('DROP TABLE credential')
                    conn.execute(schema)
                    conn.execute("INSERT INTO credential(id,generation,state) VALUES(1,0,'disconnected')")
                before = self.path.read_bytes()
                for operation in (self.reopen,) + self.operations(self.store):
                    with self.assertRaisesRegex(AuthError, '^credential_store_invalid$'):
                        operation()
                    self.assertEqual(self.path.read_bytes(), before)

    def test_a_competing_creator_is_not_initialized(self):
        self.path.unlink()
        real_open = os.open
        competed = []
        def open_after_competitor(path, flags, *args, **kwargs):
            if path == str(self.path) and flags & os.O_CREAT and not competed:
                competed.append(True)
                descriptor = real_open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                os.close(descriptor)
            return real_open(path, flags, *args, **kwargs)
        with patch('resources.lib.debrid_store.os.open', side_effect=open_after_competitor):
            with self.assertRaisesRegex(AuthError, '^credential_store_invalid$'):
                self.reopen()
        self.assertEqual(competed, [True])
        self.assertEqual(self.path.read_bytes(), b'')

    def test_rejecting_existing_wal_records_preserves_bytes_and_journal_mode(self):
        for damage in ('schema', 'row'):
            with self.subTest(damage=damage):
                profile = self.profile / damage
                store = CredentialStore(profile, clock=lambda: 1000)
                path = profile / 'realdebrid' / 'credentials.sqlite3'
                conn = sqlite3.connect(str(path))
                try:
                    self.assertEqual(conn.execute('PRAGMA journal_mode=WAL').fetchone(), ('wal',))
                    conn.execute('ALTER TABLE credential ADD COLUMN extra TEXT' if damage == 'schema'
                                 else "UPDATE credential SET state='ready'")
                    conn.commit()
                finally:
                    conn.close()
                before = path.read_bytes()
                for operation in (store.snapshot, lambda: CredentialStore(profile, clock=lambda: 1000)):
                    with self.assertRaisesRegex(AuthError, '^credential_store_invalid$'):
                        operation()
                    self.assertEqual(path.read_bytes(), before)
                    conn = sqlite3.connect(str(path))
                    try:
                        self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone(), ('wal',))
                    finally:
                        conn.close()

    def test_missing_database_is_not_recreated_by_any_operation(self):
        self.path.unlink()
        for operation in self.operations(self.store):
            with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
                operation()
            self.assertFalse(self.path.exists())

    def test_database_removed_after_path_check_is_not_recreated(self):
        check = self.store._safe_paths
        def remove_after_check(*args, **kwargs):
            check(*args, **kwargs)
            self.path.unlink()
        with patch.object(self.store, '_safe_paths', side_effect=remove_after_check):
            with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
                self.store.snapshot()
        self.assertFalse(self.path.exists())

    def test_profile_paths_with_uri_delimiters_roundtrip(self):
        profile = self.profile / 'profile ?#'
        store = CredentialStore(profile, clock=lambda: 1000)
        self.assertTrue(store.install(CREDENTIALS, TOKENS))
        self.assertEqual(CredentialStore(profile, clock=lambda: 1000).snapshot().tokens, TOKENS)

    def test_invalid_profile_paths_have_fixed_errors(self):
        for profile in (None, False, 42):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
                    CredentialStore(profile, clock=lambda: 1000)

    def test_claim_expiring_while_waiting_for_write_lock_cannot_complete(self):
        self.store.install(CREDENTIALS, TOKENS)
        claim = self.store.claim_refresh(1)
        clock_called = Event()
        results = []
        def clock():
            value = self.clock[0]
            clock_called.set()
            return value
        def complete():
            try:
                results.append(self.store.complete_refresh(claim, ROTATED))
            except Exception as error:
                results.append(error)
        self.store._clock = clock
        conn = sqlite3.connect(str(self.path))
        worker = Thread(target=complete, daemon=True)
        try:
            conn.execute('BEGIN IMMEDIATE')
            worker.start()
            self.assertTrue(clock_called.wait(2))
            self.clock[0] = 1030
        finally:
            conn.close()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [False])
        self.assertEqual(self.store.snapshot().state, 'reauth')
        self.assertEqual(self.store.snapshot().tokens, None)

    def test_invalid_post_lock_clock_rolls_back_without_consuming_credentials(self):
        self.store.install(CREDENTIALS, TOKENS)
        before = self.path.read_bytes()
        times = iter((1000, math.nan))
        self.store._clock = lambda: next(times)
        with self.assertRaisesRegex(AuthError, '^invalid_store_clock$'):
            self.store.claim_refresh(1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.reopen().snapshot().tokens, TOKENS)

    def test_roundtrip_permissions_and_provider_isolation(self):
        sentinel = self.profile / 'trakt' / 'tokens.sqlite3'
        sentinel.parent.mkdir()
        sentinel.write_bytes(b'unchanged other provider')
        self.assertEqual(self.store.snapshot().state, 'disconnected')
        self.assertTrue(self.store.install(CREDENTIALS, TOKENS, expected_generation=0))
        value = self.reopen().snapshot()
        self.assertEqual((value.state, value.generation, value.credentials, value.tokens),
                         ('ready', 1, CREDENTIALS, TOKENS))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(sentinel.read_bytes(), b'unchanged other provider')
        self.assertNotIn('synthetic', repr(value))
        self.assertNotIn(self.temp.name, repr(self.store))

    def test_refresh_claim_clears_all_secret_columns_and_rotates_once(self):
        self.store.install(CREDENTIALS, TOKENS)
        claim = self.store.claim_refresh(1)
        self.assertEqual((claim.credentials, claim.tokens), (CREDENTIALS, TOKENS))
        self.assertNotIn('synthetic', repr(claim))
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT client_id,client_secret,access,refresh,expires FROM credential').fetchone(),
                             (None,) * 5)
        snapshot = self.reopen().snapshot()
        self.assertEqual((snapshot.state, snapshot.credentials, snapshot.tokens), ('refreshing', None, None))
        self.assertIsNone(self.reopen().claim_refresh(1))
        self.assertTrue(self.reopen().complete_refresh(claim, ROTATED))
        self.assertFalse(self.store.complete_refresh(claim, TOKENS))
        self.assertFalse(self.store.fail_refresh(claim))
        restored = self.store.snapshot()
        self.assertEqual((restored.generation, restored.credentials, restored.tokens), (2, CREDENTIALS, ROTATED))

    def test_two_instances_compete_for_one_durable_claim(self):
        self.store.install(CREDENTIALS, TOKENS)
        other, barrier = self.reopen(), Barrier(2)
        def claim(store):
            barrier.wait(timeout=5)
            return store.claim_refresh(1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, (self.store, other)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(self.reopen().snapshot().state, 'refreshing')

    def test_abandoned_and_failed_claim_require_new_login(self):
        self.store.install(CREDENTIALS, TOKENS)
        claim = self.store.claim_refresh(1)
        self.clock[0] = 1030
        self.assertEqual(self.reopen().snapshot().state, 'reauth')
        self.assertFalse(self.store.complete_refresh(claim, ROTATED))
        self.assertIsNone(self.store.claim_refresh(1))
        self.store.install(CREDENTIALS, ROTATED, expected_generation=1)
        next_claim = self.store.claim_refresh(2)
        self.assertTrue(self.store.fail_refresh(next_claim))
        self.assertFalse(self.store.fail_refresh(next_claim))
        self.assertEqual(self.reopen().snapshot().state, 'reauth')

    def test_disconnect_and_replacement_win_over_late_completions(self):
        self.store.install(CREDENTIALS, TOKENS)
        claim = self.store.claim_refresh(1)
        self.assertTrue(self.reopen().disconnect(expected_generation=1))
        replacement = Credentials('synthetic-other-client', 'synthetic-other-secret')
        self.store.install(replacement, ROTATED, expected_generation=2)
        self.assertFalse(self.store.install(CREDENTIALS, TOKENS, expected_generation=1))
        self.assertFalse(self.store.disconnect(expected_generation=1))
        self.assertFalse(self.store.complete_refresh(claim, TOKENS))
        self.assertFalse(self.store.fail_refresh(claim))
        self.assertEqual(self.reopen().snapshot().credentials, replacement)
        self.assertTrue(self.store.disconnect(expected_generation=3))
        self.assertEqual(self.reopen().snapshot().tokens, None)

    def test_invalid_clocks_and_configuration_are_fixed_errors(self):
        for invalid in (None, True, -1, math.inf, math.nan, 10 ** 1000, 'private-path'):
            with self.subTest(invalid=repr(invalid)[:20]), self.assertRaisesRegex(AuthError, '^invalid_store_clock$'):
                CredentialStore(self.profile, clock=lambda: invalid)
        for invalid in (True, 0, 601, math.nan, 10 ** 1000):
            with self.subTest(ttl=repr(invalid)[:20]), self.assertRaisesRegex(AuthError, '^invalid_store_configuration$'):
                CredentialStore(self.profile, claim_ttl=invalid)
        self.clock[0] = math.nan
        with self.assertRaisesRegex(AuthError, '^invalid_store_clock$'):
            self.store.install(CREDENTIALS, TOKENS)
        self.clock[0] = 1000
        self.assertEqual(self.store.snapshot().state, 'disconnected')

    def test_invalid_generation_and_claim_cannot_change_store(self):
        self.store.install(CREDENTIALS, TOKENS)
        for value in (True, -1, '1', 10 ** 1000):
            for operation in (lambda: self.store.claim_refresh(value),
                              lambda: self.store.disconnect(value),
                              lambda: self.store.install(CREDENTIALS, TOKENS, value)):
                with self.assertRaisesRegex(AuthError, '^invalid_store_configuration$'):
                    operation()
        with self.assertRaisesRegex(AuthError, '^invalid_store_claim$'):
            self.store.complete_refresh(None, TOKENS)
        self.assertEqual(self.store.snapshot().tokens, TOKENS)

    def test_symlinks_hardlinks_and_nonregular_database_fail_closed(self):
        self.path.unlink()
        target = self.profile / 'private-target'
        target.write_bytes(b'keep')
        target.chmod(0o644)
        for kind in ('symlink', 'hardlink', 'fifo'):
            if kind == 'symlink':
                self.path.symlink_to(target)
            elif kind == 'hardlink':
                os.link(str(target), str(self.path))
            else:
                os.mkfifo(str(self.path))
            with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
                self.reopen()
            self.path.unlink()
            self.assertEqual(target.read_bytes(), b'keep')
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_symlinked_parent_and_journal_fail_closed(self):
        journal = Path(str(self.path) + '-journal')
        target = self.profile / 'private-target'
        target.write_bytes(b'keep')
        journal.symlink_to(target)
        with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
            self.store.snapshot()
        journal.unlink()
        alias = self.profile / 'alias'
        alias.symlink_to(self.profile, target_is_directory=True)
        with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
            CredentialStore(alias)
        self.assertEqual(target.read_bytes(), b'keep')

    def test_corrupt_database_and_invalid_record_are_not_repaired(self):
        self.path.write_bytes(b'private-corrupt-data')
        with self.assertRaisesRegex(AuthError, '^credential_store_unavailable$'):
            self.reopen()
        self.path.unlink()
        self.store = self.reopen()
        for statement in ("UPDATE credential SET state='private-invalid'",
                          "UPDATE credential SET state='ready'",
                          "UPDATE credential SET state='refreshing',deadline=1000"):
            with sqlite3.connect(str(self.path)) as conn:
                conn.execute(statement)
            with self.assertRaisesRegex(AuthError, '^credential_store_invalid$'):
                self.store.snapshot()
            with sqlite3.connect(str(self.path)) as conn:
                conn.execute("UPDATE credential SET state='disconnected',deadline=NULL")
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute('DELETE FROM credential')
        with self.assertRaisesRegex(AuthError, '^credential_store_invalid$'):
            self.store.snapshot()

    def test_missing_record_reopen_and_generation_exhaustion_fail_closed(self):
        self.store.install(CREDENTIALS, TOKENS)
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute('UPDATE credential SET generation=?', (2 ** 63 - 1,))
        self.assertEqual(self.store.snapshot().generation, 2 ** 63 - 1)
        for operation in (lambda: self.store.install(CREDENTIALS, TOKENS),
                          lambda: self.store.disconnect(),
                          lambda: self.store.claim_refresh(2 ** 63 - 1)):
            with self.assertRaisesRegex(AuthError, '^credential_store_generation_exhausted$'):
                operation()
        self.assertEqual(self.store.snapshot().tokens, TOKENS)
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute('DELETE FROM credential')
        with self.assertRaisesRegex(AuthError, '^credential_store_invalid$'):
            self.reopen()
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM credential').fetchone(), (0,))
