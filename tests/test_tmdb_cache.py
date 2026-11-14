"""Synthetic artwork cache lifecycle, request bounds and inter-invocation isolation."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.tmdb_artwork import Artwork, ArtworkError
from resources.lib.tmdb_cache import ArtworkCache, FRESH, NEGATIVE, MAX_AGE, MAX_BYTES, MAX_ROWS, LEASE

KEY = ('movie', 7, 'en-US')
ART = Artwork('/SyntheticPoster.jpg', '/SyntheticBackdrop.jpg')


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 2000000000.
        self.cache = ArtworkCache(self.tmp.name, clock=lambda: self.now)

    def reopen(self):
        return ArtworkCache(self.tmp.name, clock=lambda: self.now)

    def test_cold_100_titles_bounded_fill_then_warm_and_restart_no_fetch(self):
        keys = [('movie', i, 'en-US') for i in range(1, 101)]
        calls = []
        def fetch(lookup):
            calls.append(lookup)
            return ART
        self.assertEqual(self.cache.read_many(keys), {})
        for _ in range(5):
            self.assertEqual(self.cache.refresh(keys, fetch), {'attempted': 20, 'stored': 20})
        self.assertEqual(len(calls), 100)
        self.assertEqual(len(set(calls)), 100)
        self.assertEqual(len(self.reopen().read_many(keys)), 100)
        self.assertEqual(self.reopen().refresh(keys, fetch), {'attempted': 0, 'stored': 0})
        self.assertEqual(len(calls), 100)
        self.assertLessEqual((Path(self.tmp.name) / 'tmdb-artwork/paths.sqlite3').stat().st_size, MAX_BYTES)

    def test_fresh_stale_and_hard_expiry_are_not_sliding_on_reads_or_errors(self):
        self.cache.refresh([KEY], lambda _: ART)
        self.now += FRESH - 1
        self.assertFalse(self.cache.read_many([KEY])[KEY].stale)
        self.now += 1
        self.assertTrue(self.cache.read_many([KEY])[KEY].stale)
        def offline(_): raise ArtworkError()
        self.assertEqual(self.cache.refresh([KEY], offline)['stored'], 0)
        self.assertTrue(self.cache.read_many([KEY])[KEY].stale)
        self.now += MAX_AGE - FRESH
        self.assertEqual(self.cache.read_many([KEY]), {})
        with sqlite3.connect(Path(self.tmp.name) / 'tmdb-artwork/paths.sqlite3') as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM artwork').fetchone(), (0,))

    def test_negative_cache_expires_and_language_and_kind_do_not_collide(self):
        keys = [KEY, ('show', 7, 'en-US'), ('movie', 7, 'fr-FR')]
        self.cache.refresh(keys, lambda _: Artwork())
        self.assertEqual(self.cache.read_many(keys), {})
        self.assertEqual(self.cache.refresh(keys, lambda _: ART)['attempted'], 0)
        self.now += NEGATIVE
        self.assertEqual(self.cache.refresh(keys, lambda _: ART)['stored'], 3)
        self.assertEqual(len(self.cache.read_many(keys)), 3)

    def test_failed_refresh_keeps_original_age_and_shared_cooldown(self):
        self.cache.refresh([KEY], lambda _: ART)
        self.now += FRESH
        def limited(_): raise ArtworkError('limited', 120)
        self.cache.refresh([KEY], limited)
        called = []
        self.assertEqual(self.reopen().refresh([('movie', 8, 'en-US')], lambda k: called.append(k)),
                         {'attempted': 0, 'stored': 0})
        self.assertEqual(called, [])
        self.now += 120
        self.assertEqual(self.cache.refresh([KEY], lambda _: ART)['stored'], 1)
        self.assertFalse(self.cache.read_many([KEY])[KEY].stale)

    def test_parallel_readers_do_not_duplicate_fetch_and_clear_invalidates_inflight(self):
        entered, release = threading.Event(), threading.Event()
        def fetch(_):
            entered.set()
            self.assertTrue(release.wait(5))
            return ART
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.cache.refresh, [KEY], fetch)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.reopen().refresh([KEY], lambda _: self.fail('duplicate request'))['attempted'], 0)
                self.assertEqual(self.reopen().read_many([KEY]), {})
                self.reopen().clear()
            finally:
                release.set()
            self.assertEqual(future.result()['stored'], 0)
        self.assertEqual(self.cache.read_many([KEY]), {})

    def test_expired_lease_cannot_overwrite_a_later_refresh(self):
        def old(_):
            self.now += LEASE
            self.assertEqual(self.reopen().refresh([KEY], lambda _: Artwork('/New.jpg'))['stored'], 1)
            return ART
        self.assertEqual(self.cache.refresh([KEY], old)['stored'], 0)
        self.assertEqual(self.cache.read_many([KEY])[KEY].poster, '/New.jpg')

    def test_clock_rollback_invalidates_data_and_holds_network_cooldown(self):
        self.cache.refresh([KEY], lambda _: ART)
        self.now -= 1
        self.assertEqual(self.cache.read_many([KEY]), {})
        self.assertEqual(self.cache.refresh([KEY], lambda _: self.fail('rollback fetch'))['attempted'], 0)
        self.now += 60
        self.assertEqual(self.cache.refresh([KEY], lambda _: ART)['stored'], 1)

    def test_unauthorized_purges_cached_provider_content(self):
        self.cache.refresh([KEY], lambda _: ART)
        def unauthorized(_): raise ArtworkError('unauthorized', 3600)
        self.cache.refresh([('movie', 8, 'en-US')], unauthorized)
        self.assertEqual(self.cache.read_many([KEY]), {})

    def test_cancellation_and_unknown_exception_are_fixed_and_do_not_cache(self):
        self.assertEqual(self.cache.refresh([KEY], lambda _: ART, cancelled=lambda: True)['attempted'], 0)
        def fail(_): raise ValueError('private detail')
        self.assertEqual(self.cache.refresh([KEY], fail), {'attempted': 1, 'stored': 0})
        self.assertEqual(self.cache.read_many([KEY]), {})
        self.assertNotIn(self.tmp.name, repr(self.cache))

    def test_lru_capacity_storage_and_no_private_fields(self):
        keys = [('movie', i, 'en-US') for i in range(1, MAX_ROWS + 1)]
        for start in range(0, len(keys), 20):
            self.cache.refresh(keys[start:start+20], lambda _: ART)
        self.now += 1
        self.cache.read_many([keys[0]])
        self.now += 1
        self.cache.refresh([('movie', MAX_ROWS + 1, 'en-US')], lambda _: ART)
        result = self.cache.read_many(keys)
        self.assertIn(keys[0], result)
        self.assertNotIn(keys[1], result)
        path = Path(self.tmp.name) / 'tmdb-artwork/paths.sqlite3'
        self.assertLessEqual(path.stat().st_size, MAX_BYTES)
        with sqlite3.connect(path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM artwork').fetchone(), (MAX_ROWS,))
            columns = [row[1] for row in conn.execute('PRAGMA table_info(artwork)')]
        self.assertEqual(columns, ['kind', 'ident', 'language', 'poster', 'backdrop', 'checked', 'touched', 'lease', 'until'])

    def test_symlinks_hardlinks_oversized_and_foreign_database_fail_closed(self):
        path = Path(self.tmp.name) / 'tmdb-artwork/paths.sqlite3'
        extra = path.with_name('copy.sqlite3')
        extra.hardlink_to(path)
        with self.assertRaisesRegex(ArtworkError, '^unavailable$'):
            self.reopen()
        extra.unlink()
        path.unlink()
        path.symlink_to(extra)
        with self.assertRaises(ArtworkError): self.reopen()
        path.unlink()
        path.write_bytes(b'x' * (MAX_BYTES + 1))
        path.chmod(0o600)
        with self.assertRaises(ArtworkError): self.reopen()
        path.unlink()
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE foreign_data(value TEXT)')
        path.chmod(0o600)
        with self.assertRaises(ArtworkError): self.reopen()

    def test_abrupt_process_exit_leaves_only_expiring_claim(self):
        root = str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx')
        script = ("import os,sys; sys.path.insert(0,sys.argv[1]); "
                  "from resources.lib.tmdb_cache import ArtworkCache; "
                  "cache=ArtworkCache(sys.argv[2],clock=lambda:float(sys.argv[3])); "
                  "cache._claim(('movie',7,'en-US')); os._exit(0)")
        subprocess.run([sys.executable, '-c', script, root, self.tmp.name, str(self.now)],
                       check=True, timeout=10, capture_output=True)
        self.assertEqual(self.cache.refresh([KEY], lambda _: self.fail('claim active'))['attempted'], 0)
        self.now += LEASE
        self.assertEqual(self.cache.refresh([KEY], lambda _: ART)['stored'], 1)

    def test_late_rate_limit_or_clear_does_not_discard_observed_cooldown(self):
        for clear in (False, True):
            self.now += 1000
            def limited(_):
                self.now += LEASE
                if clear:
                    self.reopen().clear()
                raise ArtworkError('limited', 120)
            self.assertEqual(self.cache.refresh([KEY], limited)['stored'], 0)
            self.assertEqual(self.reopen().refresh([KEY], lambda _: self.fail('ignored late 429'))['attempted'], 0)
            self.now += 119
            self.assertEqual(self.cache.refresh([KEY], lambda _: self.fail('early retry'))['attempted'], 0)
            self.now += 1
            self.assertEqual(self.cache.refresh([KEY], lambda _: ART)['stored'], 1)
            self.cache.clear()

    def test_shorter_late_cooldown_cannot_replace_longer_observed_wait(self):
        def second(_): raise ArtworkError('limited', 120)
        def first(_):
            self.now += LEASE
            self.assertEqual(self.reopen().refresh([KEY], second)['attempted'], 1)
            raise ArtworkError('limited', 10)
        self.cache.refresh([KEY], first)
        self.now += 10
        self.assertEqual(self.cache.refresh([KEY], lambda _: self.fail('shortened cooldown'))['attempted'], 0)
        self.now += 110
        self.assertEqual(self.cache.refresh([KEY], lambda _: ART)['stored'], 1)

    def test_late_unauthorized_purges_content_and_stops_new_attempts(self):
        self.cache.refresh([KEY], lambda _: ART)
        def unauthorized(_):
            self.now += LEASE
            raise ArtworkError('unauthorized', 3600)
        self.cache.refresh([('show', 2, 'en-US')], unauthorized)
        self.assertEqual(self.cache.read_many([KEY]), {})
        self.assertEqual(self.cache.refresh([KEY], lambda _: self.fail('unauthorized retry'))['attempted'], 0)

    def test_warm_refresh_batches_database_work_instead_of_one_commit_per_title(self):
        keys = [('movie', i, 'en-US') for i in range(1, 101)]
        for _ in range(5):
            self.cache.refresh(keys, lambda _: ART)
        with patch.object(self.cache, '_transaction', wraps=self.cache._transaction) as transactions:
            result = self.cache.refresh(keys, lambda _: self.fail('fresh lookup'))
        self.assertEqual(result, {'attempted': 0, 'stored': 0})
        self.assertLessEqual(transactions.call_count, 2)

    def test_long_server_cooldown_is_not_shortened_to_one_hour(self):
        def limited(_): raise ArtworkError('limited', 86400)
        self.cache.refresh([KEY], limited)
        self.now += 3601
        self.assertEqual(self.reopen().refresh([KEY], lambda _: self.fail('early retry'))['attempted'], 0)
        self.now += 86400 - 3601
        self.assertEqual(self.cache.refresh([KEY], lambda _: ART)['stored'], 1)

    def test_cache_content_cannot_supply_arbitrary_urls_or_credentials(self):
        self.cache.refresh([KEY], lambda _: ART)
        path = Path(self.tmp.name) / 'tmdb-artwork/paths.sqlite3'
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE artwork SET poster='https://other.invalid/token'")
        with self.assertRaisesRegex(ArtworkError, '^unavailable$'):
            self.cache.read_many([KEY])
        self.cache.clear()
        self.assertEqual(self.cache.read_many([KEY]), {})
