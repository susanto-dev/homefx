"""Bounded local runtime information, without accounts, profile access or network."""
import importlib
import os
import re
import sys

UNAVAILABLE = "unavailable"
MAX_REPORT_LENGTH = 1800


def _version(value):
    # Keep numeric components only, never paths, build descriptions or identifiers.
    if type(value) is not str or len(value) > 256:
        return UNAVAILABLE
    match = re.match(r"^(\d{1,3}\.\d{1,3}(?:\.\d{1,5})?)(?=$|[ (+-])", value, re.ASCII)
    return match.group(1) if match else UNAVAILABLE


def _numbers(value):
    if not isinstance(value, (tuple, list)) or len(value) < 3:
        return UNAVAILABLE
    parts = value[:3]
    if not all(type(part) is int and 0 <= part <= 99999 for part in parts):
        return UNAVAILABLE
    return ".".join(str(part) for part in parts)


def _read(probe):
    try:
        return _version(probe())
    except Exception:
        return UNAVAILABLE


def _repository(probe):
    if probe is None:
        return UNAVAILABLE
    try:
        value = probe()
        return "not installed" if value is None else _version(value)
    except Exception:
        return UNAVAILABLE


def report(homefx_version, kodi_version, provider_version, *, repository_version=None,
           importer=importlib.import_module, python_version=sys.version_info,
           os_name=os.name, private_file_mode=hasattr(os, "fchmod")):
    """Probe only specified local capabilities; callback errors never become output."""
    sqlite_version = UNAVAILABLE
    try:
        sqlite_version = _numbers(importer("sqlite3").sqlite_version_info)
    except Exception:
        sqlite_version = UNAVAILABLE
    openssl_version = UNAVAILABLE
    verified_context = UNAVAILABLE
    ca_count = UNAVAILABLE
    try:
        tls = importer("ssl")
        openssl_version = _numbers(tls.OPENSSL_VERSION_INFO)
        context = tls.create_default_context()
        if context.verify_mode == tls.CERT_REQUIRED and context.check_hostname is True:
            verified_context = "available"
            count = context.cert_store_stats().get("x509_ca")
            if type(count) is int and 0 <= count <= 100000:
                ca_count = str(count)
    except Exception:
        # A partial probe is not evidence of a usable verified TLS context.
        verified_context = UNAVAILABLE
        ca_count = UNAVAILABLE
    private_store = "available" if os_name == "posix" and private_file_mode is True else UNAVAILABLE
    provider = _read(provider_version)
    lines = [
        "Local runtime information only",
        "HomeFX: " + _read(homefx_version),
        "HomeFX repository: " + _repository(repository_version),
        "Kodi: " + _read(kodi_version),
        "Python: " + _numbers(python_version),
        "SQLite version: " + sqlite_version,
        "OpenSSL version: " + openssl_version,
        "Verified default TLS context: " + verified_context,
        "Trusted CA count: " + ca_count,
        "POSIX private-store prerequisites: " + private_store,
        "Profile permissions and storage have not been tested.",
        "Umbrella version: " + provider + "; handoff untested.",
        "No network, login, service or playback tests were run.",
        "This report does not establish TV compatibility or acceptance.",
    ]
    return "\n".join(lines)[:MAX_REPORT_LENGTH]
