"""Token storage tests use temporary profiles and invented credentials only."""
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import AuthError, TokenSet
from resources.lib.trakt_tokens import TokenStore


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

    def test_empty_store_and_disconnect(self):
        with tempfile.TemporaryDirectory() as temp:
            store = TokenStore(temp)
            self.assertEqual(store.snapshot().state, "disconnected")
            self.assertIsNone(store.snapshot().tokens)
            self.assertIsNone(store.claim_refresh(0))
            store.disconnect()
            self.assertEqual(store.snapshot().generation, 1)
