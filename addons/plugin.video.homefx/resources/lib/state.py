"""Local demo preferences only. Never stores service credentials."""
import json
import os
import tempfile
from pathlib import Path
from .catalogue import LISTS


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("watched", {}), dict):
            raise ValueError("Invalid demo state")
        selected = data.get("selected", list(LISTS))
        if not isinstance(selected, list):
            raise ValueError("Invalid list selection")
        return {"watched": data.get("watched", {}),
                "selected": [x for x in selected if isinstance(x, str) and x in LISTS]}
    except (OSError, ValueError):
        return {"watched": {}, "selected": list(LISTS)}


def save(path, data):
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
