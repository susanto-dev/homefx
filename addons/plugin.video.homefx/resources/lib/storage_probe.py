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
    try:
        if os.name != "posix" or not hasattr(os, "fchmod"):
            permissions = "unsupported"
            raise ValueError()
        try:
            sqlite = importlib.import_module("sqlite3")
        except ImportError:
            transaction = "unavailable"
            raise ValueError()
        profile = _safe_profile(profile)
        profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        _safe_profile(profile)
        directory = Path(tempfile.mkdtemp(prefix=".homefx-storage-check-", dir=str(profile)))
        cleanup = "pending"
        permissions = "failed"
        if not _private(directory, 0o700, directory=True):
            raise ValueError()
        database = directory / "synthetic.sqlite3"
        descriptor = os.open(str(database), os.O_CREAT | os.O_EXCL | os.O_RDWR
                             | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        if not _private(database, 0o600):
            raise ValueError()
        permissions = "passed"
        transaction = "failed"
        connection = sqlite.connect(str(database), timeout=2)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("CREATE TABLE probe (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO probe VALUES (1)")
        connection.commit()
        connection.execute("INSERT INTO probe VALUES (2)")
        connection.rollback()
        if connection.execute("SELECT value FROM probe").fetchall() != [(1,)]:
            raise ValueError()
        connection.close()
        connection = None
        if not _private(directory, 0o700, directory=True) or not _private(database, 0o600):
            permissions = "failed"
            raise ValueError()
        transaction = "passed"
    except Exception:
        failed = True  # Only fixed result labels leave this boundary.
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                transaction = "failed"
        if directory is not None:
            try:
                shutil.rmtree(str(directory))
                cleanup = "failed" if directory.exists() or directory.is_symlink() else "passed"
            except Exception:
                cleanup = "failed"
    passed = not failed and permissions == transaction == cleanup == "passed"
    return "\n".join([
        "Private storage self-check (synthetic data only)",
        "Private file permissions: " + permissions,
        "SQLite commit/rollback: " + transaction,
        "Temporary cleanup: " + cleanup,
        "Overall: " + ("passed" if passed else "not passed"),
        "No account files were read. No network or login was attempted.",
        "This does not verify token recovery, service access or playback.",
    ])
