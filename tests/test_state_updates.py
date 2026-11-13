"""Serialized local actions preserve unrelated demo state across invocations."""
import builtins
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
import io
import multiprocessing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/plugin.video.homefx'))
from resources.lib import state


def _update_worker(path, action, values, ready, start, entered, release, result, blocking):
    """Spawn-safe worker; events coordinate contention, not elapsed sleeps."""
    original_save = state._save
    original_connect = sqlite3.connect
    # Allow the test controller to observe a blocked operation before releasing it.
    # Production timeout is tested separately and is never changed by the add-on.
    state.LOCK_TIMEOUT = 5

    def save(target, data):
        if blocking:
            entered.set()
            if not release.wait(10):
                raise AssertionError('Test controller did not release writer')
        return original_save(target, data)

    def connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        if not blocking:
            connection.set_trace_callback(lambda sql: entered.set() if sql == 'BEGIN IMMEDIATE' else None)
        return connection

    ready.set()
    if not start.wait(10):
        result.send('start timeout')
        return
    try:
        with patch.object(state, '_save', save), patch.object(sqlite3, 'connect', connect):
            state.update(path, action, **values)
        result.send('ok')
    except Exception as error:
        result.send(type(error).__name__)
    finally:
        result.close()


def _crash_lock_worker(path, entered):
    with state._locked(Path(path)):
        entered.set()
        os._exit(0)


class DemoStateUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'demo.json'

    def test_field_updates_retain_unrelated_current_fields_and_reset_is_explicit(self):
        state.save(self.path, {'watched': {'m1': True}, 'selected': ['weekend'], 'saved_movies': ['m2']})
        state.update(self.path, 'select', selected=['series', 'series'])
        state.update(self.path, 'watched', key='e2', value=True)
        state.update(self.path, 'collect', key='m3', value=True)
        state.update(self.path, 'collect', key='m3', value=True)
        state.update(self.path, 'collect', key='m2', value=False)
        self.assertEqual(state.load(self.path), {'watched': {'m1': True, 'e2': True},
                                               'selected': ['series'], 'saved_movies': ['m3']})
        state.update(self.path, 'reset')
        self.assertEqual(state.load(self.path), {'watched': {}, 'selected': list(state.LISTS), 'saved_movies': []})

    def test_invalid_actions_fail_before_creating_any_files(self):
        cases = [('unknown', {}), ('select', {'selected': ['missing']}), ('select', {'selected': 'series'}),
                 ('watched', {'key': 'm1', 'value': 1}), ('watched', {'key': 'missing', 'value': True}),
                 ('collect', {'key': 's1', 'value': True}), ('reset', {'key': 'm1'}),
                 ('select', {'selected': [], 'value': False})]
        for action, values in cases:
            with self.subTest(action=action, values=values), self.assertRaises(ValueError):
                state.update(self.path, action, **values)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_read_only_load_does_not_import_sqlite_or_create_lock(self):
        self.path.write_text('{"selected":["series"]}')
        original_import = builtins.__import__
        def importing(name, *args, **kwargs):
            if name == 'sqlite3':
                raise ImportError('SQLite unavailable')
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, '__import__', importing):
            self.assertEqual(state.load(self.path)['selected'], ['series'])
            with self.assertRaisesRegex(OSError, '^Unable to save demo state$'):
                state.update(self.path, 'watched', key='m1', value=True)
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_separate_processes_merge_contended_actions_from_latest_state(self):
        context = multiprocessing.get_context('spawn')
        state.save(self.path, {'watched': {}, 'selected': [], 'saved_movies': []})
        for second_action, second_values in [('select', {'selected': ['series']}),
                                             ('collect', {'key': 'm2', 'value': True})]:
            with self.subTest(second_action=second_action):
                state.save(self.path, {'watched': {}, 'selected': [], 'saved_movies': []})
                ready = [context.Event(), context.Event()]
                start = [context.Event(), context.Event()]
                entered = [context.Event(), context.Event()]
                release = context.Event()
                pipes = [context.Pipe(False), context.Pipe(False)]
                processes = [context.Process(target=_update_worker, args=(
                    str(self.path), action, values, ready[index], start[index], entered[index],
                    release, pipes[index][1], index == 0)) for index, (action, values) in enumerate([
                        ('watched', {'key': 'm1', 'value': True}), (second_action, second_values)])]
                try:
                    for process in processes:
                        process.start()
                    for event in ready:
                        self.assertTrue(event.wait(10), 'Worker did not initialize')
                    start[0].set()
                    self.assertTrue(entered[0].wait(10), 'First writer did not hold lock')
                    start[1].set()
                    self.assertTrue(entered[1].wait(10), 'Second writer did not attempt lock')
                    # First writer is paused after its read, proving overlap.
                    self.assertFalse(pipes[1][0].poll())
                    release.set()
                    for process, pair in zip(processes, pipes):
                        process.join(10)
                        self.assertFalse(process.is_alive(), 'Worker failed to complete')
                        self.assertEqual(process.exitcode, 0)
                        self.assertTrue(pair[0].poll())
                        self.assertEqual(pair[0].recv(), 'ok')
                finally:
                    release.set()
                    for process in processes:
                        if process.is_alive():
                            process.terminate()
                        process.join(10)
                    for pair in pipes:
                        for connection in pair:
                            connection.close()
                data = state.load(self.path)
                self.assertEqual(data['watched'], {'m1': True})
                self.assertEqual(data['selected'], ['series'] if second_action == 'select' else [])
                self.assertEqual(data['saved_movies'], ['m2'] if second_action == 'collect' else [])

    def test_first_use_threaded_initialization_preserves_independent_updates(self):
        actions = [('watched', {'key': key, 'value': True}) for key in ('m1', 'm2', 'm3')]
        actions += [('collect', {'key': key, 'value': True}) for key in ('m4', 'm5')]
        actions += [('select', {'selected': ['series']})]
        barrier = threading.Barrier(len(actions))
        path = self.root / 'new' / 'profile' / 'demo.json'
        def mutate(action, values):
            barrier.wait(timeout=10)
            return state.update(path, action, **values)
        # Longer test-only coordination budget avoids conflating worker scheduling
        # with the separately tested production busy timeout.
        with patch.object(state, 'LOCK_TIMEOUT', 5), ThreadPoolExecutor(max_workers=len(actions)) as pool:
            futures = [pool.submit(mutate, action, values) for action, values in actions]
            for future in futures:
                future.result(timeout=10)
        data = state.load(path)
        self.assertEqual(data['watched'], {'m1': True, 'm2': True, 'm3': True})
        self.assertEqual(set(data['saved_movies']), {'m4', 'm5'})
        self.assertEqual(data['selected'], ['series'])

    def test_peer_creating_database_and_journal_during_metadata_check_is_not_an_orphan(self):
        lock = state._lock_path(self.path)
        journal = Path(str(lock) + '-journal')
        original = Path.lstat
        created = []
        def metadata(path):
            if path == journal and not created:
                # A peer starts initialization between this check's lstat calls.
                lock.write_bytes(b'')
                journal.write_bytes(b'')
                created.append(True)
            return original(path)
        with patch.object(Path, 'lstat', metadata):
            self.assertTrue(state._check_lock_files(lock))
        self.assertEqual(created, [True])
        lock.unlink()
        with self.assertRaises(OSError):
            state._check_lock_files(lock)

    def test_lock_database_uses_sqlite_descriptor_management_not_raw_open_close(self):
        lock = state._lock_path(self.path)
        original_path_open = Path.open
        original_os_open = os.open
        def path_open(path, *args, **kwargs):
            self.assertNotEqual(path, lock, 'Raw DB close can release another SQLite writer lock')
            return original_path_open(path, *args, **kwargs)
        def os_open(path, *args, **kwargs):
            self.assertNotEqual(Path(path), lock, 'Raw DB close can release another SQLite writer lock')
            return original_os_open(path, *args, **kwargs)
        with patch.object(Path, 'open', path_open), patch.object(os, 'open', os_open):
            state.update(self.path, 'watched', key='m1', value=True)
            state.update(self.path, 'select', selected=['series'])
        self.assertEqual(state.load(self.path)['watched'], {'m1': True})

    def test_busy_lock_fails_bounded_without_overwrite_and_save_uses_same_lock(self):
        state.update(self.path, 'select', selected=['series'])
        before = self.path.read_bytes()
        lock = sqlite3.connect(str(state._lock_path(self.path)), isolation_level=None)
        self.addCleanup(lock.close)
        lock.execute('BEGIN IMMEDIATE')
        original_connect = sqlite3.connect
        for mutation in (lambda: state.update(self.path, 'watched', key='m1', value=True),
                         lambda: state.save(self.path, {'selected': []})):
            with patch.object(sqlite3, 'connect', wraps=original_connect) as connect:
                with self.assertRaisesRegex(OSError, '^Unable to save demo state$'):
                    mutation()
                self.assertEqual(connect.call_args.kwargs['timeout'], 0.25)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertEqual(list(self.root.glob('demo-*')), [])
        lock.rollback()
        state.update(self.path, 'watched', key='m1', value=True)
        self.assertEqual(state.load(self.path)['selected'], ['series'])
        self.assertEqual(state.load(self.path)['watched'], {'m1': True})

    def test_process_exit_releases_lock_without_removing_persistent_lock_file(self):
        state.update(self.path, 'select', selected=['series'])
        context = multiprocessing.get_context('spawn')
        entered = context.Event()
        process = context.Process(target=_crash_lock_worker, args=(str(self.path), entered))
        process.start()
        try:
            process.join(10)
            self.assertFalse(process.is_alive())
            self.assertTrue(entered.is_set())
            self.assertEqual(process.exitcode, 0)
        finally:
            if process.is_alive():
                process.terminate()
            process.join(10)
        self.assertTrue(state._lock_path(self.path).exists())
        state.update(self.path, 'collect', key='m2', value=True)
        self.assertEqual(state.load(self.path)['saved_movies'], ['m2'])

    def test_lock_file_and_sidecars_reject_unsafe_paths_without_touching_targets(self):
        for suffix in ('', '-journal', '-wal', '-shm'):
            for kind in ('symlink', 'hardlink', 'directory', 'fifo'):
                with self.subTest(suffix=suffix, kind=kind), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    path = root / 'demo.json'
                    path.write_text('{"selected":["series"]}')
                    lock = state._lock_path(path)
                    if suffix:
                        lock.touch()
                    target = Path(str(lock) + suffix)
                    outside = root / 'outside'
                    outside.write_bytes(b'sentinel')
                    if kind == 'symlink':
                        target.symlink_to(outside)
                    elif kind == 'hardlink':
                        os.link(outside, target)
                    elif kind == 'directory':
                        target.mkdir()
                    elif hasattr(os, 'mkfifo'):
                        os.mkfifo(target)
                    else:
                        continue
                    before = path.read_bytes()
                    with self.assertRaisesRegex(OSError, '^Unable to save demo state$'):
                        state.update(path, 'watched', key='m1', value=True)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(outside.read_bytes(), b'sentinel')
                    self.assertEqual(list(root.glob('demo-*')), [])

    def test_corrupt_or_unrelated_lock_database_is_not_reset(self):
        for kind in ('corrupt', 'oversize', 'unrelated'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'demo.json'
                path.write_text('{"selected":["series"]}')
                lock = state._lock_path(path)
                if kind == 'unrelated':
                    with sqlite3.connect(str(lock)) as connection:
                        connection.execute('CREATE TABLE unrelated(value TEXT)')
                else:
                    lock.write_bytes(b'bad' if kind == 'corrupt' else b'x' * (state.MAX_STATE_BYTES + 1))
                before = (path.read_bytes(), lock.read_bytes())
                with self.assertRaisesRegex(OSError, '^Unable to save demo state$'):
                    state.update(path, 'reset')
                self.assertEqual((path.read_bytes(), lock.read_bytes()), before)

    def test_failed_json_replace_releases_lock_and_keeps_previous_state(self):
        state.update(self.path, 'select', selected=['series'])
        before = self.path.read_bytes()
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(state.os, 'replace', side_effect=OSError('private fixture path')), \
                redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaisesRegex(OSError, '^Unable to save demo state$'):
                state.update(self.path, 'watched', key='m1', value=True)
        self.assertEqual((output.getvalue(), errors.getvalue()), ('', ''))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.root.glob('demo-*')), [])
        state.update(self.path, 'collect', key='m2', value=True)
        self.assertEqual(state.load(self.path)['selected'], ['series'])
        self.assertEqual(state.load(self.path)['saved_movies'], ['m2'])

    def test_initial_marker_commit_failure_cannot_replace_json(self):
        self.path.write_text('{"selected":["series"]}')
        before = self.path.read_bytes()
        class FailingCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError('synthetic failure')
        original = sqlite3.connect
        def connect(*args, **kwargs):
            return original(*args, factory=FailingCommit, **kwargs)
        with patch.object(sqlite3, 'connect', connect):
            with self.assertRaisesRegex(OSError, '^Unable to save demo state$'):
                state.update(self.path, 'reset')
        self.assertEqual(self.path.read_bytes(), before)
        state.update(self.path, 'collect', key='m2', value=True)
        self.assertEqual(state.load(self.path)['selected'], ['series'])


if __name__ == '__main__':
    unittest.main()
