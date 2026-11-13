"""Validate the four declared Python inventories offline; never resolve or install.

This deliberately supports only name==numeric.release pins, lowercase SHA-256
hashes, whole-line comments, blank lines and explicit backslash continuations.
It is an inventory guard, not pip's parser, a resolved dependency graph, an
advisory scanner, or a review of package provenance/licences.
"""

import argparse
import json
from pathlib import Path
import re
import stat


ROOT = Path(__file__).resolve().parents[1]
INVENTORIES = (
    "requirements.txt",
    "tools/build-requirements.txt",
    "tools/quality-requirements.txt",
    "tools/security-requirements.txt",
)
MAX_BYTES = 256 * 1024
MAX_LINE = 1024
MAX_DECLARATION = 32768
MAX_PACKAGES = 256
MAX_HASHES = 512
PIN = re.compile(r"([A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?)=="
                 r"([0-9]+(?:\.[0-9]+)*)", re.ASCII)
HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})", re.ASCII)


class DependencyError(ValueError):
    """Public failures use fixed categories, without input or filesystem details."""


def _no_symlinks(path):
    for component in (path,) + tuple(path.parents):
        if component.is_symlink():
            raise DependencyError("symlink paths are unsupported")


def _read(path):
    try:
        _no_symlinks(path)
        if not stat.S_ISREG(path.stat().st_mode):
            raise DependencyError("inventory must be a regular file")
        with path.open("rb") as source:
            content = source.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise DependencyError("inventory exceeds bounds")
        return content.decode("utf-8")
    except (OSError, UnicodeError):
        raise DependencyError("inventory unavailable or invalid UTF-8") from None


def _declarations(content):
    pending = []
    size = 0
    if content.endswith("\r"):
        raise DependencyError("unsupported inventory characters")
    # Only LF/CRLF are supported; other Unicode line breaks/control characters
    # must not be silently interpreted as separators by splitlines/split.
    for raw in content.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        if len(line) > MAX_LINE:
            raise DependencyError("inventory exceeds bounds")
        if any(ord(char) < 32 and char != "\t" or ord(char) > 126 for char in line):
            raise DependencyError("unsupported inventory characters")
        line = line.strip(" \t")
        if not line or line.startswith("#"):
            if pending:
                raise DependencyError("incomplete requirement continuation")
            continue
        continued = line.endswith("\\")
        piece = line[:-1].rstrip(" \t") if continued else line
        if not piece:
            raise DependencyError("invalid requirement declaration")
        pending.append(piece)
        size += len(piece) + 1
        if size > MAX_DECLARATION:
            raise DependencyError("inventory exceeds bounds")
        if not continued:
            yield " ".join(pending)
            pending = []
            size = 0
    if pending:
        raise DependencyError("incomplete requirement continuation")


def parse_inventory(content):
    """Parse the documented strict subset into sorted normalized records."""
    if len(content) > MAX_BYTES:
        raise DependencyError("inventory exceeds bounds")
    packages = {}
    for declaration in _declarations(content):
        tokens = declaration.split()
        pin = PIN.fullmatch(tokens[0])
        if pin is None or len(pin.group(2)) > 64:
            raise DependencyError("invalid requirement pin")
        name = re.sub(r"[-_.]+", "-", pin.group(1)).lower()
        if name in packages:
            raise DependencyError("duplicate normalized requirement")
        hashes = []
        for token in tokens[1:]:
            match = HASH.fullmatch(token)
            if match is None:
                raise DependencyError("invalid requirement hash or option")
            hashes.append(match.group(1))
        if not hashes:
            raise DependencyError("requirement hashes missing")
        if len(hashes) > MAX_HASHES:
            raise DependencyError("inventory exceeds bounds")
        if len(set(hashes)) != len(hashes):
            raise DependencyError("duplicate requirement hash")
        packages[name] = {"name": name, "version": pin.group(2), "hashes": sorted(hashes)}
        if len(packages) > MAX_PACKAGES:
            raise DependencyError("inventory exceeds bounds")
    return [packages[name] for name in sorted(packages)]


def check(root=ROOT):
    """Read every fixed inventory and require consistent shared pins and hashes.

    The intentionally dependency-free runtime may be empty; each tooling inventory
    must retain at least one declaration. Equal versions with different textual
    spellings are not inferred to be equivalent. No metadata or transitive
    dependency edges are discovered.
    """
    root = Path(root).absolute()
    aggregate = {}
    inventories = []
    for relative in INVENTORIES:
        packages = parse_inventory(_read(root / relative))
        if relative != "requirements.txt" and not packages:
            raise DependencyError("tool inventory is empty")
        inventories.append({"path": relative, "packages": len(packages)})
        for package in packages:
            name = package["name"]
            if name not in aggregate:
                aggregate[name] = dict(package, inventories=[])
            record = aggregate[name]
            if record["version"] != package["version"]:
                raise DependencyError("conflicting inventory versions")
            if record["hashes"] != package["hashes"]:
                raise DependencyError("conflicting inventory hashes")
            record["inventories"].append(relative)
    return {"schema_version": 1, "inventories": inventories,
            "packages": [aggregate[name] for name in sorted(aggregate)]}


def write_manifest(output, manifest):
    """Write a fresh manifest only; refuse existing files and symlink paths."""
    output = Path(output).absolute()
    try:
        _no_symlinks(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as target:
            target.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    except OSError:
        raise DependencyError("manifest output unavailable or already exists") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write a fresh normalized JSON inventory")
    args = parser.parse_args(argv)
    try:
        result = check()
        if args.output is not None:
            write_manifest(args.output, result)
    except DependencyError as error:
        parser.exit(1, "Dependency inventory check failed: " + str(error) + "\n")
    print("Validated {0} Python inventories and {1} normalized packages (offline).".format(
        len(result["inventories"]), len(result["packages"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
