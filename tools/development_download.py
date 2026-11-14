"""Validate the optional, content-addressed Development ZIP in a Pages artifact."""
import hashlib
import io
import json
import re
import stat
from zipfile import ZipFile

import build_development_test as builder

PREFIX = builder.ADDON_ID + "-"
CONFIG_PATH = builder.ADDON_ID + "/resources/development.json"
MAX_CONFIG_BYTES = 4096


class DownloadError(ValueError):
    """Fixed diagnostics; never include configuration or archive contents."""


def _require(condition):
    if not condition:
        raise DownloadError("invalid Development download")


def verify(files, *, video=False):
    """Return the optional ZIP name after checking its complete pair and contents.

    ZIP members are bounded and compared with the checked-out source at the
    publication revision, without executing archived code or rebuilding ZIP bytes.
    Public configuration is the sole variable input and must match the canonical
    Development schema. The caller separately rejects unrelated site files.
    """
    try:
        _require(type(video) is bool)
        addon_id = builder.VIDEO_ID if video else builder.ADDON_ID
        prefix = addon_id + "-"
        config_path = addon_id + "/resources/development.json"
        names = {name for name in files if name.startswith(prefix)}
        if not names:
            return None
        archives = [name for name in names if name.endswith(".zip")]
        _require(len(archives) == 1)
        name = archives[0]
        match = re.fullmatch(re.escape(prefix + builder.VERSION + "-") + r"([0-9a-f]{64})\.zip", name)
        _require(match is not None and names == {name, name + ".sha256"})
        data = files[name]
        _require(type(data) is bytes and 0 < len(data) <= builder.MAX_ZIP)
        digest = hashlib.sha256(data).hexdigest()
        _require(digest == match.group(1))
        _require(files[name + ".sha256"] == (digest + "  " + name + "\n").encode("ascii"))
        with ZipFile(io.BytesIO(data)) as archive:
            _require(not archive.comment and data[:4] == b"PK\x03\x04"
                     and data[-22:-18] == b"PK\x05\x06")
            entries = archive.infolist()
            _require(0 < len(entries) <= 128)
            _require(len({entry.filename for entry in entries}) == len(entries))
            _require(sum(entry.file_size for entry in entries) <= builder.MAX_TOTAL)
            for entry in entries:
                _require(0 <= entry.file_size <= builder.MAX_FILE
                         and not entry.is_dir() and not entry.flag_bits & 1
                         and stat.S_IFMT(entry.external_attr >> 16) == stat.S_IFREG
                         and entry.external_attr >> 16 == 0o100644
                         and not entry.extra and not entry.comment)
            config_entry = archive.getinfo(config_path)
            _require(config_entry.file_size <= MAX_CONFIG_BYTES)
            config = json.loads(archive.read(config_entry).decode("utf-8"))
            _require(type(config) is dict
                     and set(config) == {"schema", "environment", "client_id", "redirect_uri"}
                     and type(config["schema"]) is int and config["schema"] == 1)
            canonical = builder._configuration({
                "HOMEFX_TRAKT_ENVIRONMENT": config["environment"],
                "TRAKT_CLIENT_ID": config["client_id"],
                "TRAKT_REDIRECT_URI": config["redirect_uri"],
            })
            expected = {addon_id + "/" + path: content for path, content in
                        builder._sources(builder.ROOT, canonical, video).items()}
            _require({entry.filename for entry in entries} == set(expected))
            for entry in entries:
                _require(entry.file_size == len(expected[entry.filename]))
                _require(archive.read(entry) == expected[entry.filename])
        return name
    except Exception:
        raise DownloadError("invalid Development download") from None
