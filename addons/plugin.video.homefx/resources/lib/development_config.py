"""Strict public Development configuration and own-profile scoping; no network."""
import hashlib
import json
from pathlib import Path
import stat
from . import service_runtime, storage_probe, trakt_auth

MAX_CONFIG_BYTES = 4096


class DevelopmentError(ValueError):
    """Fixed error only; no configuration, code, token or path values."""


def validate_config(value):
    if (type(value) is not dict
            or set(value) != {"schema", "environment", "client_id", "redirect_uri"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["environment"] != "Development"
            or type(value["client_id"]) is not str
            or not trakt_auth._text(value["client_id"], 256)
            or not service_runtime._redirect(value["redirect_uri"])):
        raise DevelopmentError("invalid_development_configuration")
    return dict(value)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DevelopmentError("invalid_development_configuration")
        result[key] = value
    return result


def load_config(path):
    try:
        path = Path(path).absolute()
        if any(part.is_symlink() for part in (path,) + tuple(path.parents)):
            raise ValueError()
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError()
        with path.open('rb') as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ValueError()
        return validate_config(json.loads(raw.decode('utf-8'), object_pairs_hook=_unique))
    except Exception:
        raise DevelopmentError("invalid_development_configuration") from None


def scoped_profile(profile, config):
    config = validate_config(config)
    base = storage_probe._safe_profile(profile)
    identity = json.dumps([config["client_id"], config["redirect_uri"]],
                          ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    path = base / ("development-" + hashlib.sha256(identity).hexdigest())
    # Includes existing database and sidecar checks before constructors mutate anything.
    return service_runtime._profile(path, "trakt")


