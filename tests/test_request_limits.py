"""Offline limits tests use synthetic clocks and private temporary SQLite files."""
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from pathlib import Path
import os
import sqlite3
import stat
import sys
import tempfile
from threading import Barrier, Event
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.request_limits import LimitError, RequestLimits


class RequestLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name)
        self.now = [1000]
        self.rd = self.open('realdebrid')
        self.path = self.profile / 'limits/requests.sqlite3'

    def open(self, provider):
        return RequestLimits(self.profile, provider, clock=lambda: self.now[0])

    def query(self, sql, parameters=()):
        with sqlite3.connect(str(self.path)) as connection:
            return connection.execute(sql, parameters).fetchall()

    def test_rolling_window_counts_issued_attempts_and_blocks_without_extension(self):
        for _ in range(250):
            self.assertEqual(self.rd.reserve(), 0)
        self.assertEqual(self.rd.reserve(), 60)
        for _ in range(5):
            self.assertEqual(self.open('realdebrid').reserve(), 60)
        self.assertEqual(self.query('SELECT COUNT(*) FROM issued'), [(250,)])
        self.now[0] = 1059.1
        self.assertEqual(self.rd.reserve(), 1)
        self.now[0] = 1060
        self.assertEqual(self.rd.reserve(), 0)
        self.assertEqual(self.query('SELECT stamp FROM issued'), [(1060,)])

    def test_two_instances_atomically_reserve_last_slot(self):
        for _ in range(249):
            self.rd.reserve()
        other, barrier = self.open('realdebrid'), Barrier(2)
        def reserve(limits):
            barrier.wait(timeout=5)
            return limits.reserve()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, (self.rd, other)))
        self.assertEqual(sorted(results), [0, 60])
        self.assertEqual(self.query('SELECT COUNT(*) FROM issued'), [(250,)])

    def test_cooldown_survives_restart_and_does_not_shorten_or_reset(self):
        self.rd.observe(429, {'Retry-After': '120'})
        self.assertEqual(self.open('realdebrid').reserve(), 120)
        self.now[0] = 1010
        self.rd.observe(429, {'retry-after': '1'})
        self.rd.observe(200, {})
        self.assertEqual(self.open('realdebrid').reserve(), 110)
        self.assertEqual(self.query('SELECT COUNT(*) FROM issued'), [(0,)])
        self.now[0] = 1120
        self.assertEqual(self.rd.reserve(), 0)

    def test_provider_isolation_and_no_guessed_trakt_numeric_quota(self):
        trakt = self.open('trakt')
        self.rd.observe(429, {'retry-after': '40'})
        for _ in range(255):
            self.assertEqual(trakt.reserve(), 0)
        self.assertEqual(self.query('SELECT COUNT(*) FROM issued'), [(0,)])
        trakt.observe(429, {'retry-after': '90'})
        self.assertEqual(self.rd.reserve(), 40)
        self.assertEqual(self.open('trakt').reserve(), 90)
        self.now[0] = 1040
        self.assertEqual(self.rd.reserve(), 0)
        self.assertEqual(trakt.reserve(), 50)

    def test_retry_after_defaults_dates_and_bounds(self):
        cases = [({}, 60), ({'Retry-After': 'garbage'}, 60),
                 ({'Retry-After': '-4'}, 1), ({'Retry-After': '0'}, 1),
                 ({'Retry-After': '9' * 100}, 3600),
                 ({'Retry-After': '9' * 129}, 3600),
                 ({'Retry-After': True}, 60), ({'Retry-After': []}, 60),
                 ({'Retry-After': '1', 'retry-after': '2'}, 60),
                 ({'rEtRy-AfTeR': formatdate(1101, usegmt=True)}, 101),
                 ({'Retry-After': formatdate(999, usegmt=True)}, 1)]
        for headers, delay in cases:
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as profile:
                limits = RequestLimits(profile, 'trakt', clock=lambda: 1000)
                limits.observe(429, headers)
                self.assertEqual(limits.reserve(), delay)

    def test_long_server_cooldown_is_preserved_while_returned_wait_is_bounded(self):
        for raw in ('7200', formatdate(8200, usegmt=True), '9' * 5000, 10 ** 5000):
            with self.subTest(kind=type(raw).__name__), tempfile.TemporaryDirectory() as profile:
                now = [1000]
                limits = RequestLimits(profile, 'trakt', clock=lambda: now[0])
                limits.observe(429, {'Retry-After': raw})
                self.assertEqual(limits.reserve(), 3600)
                now[0] = 4600
                self.assertEqual(limits.reserve(), 3600)
                now[0] = 8199
                self.assertGreater(limits.reserve(), 0)
                if raw in ('7200', formatdate(8200, usegmt=True)):
                    now[0] = 8200
                    self.assertEqual(limits.reserve(), 0)

    def test_bad_or_backwards_clock_fails_closed_without_counting(self):
        self.rd.reserve()
        for bad in (999, -1, True, float('nan'), float('inf'), '1000', 10 ** 1000):
            self.now[0] = bad
            with self.subTest(value=type(bad).__name__):
                with self.assertRaisesRegex(LimitError, '^invalid_limit_clock$'):
                    self.rd.reserve()
        def broken_clock():
            raise RuntimeError('synthetic private details')
        other = RequestLimits(self.profile, 'realdebrid', clock=broken_clock)
        with self.assertRaisesRegex(LimitError, '^invalid_limit_clock$'):
            other.observe(429, {})
        self.assertEqual(self.query('SELECT COUNT(*) FROM issued'), [(1,)])
        self.now[0] = 1000
        self.assertEqual(self.rd.reserve(), 0)

    def test_corrupted_rows_fail_closed_instead_of_resetting(self):
        changes = ["DELETE FROM state WHERE provider='trakt'",
                   "UPDATE state SET last=-1 WHERE provider='realdebrid'",
                   "UPDATE state SET cooldown=1000000000001 WHERE provider='trakt'",
                   "INSERT INTO issued VALUES ('trakt',0)",
                   "INSERT INTO issued VALUES ('realdebrid',9999)"]
        for sql in changes:
            with self.subTest(sql=sql), tempfile.TemporaryDirectory() as profile:
                limits = RequestLimits(profile, 'realdebrid', clock=lambda: 1000)
                path = Path(profile) / 'limits/requests.sqlite3'
                with sqlite3.connect(str(path)) as connection:
                    connection.execute(sql)
                with self.assertRaisesRegex(LimitError, '^limit_store_invalid$'):
                    limits.reserve()
                with self.assertRaisesRegex(LimitError, '^limit_store_invalid$'):
                    RequestLimits(profile, 'realdebrid', clock=lambda: 1000)
        with sqlite3.connect(str(self.path)) as connection:
            connection.executemany('INSERT INTO issued VALUES (?,?)', [('realdebrid', 0)] * 251)
        with self.assertRaisesRegex(LimitError, '^limit_store_invalid$'):
            self.rd.reserve()

    def test_existing_empty_or_invalid_database_is_not_reinitialized(self):
        for data in (b'', b'not a database'):
            with tempfile.TemporaryDirectory() as profile:
                path = Path(profile) / 'limits/requests.sqlite3'
                path.parent.mkdir()
                path.write_bytes(data)
                with self.assertRaisesRegex(LimitError, '^limit_store_unavailable$'):
                    RequestLimits(profile, 'trakt')
                self.assertEqual(path.read_bytes(), data)

    def test_deleted_database_is_not_recreated_by_later_operations(self):
        self.rd.observe(429, {'Retry-After': '120'})
        self.path.unlink()
        for operation in (self.rd.reserve, lambda: self.rd.observe(429, {})):
            with self.assertRaisesRegex(LimitError, '^limit_store_unavailable$'):
                operation()
            self.assertFalse(self.path.exists())
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_competing_creation_does_not_initialize_an_existing_empty_file(self):
        with tempfile.TemporaryDirectory() as profile:
            path = Path(profile) / 'limits/requests.sqlite3'
            real_open = os.open
            inserted = []

            def open_after_competing_creation(name, flags, *args):
                if str(name) == str(path) and not inserted:
                    path.write_bytes(b'')
                    inserted.append(True)
                return real_open(name, flags, *args)

            with patch('resources.lib.request_limits.os.open', side_effect=open_after_competing_creation):
                with self.assertRaisesRegex(LimitError, '^limit_store_unavailable$'):
                    RequestLimits(profile, 'trakt')
            self.assertEqual(inserted, [True])
            self.assertEqual(path.read_bytes(), b'')

    def test_incompatible_schemas_fail_before_reservations_or_cooldown_writes(self):
        changes = [
            ('ALTER TABLE state RENAME TO old_state',
             'CREATE TABLE state (provider TEXT, cooldown REAL NOT NULL, last REAL NOT NULL)',
             'INSERT INTO state SELECT * FROM old_state'),
            ('ALTER TABLE issued RENAME TO old_issued',
             'CREATE VIEW issued AS SELECT provider,stamp FROM old_issued'),
            ('ALTER TABLE issued ADD COLUMN unrelated TEXT',),
        ]
        for statements in changes:
            with self.subTest(statements=statements), tempfile.TemporaryDirectory() as profile:
                limits = RequestLimits(profile, 'realdebrid', clock=lambda: 1000)
                limits.reserve()
                limits.observe(429, {'Retry-After': '120'})
                path = Path(profile) / 'limits/requests.sqlite3'
                with sqlite3.connect(str(path)) as connection:
                    for sql in statements:
                        connection.execute(sql)
                before = path.read_bytes()
                for operation in (limits.reserve, lambda: limits.observe(429, {}),
                                  lambda: RequestLimits(profile, 'realdebrid')):
                    with self.assertRaisesRegex(LimitError, '^limit_store_invalid$'):
                        operation()
                    self.assertEqual(path.read_bytes(), before)

    def test_waiting_reservation_samples_clock_after_write_lock(self):
        self.rd.observe(429, {'Retry-After': '10'})
        entered = Event()
        sampled = []
        real_connect = self.rd._connect

        class Connection:
            def __init__(self, connection):
                self.connection = connection

            def execute(self, sql, *args):
                if sql == 'BEGIN IMMEDIATE':
                    entered.set()
                return self.connection.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(self.connection, name)

        def clock():
            sampled.append(self.now[0])
            return self.now[0]

        self.rd._clock = clock
        blocker = sqlite3.connect(str(self.path))
        self.addCleanup(blocker.close)
        blocker.execute('BEGIN IMMEDIATE')
        with patch.object(self.rd, '_connect', side_effect=lambda: Connection(real_connect())):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self.rd.reserve)
                try:
                    self.assertTrue(entered.wait(timeout=1))
                    self.assertEqual(sampled, [])
                    self.now[0] = 1010
                finally:
                    blocker.rollback()
                self.assertEqual(pending.result(timeout=5), 0)
        self.assertEqual(sampled, [1010])
        self.assertEqual(self.query('SELECT stamp FROM issued'), [(1010,)])

    def test_private_permissions_and_minimal_persisted_fields(self):
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual([row[1] for row in self.query('PRAGMA table_info(state)')],
                         ['provider', 'cooldown', 'last'])
        self.assertEqual([row[1] for row in self.query('PRAGMA table_info(issued)')],
                         ['provider', 'stamp'])
        self.assertNotIn(self.temp.name, repr(self.rd))
        self.assertEqual(list(self.profile.iterdir()), [self.path.parent])

    def test_unsafe_symlink_hardlink_and_special_paths_fail_closed(self):
        for kind in ('directory', 'database', 'journal', 'hardlink', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as profile:
                root = Path(profile)
                directory = root / 'limits'
                target = root / 'target'
                target.write_bytes(b'unchanged')
                if kind == 'directory':
                    directory.symlink_to(root, target_is_directory=True)
                else:
                    directory.mkdir()
                    path = directory / 'requests.sqlite3'
                    if kind == 'database':
                        path.symlink_to(target)
                    elif kind == 'journal':
                        Path(str(path) + '-journal').symlink_to(target)
                    elif kind == 'hardlink':
                        os.link(str(target), str(path))
                    else:
                        os.mkfifo(str(path))
                with self.assertRaisesRegex(LimitError, '^limit_store_unavailable$'):
                    RequestLimits(root, 'trakt')
                self.assertEqual(target.read_bytes(), b'unchanged')

    def test_later_unsafe_database_and_sidecars_leave_existing_data_untouched(self):
        for suffix in ('', '-journal', '-wal', '-shm'):
            for kind in ('symlink', 'hardlink', 'fifo', 'directory'):
                with self.subTest(suffix=suffix, kind=kind), tempfile.TemporaryDirectory() as profile:
                    limits = RequestLimits(profile, 'realdebrid', clock=lambda: 1000)
                    limits.reserve()
                    path = Path(profile) / 'limits/requests.sqlite3'
                    original = path.read_bytes()
                    unsafe = Path(str(path) + suffix)
                    if suffix == '':
                        path.unlink()
                    target = Path(profile) / 'target'
                    target.write_bytes(b'unchanged')
                    target.chmod(0o640)
                    if kind == 'symlink':
                        unsafe.symlink_to(target)
                    elif kind == 'hardlink':
                        os.link(str(target), str(unsafe))
                    elif kind == 'fifo':
                        os.mkfifo(str(unsafe))
                    else:
                        unsafe.mkdir()
                    for operation in (limits.reserve, lambda: limits.observe(429, {})):
                        with self.assertRaisesRegex(LimitError, '^limit_store_unavailable$'):
                            operation()
                    self.assertEqual(target.read_bytes(), b'unchanged')
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)
                    if suffix:
                        self.assertEqual(path.read_bytes(), original)

    def test_configuration_and_response_validation(self):
        for provider in ('other', '', None, []):
            with self.assertRaisesRegex(LimitError, '^invalid_limit_configuration$'):
                RequestLimits(self.profile, provider)
        with patch('resources.lib.request_limits.os.name', 'nt'):
            with self.assertRaisesRegex(LimitError, '^limit_store_platform_unsupported$'):
                RequestLimits(self.profile, 'trakt')
        for status, headers in ((True, {}), (99, {}), (600, {}), (429, [])):
            with self.assertRaisesRegex(LimitError, '^invalid_limit_response$'):
                self.rd.observe(status, headers)
        self.assertEqual(self.query('SELECT COUNT(*) FROM issued'), [(0,)])


if __name__ == '__main__':
    unittest.main()
