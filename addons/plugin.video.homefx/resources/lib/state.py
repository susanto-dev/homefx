"""Local demo preferences only. Never stores service credentials."""
from contextlib import contextmanager
import json
import os
import stat
import tempfile
from pathlib import Path
from .catalogue import LISTS, catalogue

MAX_STATE_BYTES = 64 * 1024
LOCK_TIMEOUT = 0.25
_LOCK_APPLICATION_ID = 0x48465844
_LOCK_VERSION = 1


def _check_parent_chain(path):
    """Reject symlinks and non-directories in the existing parent chain."""
    if ".." in path.parts:
        raise OSError("Unsafe demo state path")
    parent = path.parent.absolute()
    missing = []
    current = parent
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            missing.append(current)
        else:
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise OSError("Unsafe demo state path")
        if current.parent == current:
            break
        current = current.parent
    return list(reversed(missing))


def _check_existing_target(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1):
        raise OSError("Unsafe demo state path")
    return True


def _normalise(data):
    if not isinstance(data, dict) or not isinstance(data.get("watched", {}), dict):
        raise ValueError("Invalid demo state")
    selected = data.get("selected", list(LISTS))
    if not isinstance(selected, list):
        raise ValueError("Invalid list selection")
    items = catalogue()
    saved = data.get("saved_movies", [])
    if not isinstance(saved, list):
        saved = []
    return {"watched": {key: value for key, value in data.get("watched", {}).items()
                        if key in items and isinstance(value, bool)},
            "selected": list(dict.fromkeys(x for x in selected if isinstance(x, str) and x in LISTS)),
            "saved_movies": list(dict.fromkeys(x for x in saved if isinstance(x, str)
                                  and x in items and items[x]["kind"] == "movie"))}


def load(path):
    path = Path(path)
    try:
        _check_parent_chain(path)
        _check_existing_target(path)
        flags = os.O_RDONLY
        flags |= getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                raise OSError("Unsafe demo state file")
            stream = os.fdopen(fd, "rb")
            fd = -1
        finally:
            if fd >= 0:
                os.close(fd)
        with stream:
            raw = stream.read(MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Demo state exceeds size bound")
        return _normalise(json.loads(raw.decode("utf-8")))
    except (OSError, ValueError, RecursionError):
        return {"watched": {}, "selected": list(LISTS), "saved_movies": []}


def _lock_path(path):
    return path.with_name(path.name + ".lock.sqlite3")


def _check_lock_files(path):
    """Inspect metadata only: closing raw DB descriptors can release SQLite locks."""
    _check_parent_chain(path)
    present = False
    sidecars = False
    # Inspect the persistent database last: a peer can create it and its journal
    # between two lstat calls during first-use initialization.
    for suffix in ("-journal", "-wal", "-shm", ""):
        target = Path(str(path) + suffix)
        try:
            info = target.lstat()
        except FileNotFoundError:
            continue
        if not suffix:
            present = True
        else:
            sidecars = True
        links = (0, 1) if suffix == "-journal" else (1,)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink not in links
                or suffix in ("-wal", "-shm") or info.st_size > MAX_STATE_BYTES):
            raise OSError("Unsafe demo lock")
    if sidecars and not present:
        raise OSError("Invalid demo lock")
    return present


def _inspect_lock(connection, path):
    """Use SQLite's descriptor management, never a second raw file open/close."""
    if connection.execute("SELECT name FROM sqlite_master").fetchall():
        raise OSError("Invalid demo lock")
    application = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    if mode != "delete":
        raise OSError("Invalid demo lock")
    if path.stat().st_size == 0 and application == version == 0:
        return False
    if (application, version) != (_LOCK_APPLICATION_ID, _LOCK_VERSION):
        raise OSError("Invalid demo lock")
    return True


@contextmanager
def _locked(path):
    # Browsing and capability reporting do not require SQLite. Only mutations do.
    import sqlite3

    missing = _check_parent_chain(path)
    _check_existing_target(path)
    for directory in missing:
        directory.mkdir(exist_ok=True)
    _check_parent_chain(path)
    lock = _lock_path(path)
    if _check_lock_files(lock):
        # Read-only inspection refuses recovery of unverified or unrelated data.
        # SQLite manages these descriptors alongside concurrent writer handles.
        inspection = sqlite3.connect(lock.absolute().as_uri() + "?mode=ro", uri=True,
                                     timeout=LOCK_TIMEOUT, isolation_level=None)
        try:
            inspection.execute("BEGIN")
            _inspect_lock(inspection, lock)
        finally:
            inspection.close()
    _check_lock_files(lock)
    connection = sqlite3.connect(str(lock), timeout=LOCK_TIMEOUT, isolation_level=None)
    try:
        connection.execute("BEGIN IMMEDIATE")
        _check_lock_files(lock)
        if not _inspect_lock(connection, lock):
            connection.execute("PRAGMA application_id = %d" % _LOCK_APPLICATION_ID)
            connection.execute("PRAGMA user_version = %d" % _LOCK_VERSION)
            # Initialize before JSON replacement. The subsequent mutation lock
            # performs no SQLite writes, so it has no fallible database commit
            # after JSON has already been replaced.
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            _check_lock_files(lock)
            if not _inspect_lock(connection, lock):
                raise OSError("Invalid demo lock")
        yield
    finally:
        connection.close()


def _save(path, data):
    """Atomic JSON replacement; caller owns the interprocess mutation lock."""
    temp = None
    try:
        _check_parent_chain(path)
        _check_existing_target(path)
        fd, temp = tempfile.mkstemp(prefix="demo-", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        _check_parent_chain(path)
        _check_existing_target(path)
        os.replace(temp, path)
        temp = None
    finally:
        if temp is not None:
            try:
                os.unlink(temp)
            except OSError:
                pass


def save(path, data):
    """Explicit complete replacement, serialized with all field-scoped updates."""
    data = _normalise(data)
    path = Path(path)
    try:
        with _locked(path):
            _save(path, data)
    except Exception:
        raise OSError("Unable to save demo state") from None


def update(path, action, *, selected=None, key=None, value=None):
    """Apply one confirmed local action to latest state; never hold this over a UI dialog.

    SQLite provides a bounded cross-process lock, not a second source of state.
    The existing demo.json format remains authoritative. Reset explicitly replaces
    all fields; every other operation preserves unrelated current fields.
    """
    items = catalogue()
    valid = ((action == "select" and isinstance(selected, list) and key is None and value is None
              and all(type(entry) is str and entry in LISTS for entry in selected))
             or (action in ("watched", "collect") and selected is None
                 and type(key) is str and key in items and type(value) is bool
                 and (action == "watched" or items[key]["kind"] == "movie"))
             or (action == "reset" and selected is key is value is None))
    if not valid:
        raise ValueError("Invalid demo update")
    path = Path(path)
    try:
        with _locked(path):
            _check_existing_target(path)
            data = load(path)
            if action == "select":
                data["selected"] = list(dict.fromkeys(selected))
            elif action == "watched":
                data["watched"][key] = value
            elif action == "collect":
                if value and key not in data["saved_movies"]:
                    data["saved_movies"].append(key)
                elif not value and key in data["saved_movies"]:
                    data["saved_movies"].remove(key)
            else:
                data = {"watched": {}, "selected": list(LISTS), "saved_movies": []}
            _save(path, data)
            return data
    except Exception:
        raise OSError("Unable to save demo state") from None
