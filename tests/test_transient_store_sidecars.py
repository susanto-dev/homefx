"""Real SQLite journal lifetimes across private credential and quota stores."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib import service_runtime as runtime
from resources.lib.debrid_auth import AuthError as DebridError
from resources.lib.debrid_store import CredentialStore
from resources.lib.request_limits import LimitError, RequestLimits
from resources.lib.trakt_auth import AuthError as TraktError
from resources.lib.trakt_tokens import TokenStore


CASES = (
    ('trakt', lambda profile: TokenStore(profile, clock=lambda: 1000),
     'trakt/tokens.sqlite3', TraktError),
    ('realdebrid', lambda profile: CredentialStore(profile, clock=lambda: 1000),
     'realdebrid/credentials.sqlite3', DebridError),
    ('limits', lambda profile: RequestLimits(profile, 'realdebrid', clock=lambda: 1000),
     'limits/requests.sqlite3', LimitError),
)


def read(store, kind):
    return store.reserve() if kind == 'limits' else store.snapshot().generation


class TransientStoreSidecarsTests(unittest.TestCase):
    def test_real_commit_unlinked_journal_preserves_committed_state_on_read_and_reopen(self):
        for kind, factory, relative, error in CASES:
            for reopen in (False, True):
                with self.subTest(kind=kind, reopen=reopen), tempfile.TemporaryDirectory() as profile:
                    store = factory(profile)
                    main = Path(profile) / relative
                    journal = Path(str(main) + '-journal')
                    with closing(sqlite3.connect(str(main))) as writer:
                        writer.execute('BEGIN IMMEDIATE')
                        if kind == 'limits':
                            writer.execute("UPDATE state SET cooldown=1040 WHERE provider='realdebrid'")
                            expected = 40
                        else:
                            writer.execute('UPDATE credential SET generation=1')
                            expected = 1
                        self.assertTrue(journal.is_file())
                        real_lstat = Path.lstat
                        observed_links = []

                        def commit_during_stat(path):
                            if path == journal and not observed_links:
                                descriptor = os.open(str(journal), os.O_RDONLY)
                                try:
                                    writer.commit()
                                    info = os.fstat(descriptor)
                                finally:
                                    os.close(descriptor)
                                observed_links.append(info.st_nlink)
                                return info
                            return real_lstat(path)

                        with mock.patch.object(Path, 'lstat', commit_during_stat):
                            current = factory(profile) if reopen else store
                            self.assertEqual(read(current, kind), expected)
                        self.assertEqual(observed_links, [0])
                        self.assertFalse(journal.exists())
                        self.assertEqual(read(factory(profile), kind), expected)

    def test_factories_accept_transient_journals_and_preserve_committed_state(self):
        cases = (
            ('trakt', 'trakt/tokens.sqlite3', 'UPDATE credential SET generation=1',
             'SELECT generation FROM credential', 1),
            ('trakt', 'trakt/preferences.sqlite3', 'UPDATE preference_state SET epoch=1',
             'SELECT epoch FROM preference_state', 1),
            ('realdebrid', 'realdebrid/credentials.sqlite3', 'UPDATE credential SET generation=1',
             'SELECT generation FROM credential', 1),
            ('trakt', 'limits/requests.sqlite3', "UPDATE state SET cooldown=1040 WHERE provider='trakt'",
             "SELECT cooldown FROM state WHERE provider='trakt'", 1040),
            ('realdebrid', 'limits/requests.sqlite3',
             "UPDATE state SET cooldown=1040 WHERE provider='realdebrid'",
             "SELECT cooldown FROM state WHERE provider='realdebrid'", 1040),
        )
        for provider, relative, update, query, expected in cases:
            with self.subTest(provider=provider, store=relative), tempfile.TemporaryDirectory() as profile:
                network = mock.Mock(side_effect=AssertionError('Provider traffic is forbidden'))
                self.assemble(profile, provider, network)
                main = Path(profile) / relative
                journal = Path(str(main) + '-journal')
                with closing(sqlite3.connect(str(main))) as writer:
                    writer.execute('BEGIN IMMEDIATE')
                    writer.execute(update)
                    descriptor = os.open(str(journal), os.O_RDONLY)
                    snapshots = []
                    real_lstat, real_stat = Path.lstat, Path.stat
                    original_profile = runtime._profile

                    def snapshot(path, original, *args, **kwargs):
                        if path == journal:
                            if not snapshots:
                                writer.commit()
                                snapshots.append(os.fstat(descriptor))
                            return snapshots[0]
                        return original(path, *args, **kwargs)

                    def preflight(*args):
                        # Inject only the syscall boundary; component constructors
                        # afterward use ordinary filesystem and SQLite operations.
                        with mock.patch.object(Path, 'lstat',
                                               lambda p: snapshot(p, real_lstat)), \
                                mock.patch.object(Path, 'stat',
                                                  lambda p, *a, **k: snapshot(p, real_stat, *a, **k)):
                            return original_profile(*args)

                    try:
                        with mock.patch.object(runtime, '_profile', side_effect=preflight):
                            self.assemble(profile, provider, network)
                    finally:
                        os.close(descriptor)
                    self.assertEqual([value.st_nlink for value in snapshots], [0])
                    self.assertFalse(journal.exists())
                    self.assertEqual(writer.execute(query).fetchall(), [(expected,)])
                network.assert_not_called()

    def test_factory_preflight_rejects_unlinked_mandatory_database(self):
        for provider, relative in (('trakt', 'trakt/tokens.sqlite3'),
                                   ('realdebrid', 'realdebrid/credentials.sqlite3')):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as profile:
                network = mock.Mock(side_effect=AssertionError('Provider traffic is forbidden'))
                self.assemble(profile, provider, network)
                main = Path(profile) / relative
                descriptor = os.open(str(main), os.O_RDONLY)
                snapshots = []
                real_lstat, real_stat = Path.lstat, Path.stat

                def snapshot(path, original, *args, **kwargs):
                    if path == main:
                        if not snapshots:
                            main.unlink()
                            snapshots.append(os.fstat(descriptor))
                        return snapshots[0]
                    return original(path, *args, **kwargs)

                try:
                    with mock.patch.object(Path, 'lstat', lambda p: snapshot(p, real_lstat)), \
                            mock.patch.object(Path, 'stat',
                                              lambda p, *a, **k: snapshot(p, real_stat, *a, **k)):
                        with self.assertRaisesRegex(runtime.SetupError, '^invalid_runtime_profile$'):
                            self.assemble(profile, provider, network)
                finally:
                    os.close(descriptor)
                self.assertEqual([value.st_nlink for value in snapshots], [0])
                self.assertFalse(main.exists())
                network.assert_not_called()

    @staticmethod
    def assemble(profile, provider, network):
        options = dict(clock=lambda: 1000, monotonic=lambda: 0, connection_factory=network)
        if provider == 'trakt':
            return runtime.build_trakt(profile, 'synthetic-client',
                                       'https://example.invalid/callback', **options)
        return runtime.build_debrid(profile, 'synthetic-client', **options)

    def test_unlinked_mandatory_database_is_rejected_without_recreation(self):
        for kind, factory, relative, error in CASES:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as profile:
                store = factory(profile)
                main = Path(profile) / relative
                real_lstat = Path.lstat
                observed_links = []

                def unlink_during_stat(path):
                    if path == main and not observed_links:
                        descriptor = os.open(str(main), os.O_RDONLY)
                        try:
                            main.unlink()
                            info = os.fstat(descriptor)
                        finally:
                            os.close(descriptor)
                        observed_links.append(info.st_nlink)
                        return info
                    return real_lstat(path)

                with mock.patch.object(Path, 'lstat', unlink_during_stat):
                    with self.assertRaises(error):
                        read(store, kind)
                self.assertEqual(observed_links, [0])
                self.assertFalse(main.exists())

    def test_unsafe_sidecars_remain_rejected_without_touching_outside_files(self):
        for kind, factory, relative, error in CASES:
            for suffix in ('-journal', '-wal', '-shm'):
                for unsafe in ('symlink', 'hardlink', 'fifo', 'directory'):
                    with self.subTest(kind=kind, suffix=suffix, unsafe=unsafe), \
                            tempfile.TemporaryDirectory() as profile:
                        store = factory(profile)
                        main = Path(profile) / relative
                        before = main.read_bytes()
                        sidecar = Path(str(main) + suffix)
                        outside = Path(profile) / 'synthetic-outside'
                        outside.write_bytes(b'synthetic')
                        if unsafe == 'symlink':
                            sidecar.symlink_to(outside)
                        elif unsafe == 'hardlink':
                            os.link(str(outside), str(sidecar))
                        elif unsafe == 'fifo':
                            os.mkfifo(str(sidecar), 0o600)
                        else:
                            sidecar.mkdir()
                        with self.assertRaises(error):
                            read(store, kind)
                        self.assertEqual(main.read_bytes(), before)
                        self.assertEqual(outside.read_bytes(), b'synthetic')


if __name__ == '__main__':
    unittest.main()
