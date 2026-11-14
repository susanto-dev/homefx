"""Bounded local build identification; no account, profile or provider inspection."""
import json
import os
from pathlib import Path
import re
import stat
import sys

UNAVAILABLE = 'unavailable'
EXPECTED_SKIN = 'skin.arctic.zephyr.mod'
MAX_FILE = 1024


def _build(path):
    """Read only the installed public build record; reject links and unusual files."""
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path,) + tuple(path.parents)):
        raise ValueError('invalid_build_record')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
        raise ValueError('invalid_build_record')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_FILE
                or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)):
            raise ValueError('invalid_build_record')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(MAX_FILE + 1)
    finally:
        os.close(fd)
    if len(data) > MAX_FILE:
        raise ValueError('invalid_build_record')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('invalid_build_record')
            result[key] = value
        return result

    value = json.loads(data.decode('utf-8'), object_pairs_hook=unique)
    if (type(value) is not dict or set(value) != {'schema', 'source_version', 'runtime_sha256'}
            or type(value['schema']) is not int or value['schema'] != 1
            or type(value['source_version']) is not str
            or re.fullmatch(r'[0-9]{1,5}\.[0-9]{1,5}\.[0-9]{1,5}', value['source_version']) is None
            or type(value['runtime_sha256']) is not str
            or re.fullmatch(r'[0-9a-f]{64}', value['runtime_sha256']) is None):
        raise ValueError('invalid_build_record')
    return value['source_version'], value['runtime_sha256']


def _version(callback):
    try:
        value = callback()
        if type(value) is not str or len(value) > 256:
            return UNAVAILABLE
        match = re.match(r'^(\d{1,5}\.\d{1,5}(?:\.\d{1,5})?)(?=$|[ (+-])', value, re.ASCII)
        return match.group(1) if match else UNAVAILABLE
    except Exception:
        return UNAVAILABLE


def report(build_path, kodi_version, skin_id, skin_version, *, python_version=sys.version_info):
    """Callbacks provide local runtime labels only. Never return their raw text."""
    try:
        source, fingerprint = _build(build_path)
    except Exception:
        source, fingerprint = UNAVAILABLE, UNAVAILABLE
    try:
        identity = skin_id()
        skin = ('Arctic Zephyr Reloaded' if identity == EXPECTED_SKIN else
                'other skin' if type(identity) is str and identity else UNAVAILABLE)
    except Exception:
        skin = UNAVAILABLE
    skin_release = _version(skin_version) if skin == 'Arctic Zephyr Reloaded' else UNAVAILABLE
    parts = python_version[:3] if isinstance(python_version, (tuple, list)) else ()
    python = ('.'.join(str(v) for v in parts) if len(parts) == 3
              and all(type(v) is int and 0 <= v <= 99999 for v in parts) else UNAVAILABLE)
    return '\n'.join([
        'HomeFX Development Video — local build information',
        'Source version: ' + source,
        'Runtime fingerprint: ' + fingerprint,
        'Fingerprint identifies bundled code/assets; it is not the ZIP checksum or a signature.',
        'The build record is descriptive; installed runtime files were not rehashed.',
        'Kodi: ' + _version(kodi_version),
        'Python: ' + python,
        'Active skin: ' + skin,
        'Skin version: ' + skin_release,
        'No account files, settings, tokens or profile paths were read.',
        'No network, login, storage, widget or playback test was run.',
        'Installed versions do not establish skin compatibility or TV acceptance.',
    ])
