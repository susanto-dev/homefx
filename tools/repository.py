"""Build a local Kodi repository candidate, never publish or download content.

Kodi 21.2 supports an explicitly verified index checksum and ZIP SHA-256 sidecar
fallback when custom Content-SHA256 headers are absent. These hashes detect
corruption but are not signatures. HTTPS and trusted publication remain essential.
"""
import argparse
import hashlib
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
CANDIDATE_NOTICE = """HomeFX repository candidate — NOT AN ACTIVE UPDATE CHANNEL

These artifacts are for review and device-test preparation only. The HTTPS endpoint
in repository.homefx is reserved and is not deployed by this build or the preview
site. Installing the candidate repository ZIP does not establish a working channel.

Before activation: retain immutable known-good versions, publish packages before
updating the index, verify HTTPS paths, and test fresh installation and upgrades on
Kodi 21.2/Android TV. No live installation, update or rollback is claimed here.

addons.xml.sha256 is a verified Kodi change marker, not a signature or authenticity
proof. ZIP SHA-256 sidecars support Kodi integrity checks and manual comparison;
the hosting origin must still be trusted. Do not upload profiles, private configuration or credentials.
"""


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


def inspect_package(path, expected_id, expected_version, allowed_files):
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
            if len(members) != len(expected) or {i.filename for i in members} != expected:
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
    result = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Unsafe output entry")
        if path.is_file():
            if path.stat().st_size > MAX_CONTENT:
                raise ValueError("Output file exceeds size bound")
            result[path.relative_to(directory).as_posix()] = path.read_bytes()
        elif not path.is_dir():
            raise ValueError("Unexpected output entry")
    return result


def build(output=None, video_source=package.ADDON, repository_source=REPOSITORY):
    """Build fresh or verify an identical output tree; never overwrite stale files."""
    output = Path(output) if output is not None else ROOT / "dist/repository"
    video_source, repository_source = Path(video_source), Path(repository_source)
    repo_data, repo_version = _repository_manifest(repository_source)
    video_version = package.validate(video_source)
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
        (staged / "CANDIDATE.txt").write_text(CANDIDATE_NOTICE, encoding="utf-8")
        if output.exists() or output.is_symlink():
            if _tree_bytes(output) != _tree_bytes(staged):
                raise ValueError("Output differs; use a fresh output directory")
        else:
            os.rename(str(staged), str(output))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Fresh or identical candidate directory")
    args = parser.parse_args()
    print(build(args.output))
