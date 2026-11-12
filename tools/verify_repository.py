"""Read-only integrity and structure checks for an unpublished repository candidate."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZipFile

import package
import repository

IDS = ("plugin.video.homefx", "repository.homefx")
ROOT_FILES = {"addons.xml", "addons.xml.sha256", "release-inventory.json", "CANDIDATE.txt"}
MAX_FILES = 256
MAX_TOTAL = 128 * 1024 * 1024


class VerificationError(ValueError):
    """A fixed error category that does not disclose candidate filenames or contents."""


def _require(condition, category):
    if not condition:
        raise VerificationError(category)


def _snapshot(root):
    root = Path(root).absolute()
    _require(not any(p.is_symlink() for p in (root,) + tuple(root.parents)), "candidate topology")
    _require(root.is_dir(), "candidate topology")
    files, directories = {}, set()
    pending, total, nodes = [root], 0, 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                nodes += 1
                _require(nodes <= 512 and not entry.is_symlink(), "candidate topology")
                path = Path(entry.path)
                name = path.relative_to(root).as_posix()
                if entry.is_dir(follow_symlinks=False):
                    directories.add(name)
                    pending.append(path)
                else:
                    _require(entry.is_file(follow_symlinks=False), "candidate topology")
                    _require(len(files) < MAX_FILES, "candidate bounds")
                    maximum = repository.MAX_PACKAGE if name.endswith(".zip") else repository.MAX_CONTENT
                    _require(entry.stat(follow_symlinks=False).st_size <= maximum, "candidate bounds")
                    with path.open("rb") as stream:
                        data = stream.read(maximum + 1)
                    total += len(data)
                    _require(len(data) <= maximum and total <= MAX_TOTAL, "candidate bounds")
                    files[name] = data
    return files, directories


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "inventory duplicate key")
        result[key] = value
    return result


def _inventory(data):
    _require(len(data) <= repository.MAX_INVENTORY, "inventory bounds")
    value = json.loads(data, object_pairs_hook=_pairs)
    _require(isinstance(value, dict) and set(value) == {"schema", "packages"}, "inventory schema")
    _require(type(value["schema"]) is int and value["schema"] == 1, "inventory schema")
    records = value["packages"]
    _require(isinstance(records, list) and 2 <= len(records) <= 32, "inventory bounds")
    seen = set()
    for item in records:
        _require(isinstance(item, dict) and set(item) == {"id", "version", "path", "sha256"}, "inventory schema")
        ident, version = item["id"], item["version"]
        _require(isinstance(ident, str) and ident in IDS, "inventory identity")
        repository._version(version)
        _require((ident, version) not in seen, "inventory duplicate identity")
        seen.add((ident, version))
        _require(item["path"] == ident + "/" + ident + "-" + version + ".zip", "inventory path")
        _require(isinstance(item["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), "inventory hash")
    _require({item["id"] for item in records} == set(IDS), "inventory identity")
    return records


def _archive(data, ident, version):
    allowed = set(package.FILES if ident == IDS[0] else repository.REPO_FILES)
    required = {"LICENSE", "addon.xml", "default.py", "resources/__init__.py", "resources/lib/__init__.py"} if ident == IDS[0] else allowed
    if ident == IDS[0]:
        local_manifest = repository._manifest(
            repository._safe_file(package.ADDON, "addon.xml", 1024 * 1024), ident)
        if version == local_manifest.get("version"):
            required = allowed
    with ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        _require(len(names) == len(set(names)) and len(names) <= len(allowed), "package topology")
        _require(sum(entry.file_size for entry in entries) <= repository.MAX_CONTENT, "package bounds")
        relative = {ident + "/" + name: name for name in allowed}
        _require(set(names) <= set(relative) and {ident + "/" + name for name in required} <= set(names), "package topology")
        contents = {}
        for entry in entries:
            mode = entry.external_attr >> 16
            _require(not entry.is_dir() and not entry.flag_bits & 1 and stat.S_IFMT(mode) in (0, stat.S_IFREG), "package topology")
            contents[relative[entry.filename]] = archive.read(entry)
    manifest = repository._manifest(contents["addon.xml"], ident, version)
    _require(contents["LICENSE"] == (package.ROOT / "LICENSE").read_bytes(), "package licence")
    repository._retained_contract(manifest, contents, ident)
    if ident == IDS[1]:
        extension = manifest.find("./extension[@point='xbmc.addon.repository']")
        _require(len(extension) == 1, "repository configuration")
        directory = extension.find("dir")
        expected = {
            "info": (repository.BASE_URL + "addons.xml", {}),
            "checksum": (repository.BASE_URL + "addons.xml.sha256", {"verify": "sha256"}),
            "datadir": (repository.BASE_URL, {"zip": "true"}),
            "hashes": ("sha256", {}),
        }
        _require(directory.attrib == {"minversion": "21.0.0"} and len(directory) == 4, "repository configuration")
        _require({node.tag for node in directory} == set(expected), "repository configuration")
        for node in directory:
            _require((node.text, node.attrib) == expected[node.tag] and not len(node), "repository configuration")
    for asset in manifest.findall("./extension[@point='xbmc.addon.metadata']/assets/*"):
        _require(asset.text in contents and asset.text in allowed, "package asset")
    return manifest, contents


def _semantic(element):
    return (element.tag, sorted(element.attrib.items()), (element.text or "").strip(),
            (element.tail or "").strip(), tuple(_semantic(child) for child in element))


def _verify(root):
    files, directories = _snapshot(root)
    _require(ROOT_FILES <= set(files), "candidate topology")
    _require(files["CANDIDATE.txt"] == repository.CANDIDATE_NOTICE.encode("utf-8"), "inactive notice")
    index = files["addons.xml"]
    _require(files["addons.xml.sha256"] == (hashlib.sha256(index).hexdigest() + "\n").encode("ascii"), "index checksum")
    manifests = package.parse_manifest(index)
    _require(manifests.tag == "addons" and not manifests.attrib and not (manifests.text or "").strip() and len(manifests) == 2, "index structure")
    indexed = {}
    for manifest in manifests:
        ident = manifest.get("id")
        _require(manifest.tag == "addon" and ident in IDS and ident not in indexed, "index identity")
        repository._version(manifest.get("version"))
        indexed[ident] = manifest
    records = _inventory(files["release-inventory.json"])
    latest = {ident: max((item["version"] for item in records if item["id"] == ident), key=repository._version) for ident in IDS}
    expected = set(ROOT_FILES)
    for ident in IDS:
        _require(indexed[ident].get("version") == latest[ident], "index latest version")
    for item in records:
        path, ident, version = item["path"], item["id"], item["version"]
        sidecar = path + ".sha256"
        expected.update((path, sidecar))
        _require(path in files and sidecar in files, "candidate topology")
        digest = hashlib.sha256(files[path]).hexdigest()
        _require(digest == item["sha256"], "package checksum")
        _require(files[sidecar] == (digest + "  " + PurePosixPath(path).name + "\n").encode("ascii"), "package sidecar")
        manifest, contents = _archive(files[path], ident, version)
        if version == latest[ident]:
            _require(_semantic(manifest) == _semantic(indexed[ident]), "index package manifest")
            for asset in manifest.findall("./extension[@point='xbmc.addon.metadata']/assets/*"):
                target = ident + "/" + asset.text
                expected.add(target)
                _require(files.get(target) == contents[asset.text], "index asset")
    expected_dirs = {str(parent) for name in expected for parent in PurePosixPath(name).parents if str(parent) != "."}
    _require(set(files) == expected and directories == expected_dirs, "candidate topology")
    return {"packages": len(records), "retained": len(records) - 2, "current": latest}


def verify(path):
    """Check a local candidate without changing it; return only validated identities/counts.

    Checksums establish consistency, not authenticity. Run on a quiescent local
    artifact; concurrent modification is not supported.
    """
    try:
        return _verify(path)
    except VerificationError:
        raise
    except Exception:
        raise VerificationError("invalid candidate") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.path)
    except VerificationError as error:
        parser.exit(1, "Candidate verification failed: " + str(error) + "\n")
    print("Checked {packages} packages ({retained} retained).".format(**result))
    for ident, version in sorted(result["current"].items()):
        print(ident + " " + version)
    print("Integrity and structure checked; authenticity, publication and device acceptance are not established.")


if __name__ == "__main__":
    main()
