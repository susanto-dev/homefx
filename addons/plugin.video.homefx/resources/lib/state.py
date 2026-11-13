"""Local demo preferences only. Never stores service credentials."""
import json
import os
import stat
import tempfile
from pathlib import Path
from .catalogue import LISTS, catalogue

MAX_STATE_BYTES = 64 * 1024


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


def save(path, data):
    data = _normalise(data)
    path = Path(path)
    temp = None
    try:
        missing = _check_parent_chain(path)
        _check_existing_target(path)
        for directory in missing:
            directory.mkdir()
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
    except (OSError, ValueError):
        raise OSError("Unable to save demo state") from None
    finally:
        if temp is not None:
            try:
                os.unlink(temp)
            except OSError:
                pass
