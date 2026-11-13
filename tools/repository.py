"""Build local Kodi repository artifacts, never publish or download content.

Kodi 21.2 supports an explicitly verified index checksum and ZIP SHA-256 sidecar
fallback when custom Content-SHA256 headers are absent. These hashes detect
corruption but are not signatures. HTTPS and trusted publication remain essential.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from zipfile import BadZipFile, ZipFile, ZipInfo, ZIP_DEFLATED

from defusedxml import ElementTree as ET
import package

ROOT = package.ROOT
REPOSITORY = ROOT / "addons/repository.homefx"
REPO_FILES = ("LICENSE", "addon.xml")
BASE_URL = "https://susanto-dev.github.io/homefx/repository/"
MAX_PACKAGE = 16 * 1024 * 1024
MAX_CONTENT = 32 * 1024 * 1024
MAX_INVENTORY = 64 * 1024
MAX_RETAINED = 32
MAX_RETAINED_BYTES = 64 * 1024 * 1024
CANDIDATE_NOTICE = """HomeFX repository candidate — LOCAL REVIEW ARTIFACT

This build is for review and device-test preparation. Generation does not publish
or install anything. Check the deployed endpoint separately; a local candidate is
not evidence of a working channel or Kodi installation/upgrade compatibility.

The index advertises current builds only. Retained versions come from an explicitly
reviewed local inventory and do not activate a downgrade. SHA-256 checks establish
integrity, not signatures or source approval. Never include profiles or credentials.
"""
PREVIEW_NOTICE = """HomeFX experimental preview repository

This directory is prepared for the HomeFX preview installation/update channel.
It contains the synthetic video add-on and this repository add-on. No separate skin,
real account connection, playable sources or playback integration is supplied.

