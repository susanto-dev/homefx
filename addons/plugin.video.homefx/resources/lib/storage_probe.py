"""Explicit synthetic private-storage check; never read account files or network."""
import importlib
import os
from pathlib import Path
import shutil
import stat
import tempfile


def _safe_profile(profile):
    if not isinstance(profile, (str, Path)) or not str(profile) or "\0" in str(profile):
        raise ValueError()
    path = Path(profile)
    if not path.is_absolute() or path == path.parent or ".." in path.parts:
        raise ValueError()
    if any(part.is_symlink() for part in (path,) + tuple(path.parents)):
        raise ValueError()
    if path.exists() and not path.is_dir():
        raise ValueError()
    return path


def _private(path, mode, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    return (expected and stat.S_IMODE(info.st_mode) == mode
            and (directory or info.st_nlink == 1))


def report(profile):
    """Create/check/remove only a fresh synthetic directory after caller consent.

    The profile may be created if absent; it is never chmodded or removed. No
    existing profile children are listed or opened. Parent paths must remain
    quiescent; permissions cannot defend against other code running as Kodi.
    Results contain only fixed labels, never paths, account data or raw errors.
    """
    permissions, transaction, cleanup = "not run", "not run", "not needed"
    directory = connection = None
    failed = False
    stage, failure_stage = "platform prerequisites", "none"
    directory_check = "not run"
    try:
        if os.name != "posix" or not hasattr(os, "fchmod"):
            permissions = "unsupported"
            raise ValueError()
        stage = "SQLite import"
        try:
            sqlite = importlib.import_module("sqlite3")
        except ImportError:
            transaction = "unavailable"
            raise ValueError()
        stage = "profile validation"
        profile = _safe_profile(profile)
        stage = "profile creation"
        profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        stage = "profile revalidation"
        _safe_profile(profile)
        stage = "temporary directory creation"
        directory = Path(tempfile.mkdtemp(prefix=".homefx-storage-check-", dir=str(profile)))
        cleanup = "pending"
        permissions = "failed"
        # Apply the same private mode requested by account stores, but only to
        # this invocation's fresh synthetic directory, never the profile itself.
        stage = "directory permission change"
        directory_check = "permission change failed"
        descriptor = os.open(str(directory), os.O_RDONLY | os.O_NONBLOCK
                             | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(descriptor)
            path_info = directory.lstat()
            if (not stat.S_ISDIR(info.st_mode) or not stat.S_ISDIR(path_info.st_mode)
                    or (info.st_dev, info.st_ino) != (path_info.st_dev, path_info.st_ino)):
                raise ValueError()
            os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
        stage = "directory permissions"
        directory_check = "inspection failed"
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode):
            directory_check = "not a directory"
            raise ValueError()
        if stat.S_IMODE(info.st_mode) != 0o700:
            directory_check = "mode mismatch after setting private permissions"
            raise ValueError()
        directory_check = "passed"
        database = directory / "synthetic.sqlite3"
        stage = "database creation"
        descriptor = os.open(str(database), os.O_CREAT | os.O_EXCL | os.O_RDWR
                             | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            stage = "file permission change"
            os.fchmod(descriptor, 0o600)
            stage = "database descriptor close"
        finally:
            os.close(descriptor)
        stage = "database permissions"
        if not _private(database, 0o600):
            raise ValueError()
        permissions = "passed"
        transaction = "failed"
        stage = "SQLite connection"
        connection = sqlite.connect(str(database), timeout=2)
        stage = "SQLite transaction"
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE probe (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO probe VALUES (1)")
        connection.commit()
        connection.execute("INSERT INTO probe VALUES (2)")
        connection.rollback()
        if connection.execute("SELECT value FROM probe").fetchall() != [(1,)]:
            raise ValueError()
        stage = "SQLite close"
        connection.close()
        connection = None
        stage = "final permissions"
        if not _private(directory, 0o700, directory=True) or not _private(database, 0o600):
            permissions = "failed"
            raise ValueError()
        transaction = "passed"
    except Exception:
        failed = True  # Only fixed result labels leave this boundary.
        failure_stage = stage
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                transaction = "failed"
                if failure_stage == "none":
                    failure_stage = "SQLite close"
        if directory is not None:
            try:
                shutil.rmtree(str(directory))
                cleanup = "failed" if directory.exists() or directory.is_symlink() else "passed"
            except Exception:
                cleanup = "failed"
            if cleanup == "failed" and failure_stage == "none":
                failure_stage = "temporary cleanup"
    passed = not failed and permissions == transaction == cleanup == "passed"
    return "\n".join([
        "Private storage self-check (synthetic data only)",
        "Private file permissions: " + permissions,
        "SQLite commit/rollback: " + transaction,
        "Temporary cleanup: " + cleanup,
        "Failure stage: " + failure_stage,
        "Directory check: " + directory_check,
        "Overall: " + ("passed" if passed else "not passed"),
        "No account files were read. No network or login was attempted.",
        "This does not verify token recovery, service access or playback.",
    ])
