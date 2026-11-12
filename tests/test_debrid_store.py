"""Private provider storage tests use fabricated credentials and real SQLite."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import math
import os
import sqlite3
import stat
import sys
import tempfile
from threading import Barrier
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.debrid_auth import AuthError, Credentials, Tokens
from resources.lib.debrid_store import CredentialStore

CREDENTIALS = Credentials('synthetic-client', 'synthetic-secret')
TOKENS = Tokens('synthetic-access', 'synthetic-refresh', 5000)
ROTATED = Tokens('synthetic-next-access', 'synthetic-next-refresh', 9000)


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