Generation does not publish or install anything. Actual Kodi 21.2/Android TV fresh
installation, updates, offline behavior and rollback require device validation.
Retained immutable versions do not trigger downgrades; the index advertises only
current builds. SHA-256 checks establish integrity, not signatures or source approval.
Never include profiles, private configuration or credentials in published artifacts.
"""


def channel_notice(channel):
    """Return the exact local marker for an explicitly selected output channel."""
    if type(channel) is not str or channel not in {"candidate", "preview"}:
        raise ValueError("Invalid repository channel")
    return (("CANDIDATE.txt", CANDIDATE_NOTICE) if channel == "candidate" else
            ("CHANNEL.txt", PREVIEW_NOTICE))


def _manifest(data, expected_id=None, expected_version=None):
    root = package.parse_manifest(data)
    ident, version = root.get("id", ""), root.get("version", "")
    if (root.tag != "addon" or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", ident)
            or ".." in ident or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)):
        raise ValueError("Invalid packaged identity")
    if expected_id is not None and ident != expected_id:
        raise ValueError("Package ID mismatch")
    if expected_version is not None and version != expected_version:
        raise ValueError("Package version mismatch")
    return root


def _safe_file(source, relative, maximum=MAX_CONTENT):
    file = source / relative
    if source.is_symlink() or file.is_symlink() or not file.is_file():
        raise ValueError("Missing or unsafe source file")
    with file.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Source file exceeds size bound")
    return data


def _repository_manifest(source):
    data = _safe_file(source, "addon.xml", 1024 * 1024)
    root = _manifest(data, "repository.homefx")
    extensions = root.findall("./extension[@point='xbmc.addon.repository']")
    if len(extensions) != 1 or len(extensions[0]) != 1:
        raise ValueError("Expected one repository directory")
    directory = extensions[0].find("dir")
    if directory is None or directory.attrib != {"minversion": "21.0.0"}:
        raise ValueError("Repository must target Kodi 21")
    expected = {"info": BASE_URL + "addons.xml", "checksum": BASE_URL + "addons.xml.sha256",
                "datadir": BASE_URL, "hashes": "sha256"}
    if len(directory) != len(expected):
        raise ValueError("Unexpected repository configuration")
    for name, value in expected.items():
        nodes = directory.findall(name)
        attributes = {"zip": "true"} if name == "datadir" else (
            {"verify": "sha256"} if name == "checksum" else {})
        if len(nodes) != 1 or nodes[0].text != value or nodes[0].attrib != attributes:
            raise ValueError("Repository endpoint or configuration mismatch")
    if _safe_file(source, "LICENSE") != (ROOT / "LICENSE").read_bytes():
        raise ValueError("Repository licence differs from root licence")
    return data, root.get("version")


def inspect_package(path, expected_id, expected_version, allowed_files, required_files=None):
    """Read bounded allowlisted ZIP members without extracting arbitrary paths."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PACKAGE:
        raise ValueError("Missing or oversized package")
    if path.name != expected_id + "-" + expected_version + ".zip":
        raise ValueError("Package filename mismatch")
    expected = {expected_id + "/" + item for item in allowed_files}
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            names = {i.filename for i in members}
            required = expected if required_files is None else {
                expected_id + "/" + item for item in required_files}
            if (len(members) != len(names) or not required <= names <= expected):
                raise ValueError("ZIP entries differ from allowlist")
            if sum(i.file_size for i in members) > MAX_CONTENT:
                raise ValueError("Uncompressed package exceeds size bound")
            for member in members:
                parts = PurePosixPath(member.filename).parts
                if (member.is_dir() or ".." in parts or member.filename.startswith("/")
                        or "\\" in member.filename or member.flag_bits & 1
                        or stat.S_ISLNK(member.external_attr >> 16)):
                    raise ValueError("Unsafe ZIP entry")
            contents = {i.filename[len(expected_id) + 1:]: archive.read(i) for i in members}
    except (BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError("Invalid ZIP package") from error
    root = _manifest(contents["addon.xml"], expected_id, expected_version)
    for node in root.findall("./extension[@point='xbmc.addon.metadata']/assets/*"):
        if node.text not in allowed_files or node.text not in contents:
            raise ValueError("Manifest asset not in package allowlist")
    if contents.get("LICENSE") != (ROOT / "LICENSE").read_bytes():
        raise ValueError("Packaged licence differs from root licence")
    return root, contents


def _version(value):
    if (not isinstance(value, str) or not re.fullmatch(
            r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})", value)):
        raise ValueError("Invalid release version")
    result = tuple(int(part) for part in value.split("."))
    if result == (0, 0, 0):
        raise ValueError("Invalid release version")
    return result


def _no_symlinks(path):
    if any(item.is_symlink() for item in (path,) + tuple(path.parents)):
        raise ValueError("Symlinked inventory input")


def _inventory(path):
    """Read a reviewed local inventory; hashes are not source approval or signatures."""
    path = Path(path).absolute()
    _no_symlinks(path)
    data = _safe_file(path.parent, path.name, MAX_INVENTORY)

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate inventory field")
            result[key] = value
        return result

    try:
        manifest = json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("Invalid release inventory") from None
    if (not isinstance(manifest, dict) or set(manifest) != {"schema", "packages"}
            or type(manifest["schema"]) is not int or manifest["schema"] != 1
            or not isinstance(manifest["packages"], list)
            or len(manifest["packages"]) > MAX_RETAINED):
        raise ValueError("Invalid release inventory")
    records, seen = [], set()
    for item in manifest["packages"]:
        if (not isinstance(item, dict) or set(item) != {"id", "version", "path", "sha256"}
                or item["id"] not in ("plugin.video.homefx", "repository.homefx")
                or not isinstance(item["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise ValueError("Invalid release inventory entry")
        _version(item["version"])
        identity = (item["id"], item["version"])
        if identity in seen:
            raise ValueError("Duplicate release identity")
        seen.add(identity)
        relative = item["path"]
        if (not isinstance(relative, str) or not 1 <= len(relative) <= 512
                or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", relative)
                or any(part in (".", "..") for part in relative.split("/"))):
            raise ValueError("Unsafe inventory path")
        source = path.parent / relative
        _no_symlinks(source)
        if source.name != item["id"] + "-" + item["version"] + ".zip":
            raise ValueError("Inventory package filename mismatch")
        records.append((dict(item), source))
    return records


def _retained_contract(manifest, contents, ident):
    """Check old package shape and syntax, never execute or approve retained code."""
    expected_point = ("xbmc.python.pluginsource" if ident == "plugin.video.homefx"
                      else "xbmc.addon.repository")
    extensions = manifest.findall("extension")
    if (len(extensions) != 2 or {node.get("point") for node in extensions} != {
            expected_point, "xbmc.addon.metadata"}
            or manifest.findtext("./extension[@point='xbmc.addon.metadata']/license") != "MIT"):
        raise ValueError("Invalid retained extension contract")
    if ident == "plugin.video.homefx":
        dep = manifest.find("./requires/import[@addon='xbmc.python']")
        plugin = manifest.find("./extension[@point='xbmc.python.pluginsource']")
        if (len(manifest.findall("./requires/import")) != 1 or dep is None
                or dep.get("version") != "3.0.1" or plugin is None
                or plugin.get("library") != "default.py" or plugin.findtext("provides") != "video"):
            raise ValueError("Invalid retained video contract")
    else:
        # A retained repository must keep the same reviewed origin and integrity policy.
        directory = manifest.find("./extension[@point='xbmc.addon.repository']/dir")
        if (manifest.findall("requires") or directory is None
                or len(manifest.findall("./extension[@point='xbmc.addon.repository']/dir")) != 1
                or directory.get("minversion") != "21.0.0"
                or directory.findtext("info") != BASE_URL + "addons.xml"
                or directory.findtext("checksum") != BASE_URL + "addons.xml.sha256"
                or directory.find("checksum").get("verify") != "sha256"
                or directory.findtext("datadir") != BASE_URL
                or directory.find("datadir").get("zip") != "true"
                or directory.findtext("hashes") != "sha256"):
            raise ValueError("Invalid retained repository contract")
    for name, data in contents.items():
        if name.endswith(".py"):
            try:
                ast.parse(data.decode("utf-8"), feature_version=(3, 8))
            except (SyntaxError, UnicodeError, ValueError, RecursionError):
                raise ValueError("Invalid retained Python syntax") from None


def _retain(records, staged, current):
    total = 0
    for item, source in records:
        ident, version = item["id"], item["version"]
        if _version(version) > _version(current[ident]):
            raise ValueError("Retained release is newer than current build")
        data = _safe_file(source.parent, source.name, MAX_PACKAGE)
        total += len(data)
        if total > MAX_RETAINED_BYTES:
            raise ValueError("Retained packages exceed total size bound")
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Retained package checksum mismatch")
        target = staged / ident / source.name
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError("Existing version has different package bytes")
            continue
        # Inspect the exact bytes whose digest was checked, not a second source read.
        target.write_bytes(data)
        allowed = package.FILES if ident == "plugin.video.homefx" else REPO_FILES
        required = ("LICENSE", "addon.xml", "default.py", "resources/__init__.py",
                    "resources/lib/__init__.py") if ident == "plugin.video.homefx" else REPO_FILES
        manifest, contents = inspect_package(target, ident, version, allowed, required)
        _retained_contract(manifest, contents, ident)
        target.with_suffix(".zip.sha256").write_text(
            item["sha256"] + "  " + target.name + "\n", encoding="ascii")


def _write_inventory(output):
    records = []
    for ident in ("plugin.video.homefx", "repository.homefx"):
        for path in (output / ident).glob("*.zip"):
            version = path.name[len(ident) + 1:-4]
            records.append({"id": ident, "version": version,
                            "path": path.relative_to(output).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if len(records) > MAX_RETAINED:
        raise ValueError("Repository exceeds release count bound")
    records.sort(key=lambda item: (item["id"], _version(item["version"])))
    data = {"schema": 1, "packages": records}
    (output / "release-inventory.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_zip(source, output, version):
    path = output / ("repository.homefx-" + version + ".zip")
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for relative in sorted(REPO_FILES):
            info = ZipInfo("repository.homefx/" + relative, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, _safe_file(source, relative))
    return path


def _write_index(packages, output):
    index = package.parse_manifest(b"<addons/>")
    seen = set()
    for path, ident, version, files in sorted(packages, key=lambda item: item[1]):
        if ident in seen:
            raise ValueError("Duplicate add-on ID")
        seen.add(ident)
        manifest, contents = inspect_package(path, ident, version, files)
        index.append(manifest)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".zip.sha256").write_text(digest + "  " + path.name + "\n", encoding="utf-8")
        for asset in manifest.findall("./extension[@point='xbmc.addon.metadata']/assets/*"):
            target = path.parent / asset.text
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents[asset.text])
    data = ET.tostring(index, encoding="utf-8", xml_declaration=True) + b"\n"
    (output / "addons.xml").write_bytes(data)
    (output / "addons.xml.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n", encoding="ascii")


def _tree_bytes(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Unsafe output directory")
    result, total = {}, 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Unsafe output entry")
        if path.is_file():
            if path.stat().st_size > MAX_CONTENT:
                raise ValueError("Output file exceeds size bound")
            total += path.stat().st_size
            if len(result) >= 256 or total > MAX_RETAINED_BYTES + 2 * MAX_PACKAGE + MAX_CONTENT:
                raise ValueError("Output tree exceeds size bound")
            result[path.relative_to(directory).as_posix()] = path.read_bytes()
        elif not path.is_dir():
            raise ValueError("Unexpected output entry")
    return result


def build(output=None, video_source=package.ADDON, repository_source=REPOSITORY,
          retain_manifest=None, channel="candidate"):
    """Build fresh or verify an identical output tree; never overwrite stale files."""
    notice_name, notice = channel_notice(channel)
    output = Path(output) if output is not None else ROOT / "dist/repository"
    video_source, repository_source = Path(video_source), Path(repository_source)
    repo_data, repo_version = _repository_manifest(repository_source)
    video_version = package.validate(video_source)
    retained = _inventory(retain_manifest) if retain_manifest is not None else []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".repository-candidate-", dir=str(output.parent)) as temporary:
        staged = Path(temporary) / "repository"
        staged.mkdir()
        video_dir, repo_dir = staged / "plugin.video.homefx", staged / "repository.homefx"
        video_dir.mkdir()
        repo_dir.mkdir()
        video_zip = package.build(video_source, video_dir)
        repo_zip = _repo_zip(repository_source, repo_dir, repo_version)
        packaged_repo, contents = inspect_package(repo_zip, "repository.homefx", repo_version, REPO_FILES)
        if contents["addon.xml"] != repo_data or packaged_repo.get("version") != repo_version:
            raise ValueError("Repository package changed during build")
        _write_index([(video_zip, "plugin.video.homefx", video_version, package.FILES),
                      (repo_zip, "repository.homefx", repo_version, REPO_FILES)], staged)
        _retain(retained, staged, {"plugin.video.homefx": video_version,
                                   "repository.homefx": repo_version})
        _write_inventory(staged)
        (staged / notice_name).write_text(notice, encoding="utf-8")
        if output.exists() or output.is_symlink():
            if _tree_bytes(output) != _tree_bytes(staged):
                raise ValueError("Output differs; use a fresh output directory")
        else:
            os.rename(str(staged), str(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fresh or identical candidate directory")
    parser.add_argument("--retain-manifest", type=Path, help="Reviewed local release inventory")
    parser.add_argument("--channel", choices=("candidate", "preview"), default="candidate")
    args = parser.parse_args()
    print(build(args.output, retain_manifest=args.retain_manifest, channel=args.channel))
