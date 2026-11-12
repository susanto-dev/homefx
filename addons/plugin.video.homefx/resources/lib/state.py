"""Local demo preferences only. Never stores service credentials."""
import json
import os
import tempfile
from pathlib import Path
from .catalogue import LISTS, catalogue

MAX_STATE_BYTES = 64 * 1024


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
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_STATE_BYTES + 1)
        if len(raw) > MAX_STATE_BYTES:
            raise ValueError("Demo state exceeds size bound")
        return _normalise(json.loads(raw.decode("utf-8")))
    except (OSError, ValueError, RecursionError):
        return {"watched": {}, "selected": list(LISTS), "saved_movies": []}


def save(path, data):
    data = _normalise(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="demo-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
