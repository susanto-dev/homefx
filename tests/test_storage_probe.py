"""Temporary synthetic storage checks; never device or real-account acceptance."""
import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ADDON = Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"
sys.path.insert(0, str(ADDON))
from resources.lib import storage_probe as probe


class StorageProbeTests(unittest.TestCase):
    def test_success_removes_only_own_files_and_preserves_existing_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile"
            profile.mkdir(mode=0o750)
            sentinel = profile / "account-private.sqlite3"
            sentinel.write_bytes(b"must never be opened or changed")
            before = stat.S_IMODE(profile.stat().st_mode)
            mkdtemp = tempfile.mkdtemp
            created_modes = []
            def broad_directory(*args, **kwargs):
                directory = mkdtemp(*args, **kwargs)
                os.chmod(directory, 0o755)
                created_modes.append(stat.S_IMODE(os.stat(directory).st_mode))
                return directory
            with patch.object(probe.tempfile, "mkdtemp", side_effect=broad_directory):
                result = probe.report(profile)
            self.assertEqual(created_modes, [0o755])
            self.assertIn("Directory check: passed", result)
            self.assertIn("Overall: passed", result)
            self.assertIn("Failure stage: none", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertEqual(list(profile.iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b"must never be opened or changed")
            self.assertEqual(stat.S_IMODE(profile.stat().st_mode), before)
            self.assertNotIn(str(profile), result)

    def test_absent_profile_created_and_left_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "new"
            self.assertIn("Overall: passed", probe.report(str(profile)))
            self.assertEqual(list(profile.iterdir()), [])

    def test_invalid_symlink_or_special_profiles_never_write_outside(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            outside = base / "outside"
            outside.mkdir()
            link = base / "link"
            link.symlink_to(outside, target_is_directory=True)
            regular = base / "file"
            regular.write_text("private")
            fifo = base / "fifo"
            os.mkfifo(fifo)
            for value in (link, link / "child", regular, fifo, "relative", base / ".." / "escape", "/", None):
                with self.subTest(value=type(value).__name__):
                    result = probe.report(value)
                    self.assertIn("Overall: not passed", result)
                    self.assertNotIn(str(base), result)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual(regular.read_text(), "private")

    def test_missing_sqlite_does_not_break_import_or_create_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "missing"
            with patch.dict(sys.modules, {"sqlite3": None}):
                spec = importlib.util.spec_from_file_location("isolated_probe", ADDON / "resources/lib/storage_probe.py")
                isolated = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(isolated)
                result = isolated.report(profile)
            self.assertIn("Failure stage: SQLite import", result)
            self.assertIn("SQLite commit/rollback: unavailable", result)
            self.assertIn("Overall: not passed", result)
            self.assertFalse(profile.exists())

    def test_unsupported_platform_does_not_create_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "new"
            with patch.object(probe.os, "name", "unsupported"):
                result = probe.report(profile)
            self.assertIn("Failure stage: platform prerequisites", result)
            self.assertIn("Private file permissions: unsupported", result)
            self.assertFalse(profile.exists())

    def test_database_failure_is_redacted_and_temporary_files_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary)
            with patch.object(sqlite3, "connect", side_effect=sqlite3.OperationalError("secret private path")):
                result = probe.report(profile)
            self.assertIn("Failure stage: SQLite connection", result)
            self.assertIn("SQLite commit/rollback: failed", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertIn("Overall: not passed", result)
            self.assertNotIn("secret", result)
            self.assertEqual(list(profile.iterdir()), [])

    def test_broken_rollback_cannot_pass_the_transaction_check(self):
        connect = sqlite3.connect
        class BrokenRollback:
            def __init__(self, *args, **kwargs):
                self.connection = connect(*args, **kwargs)
            def execute(self, *args): return self.connection.execute(*args)
            def commit(self): return self.connection.commit()
            def rollback(self): return None
            def close(self): return self.connection.close()
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(sqlite3, "connect", side_effect=BrokenRollback):
                result = probe.report(temporary)
            self.assertIn("SQLite commit/rollback: failed", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertIn("Overall: not passed", result)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_permission_failure_still_cleans_owned_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary)
            fchmod = os.fchmod
            def fail_file_only(descriptor, mode):
                if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    return fchmod(descriptor, mode)
                raise OSError("private secret")
            with patch.object(probe.os, "fchmod", side_effect=fail_file_only):
                result = probe.report(profile)
            self.assertIn("Failure stage: file permission change", result)
            self.assertIn("SQLite commit/rollback: not run", result)
            self.assertIn("Private file permissions: failed", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertNotIn("private secret", result)
            self.assertEqual(list(profile.iterdir()), [])

    def test_cleanup_failure_cannot_be_overall_success_or_expose_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary)
            with patch.object(probe.shutil, "rmtree", side_effect=OSError("secret cleanup path")):
                result = probe.report(profile)
            self.assertIn("SQLite commit/rollback: passed", result)
            self.assertIn("Failure stage: temporary cleanup", result)
            self.assertIn("Temporary cleanup: failed", result)
            self.assertIn("Overall: not passed", result)
            self.assertNotIn("secret", result)
            remaining = list(profile.iterdir())
            self.assertEqual(len(remaining), 1)
            self.assertTrue(remaining[0].name.startswith(".homefx-storage-check-"))
            shutil.rmtree(remaining[0])

    def test_report_claims_no_service_or_token_recovery_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = probe.report(temporary)
            self.assertIn("No account files were read", result)
            self.assertIn("No network or login was attempted", result)
            self.assertIn("does not verify token recovery", result)
            self.assertLess(len(result), 800)

    def test_ignored_directory_mode_change_never_opens_sqlite(self):
        with tempfile.TemporaryDirectory() as temporary:
            mkdtemp, fchmod = tempfile.mkdtemp, os.fchmod
            def broad_directory(*args, **kwargs):
                directory = mkdtemp(*args, **kwargs)
                os.chmod(directory, 0o755)
                return directory
            def ignore_directory_change(descriptor, mode):
                if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                    return fchmod(descriptor, mode)
            with patch.object(probe.tempfile, "mkdtemp", side_effect=broad_directory), \
                    patch.object(probe.os, "fchmod", side_effect=ignore_directory_change), \
                    patch.object(sqlite3, "connect") as connect:
                result = probe.report(temporary)
            connect.assert_not_called()
            self.assertIn("Failure stage: directory permissions", result)
            self.assertIn("Directory check: mode mismatch after setting private permissions", result)
            self.assertIn("Private file permissions: failed", result)
            self.assertIn("SQLite commit/rollback: not run", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertIn("Overall: not passed", result)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_rejected_directory_permission_change_is_redacted_and_cleaned(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(probe.os, "fchmod", side_effect=OSError("/private/token")), \
                    patch.object(sqlite3, "connect") as connect:
                result = probe.report(temporary)
            connect.assert_not_called()
            self.assertIn("Failure stage: directory permission change", result)
            self.assertIn("Directory check: permission change failed", result)
            self.assertIn("SQLite commit/rollback: not run", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertIn("Overall: not passed", result)
            self.assertNotIn("/private", result)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_directory_identity_mismatch_prevents_permission_change(self):
        fstat = os.fstat
        first = True
        def different_identity(descriptor):
            nonlocal first
            info = fstat(descriptor)
            if first:
                first = False
                return types.SimpleNamespace(st_mode=info.st_mode, st_dev=info.st_dev,
                                             st_ino=info.st_ino + 1)
            return info
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(probe.os, "fstat", side_effect=different_identity), \
                    patch.object(probe.os, "fchmod") as fchmod, \
                    patch.object(sqlite3, "connect") as connect:
                result = probe.report(temporary)
            fchmod.assert_not_called()
            connect.assert_not_called()
            self.assertIn("Failure stage: directory permission change", result)
            self.assertIn("Overall: not passed", result)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_file_mode_failure_is_distinct_and_never_opens_sqlite(self):
        original = probe._private
        def directory_only(path, mode, directory=False):
            return original(path, mode, directory=True) if directory else False
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(probe, "_private", side_effect=directory_only), \
                    patch.object(sqlite3, "connect") as connect:
                result = probe.report(temporary)
            connect.assert_not_called()
            self.assertIn("Failure stage: database permissions", result)
            self.assertIn("Overall: not passed", result)
            self.assertIn("Temporary cleanup: passed", result)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_inspection_exception_is_redacted_and_cleanup_does_not_hide_first_failure(self):
        original_lstat, original_fchmod = Path.lstat, os.fchmod
        changed = False
        def change_mode(descriptor, mode):
            nonlocal changed
            original_fchmod(descriptor, mode)
            changed = True
        def unreadable_directory(path, *args, **kwargs):
            if changed and path.name.startswith(".homefx-storage-check-"):
                raise OSError("/private/token")
            return original_lstat(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(probe.os, "fchmod", side_effect=change_mode), \
                    patch.object(Path, "lstat", unreadable_directory), \
                    patch.object(probe.shutil, "rmtree", side_effect=OSError("/private/cleanup")):
                result = probe.report(temporary)
            self.assertIn("Failure stage: directory permissions", result)
            self.assertIn("Directory check: inspection failed", result)
            self.assertIn("Temporary cleanup: failed", result)
            self.assertIn("Overall: not passed", result)
            self.assertNotIn("/private", result)
            self.assertNotIn(temporary, result)
            self.assertLess(len(result), 800)
