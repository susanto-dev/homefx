"""Verify local release history and reject changes to previously recorded packages."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
# Only bounded read-only Git commands are invoked, without a shell or hooks.
import subprocess  # nosec B404
import tempfile

import package
import repository


class HistoryError(ValueError):
    """Fixed error categories; no archive contents or private paths in failures."""


def _require(condition, category):
    if not condition:
        raise HistoryError(category)


def _records(data):
    _require(len(data) <= repository.MAX_INVENTORY, "inventory bounds")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "inventory duplicate field")
            result[key] = value
        return result

    value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs)
    _require(isinstance(value, dict) and set(value) == {"schema", "packages"}
             and type(value["schema"]) is int and value["schema"] == 1
             and isinstance(value["packages"], list)
             and len(value["packages"]) <= repository.MAX_RETAINED, "inventory schema")
    records = {}
    for item in value["packages"]:
        _require(isinstance(item, dict) and set(item) == {"id", "version", "path", "sha256"},
                 "inventory schema")
        ident, version, path, digest = (item[key] for key in ("id", "version", "path", "sha256"))
        _require(isinstance(ident, str) and ident in ("plugin.video.homefx", "repository.homefx"),
                 "inventory identity")
        repository._version(version)
        _require(isinstance(path, str) and len(path) <= 512
                 and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", path)
                 and all(part not in (".", "..") for part in path.split("/"))
                 and PurePosixPath(path).name == ident + "-" + version + ".zip", "inventory path")
        _require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "inventory hash")
        identity = (ident, version)
        _require(identity not in records, "inventory duplicate identity")
        records[identity] = dict(item)
    return records


def _read(path):
    path = Path(path).absolute()
    repository._no_symlinks(path)
    return _records(repository._safe_file(path.parent, path.name, repository.MAX_INVENTORY))


def _git(root, arguments):
    # Arguments are internal constants or validated refs/object IDs, never shell text.
    result = subprocess.run(  # nosec B603
        ["git", "--no-replace-objects", "-C", str(root)] + arguments,
        check=False, shell=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=10)
    _require(result.returncode == 0, "base history unavailable")
    return result.stdout


def _base_records(inventory_path, base_ref, git_root):
    _require(isinstance(base_ref, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", base_ref)
             and ".." not in base_ref and "//" not in base_ref, "invalid base ref")
    root = Path(git_root).resolve()
    relative = Path(inventory_path).absolute().relative_to(root).as_posix()
    _require(re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", relative)
             and all(part not in (".", "..") for part in relative.split("/")), "inventory path")
    commit = _git(root, ["rev-parse", "--verify", base_ref + "^{commit}"]).strip().decode("ascii")
    _require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit), "base history unavailable")
    entry = _git(root, ["ls-tree", "-z", commit, "--", relative])
    if not entry:
        return {}
    # Exact path lookup must resolve to one regular blob, never a symlink or directory.
    _require(len(entry) <= 1024 and entry.count(b"\0") == 1, "base inventory topology")
    metadata, found = entry[:-1].split(b"\t", 1)
    mode, kind, oid = metadata.split(b" ")
    _require(mode == b"100644" and kind == b"blob" and found.decode("utf-8") == relative
             and re.fullmatch(rb"[0-9a-f]{40}|[0-9a-f]{64}", oid), "base inventory topology")
    blob = oid.decode("ascii")
    size = _git(root, ["cat-file", "-s", blob]).strip()
    _require(re.fullmatch(rb"[0-9]{1,10}", size) and int(size) <= repository.MAX_INVENTORY,
             "base inventory bounds")
    # Read the immutable object checked above, not a mutable ref or filter expansion.
    data = _git(root, ["cat-file", "blob", blob])
    _require(len(data) == int(size), "base inventory bounds")
    return _records(data)


def verify_history(inventory_path, previous_inventory_path=None, *, base_ref=None, git_root=None):
    """Validate a quiescent local inventory without changing source or release files.

    Both current package versions must be present and byte-identical to fresh builds.
    Retained archives use the existing bounded package verifier. Older inventory
    records pin identities, relative paths and hashes; removal/replacement fails.
    Temporary builds are removed. No network, extraction or archived code execution.
    This verifies history consistency, not source approval or device compatibility.
    """
    try:
        _require(previous_inventory_path is None or base_ref is None, "ambiguous prior history")
        current = _read(inventory_path)
        prior = (_read(previous_inventory_path) if previous_inventory_path is not None else
                 _base_records(inventory_path, base_ref, git_root or package.ROOT)
                 if base_ref is not None else {})
        for identity, record in prior.items():
            _require(current.get(identity) == record, "published history changed")
        versions = {"plugin.video.homefx": package.validate(),
                    "repository.homefx": repository._repository_manifest(repository.REPOSITORY)[1]}
        _require(all((ident, version) in current for ident, version in versions.items()),
                 "current packages missing")
        # The generator checks checksum-pinned input, aggregate bounds, archive contracts,
        # and exact current bytes without overwriting or executing retained artifacts.
        with tempfile.TemporaryDirectory(prefix="homefx-history-") as temporary:
            repository.build(Path(temporary) / "candidate", retain_manifest=inventory_path)
        return {"packages": len(current), "previous": len(prior), "current": versions}
    except HistoryError:
        raise
    except Exception:
        raise HistoryError("invalid release history") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    previous = parser.add_mutually_exclusive_group()
    previous.add_argument("--previous", type=Path)
    previous.add_argument("--base-ref")
    args = parser.parse_args()
    try:
        result = verify_history(args.path, args.previous, base_ref=args.base_ref)
    except HistoryError as error:
        parser.exit(1, "Release history check failed: " + str(error) + "\n")
    print("Checked {packages} packages; preserved {previous} prior records.".format(**result))
    print("Local integrity and history only; source trust and device acceptance remain separate.")


if __name__ == "__main__":
    main()
