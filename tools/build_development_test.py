"""Build an explicit Development-only Kodi test ZIP; never publish or contact Trakt."""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import check_trakt_config
import package

ROOT = package.ROOT
ADDON_ID = "script.homefx.development"
VIDEO_ID = "plugin.video.homefx.development"
VERSION = "0.1.0"
MAX_FILE = 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_ZIP = 16 * 1024 * 1024
SCRIPT_FILES = ("addon.xml", "default.py", "resources/lib/development_test.py")
# These implement the synthetic public Preview, not either Development entry.
PREVIEW_ONLY_FILES = frozenset({
    "resources/lib/catalogue.py", "resources/lib/state.py", "resources/lib/routes.py",
})
RUNTIME_FILES = tuple(name for name in package.FILES if name not in PREVIEW_ONLY_FILES and (
    name == "resources/__init__.py" or name == "resources/art/icon.png"
    or (name.startswith("resources/lib/") and name.endswith(".py"))))


class BuildError(ValueError):
    """Fixed build diagnostics; no configuration values or local paths."""


def _require(condition):
    if not condition:
        raise BuildError("development test build failed")


def _no_symlinks(path):
    _require(not any(item.is_symlink() for item in (path,) + tuple(path.parents)))


def _read(path, bound=MAX_FILE):
    _no_symlinks(path)
    _require(stat.S_ISREG(path.lstat().st_mode))
    with path.open("rb") as stream:
        data = stream.read(bound + 1)
    _require(len(data) <= bound)
    return data


def _configuration(environment):
    _require(environment.get("HOMEFX_TRAKT_ENVIRONMENT") == "Development")
    check_trakt_config.check(environment)
    value = {"schema": 1, "environment": "Development",
             "client_id": environment["TRAKT_CLIENT_ID"],
             "redirect_uri": environment["TRAKT_REDIRECT_URI"]}
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    _require(len(data) <= 4096)
    return data


def _manifest(data, video=False):
    addon_id = VIDEO_ID if video else ADDON_ID
    extension = "xbmc.python.pluginsource" if video else "xbmc.python.script"
    manifest = package.parse_manifest(data)
    _require(manifest.tag == "addon" and manifest.get("id") == addon_id
             and manifest.get("version") == VERSION
             and manifest.get("provider-name") == "susanto-dev"
             and bool(manifest.get("name", "").strip()))
    requires = manifest.findall("requires")
    _require(len(requires) == 1 and len(requires[0]) == 1)
    dependency = requires[0][0]
    _require(dependency.tag == "import" and dependency.get("addon") == "xbmc.python"
             and dependency.get("version") == "3.0.1" and not len(dependency)
             and dependency.get("optional", "false") == "false")
    extensions = manifest.findall("extension")
    _require(len(extensions) == 2 and {item.get("point") for item in extensions} == {
        extension, "xbmc.addon.metadata"})
    script = manifest.find("./extension[@point='" + extension + "']")
    _require(script.get("library") == "default.py")
    _require(not len(script) or (len(script) == 1 and script[0].tag == "provides"
                                and script[0].text == ("video" if video else "executable") and not len(script[0])))
    metadata = manifest.find("./extension[@point='xbmc.addon.metadata']")
    for name, expected in (("license", "MIT"), ("platform", "all")):
        nodes = metadata.findall(name)
        _require(len(nodes) == 1 and nodes[0].text == expected and not len(nodes[0]))
    assets = metadata.findall("assets")
    _require(len(assets) == 1 and len(assets[0]) == 1 and assets[0][0].tag == "icon"
             and assets[0][0].text == "resources/art/icon.png" and not len(assets[0][0]))


def _sources(root, configuration, video=False):
    script = root / "addons" / (VIDEO_ID if video else ADDON_ID)
    runtime = root / "addons" / "plugin.video.homefx"
    source_files = ("addon.xml", "default.py", "resources/lib/development_video.py") if video else SCRIPT_FILES
    files = {name: _read(script / name) for name in source_files}
    runtime_files = RUNTIME_FILES + (("resources/art/poster.png", "resources/art/fanart.png") if video else ())
    files.update({name: _read(runtime / name) for name in runtime_files})
    files["LICENSE"] = _read(root / "LICENSE")
    _require(files["LICENSE"] == _read(runtime / "LICENSE"))
    files["resources/development.json"] = configuration
    _require(len(files) <= 128 and sum(map(len, files.values())) <= MAX_TOTAL)
    _manifest(files["addon.xml"], video)
    for name, data in files.items():
        if name.endswith(".py"):
            ast.parse(data.decode("utf-8"), filename=name, feature_version=(3, 11))
    return files


def build(output, environment, *, video=False):
    """Write a fresh or identical complete ZIP/sidecar directory, with public config.

    Only explicit allowlisted original project files enter the archive. No account
    stores are read or generated. Source and destination parents must be quiescent.
    Existing differing or partial output is never repaired or overwritten.
    """
    try:
        _require(type(video) is bool)
        addon_id = VIDEO_ID if video else ADDON_ID
        configuration = _configuration(environment)
        root = Path(ROOT).absolute()
        _no_symlinks(root)
        output = Path(output).absolute()
        _no_symlinks(output)
        _require(".." not in output.parts and output != root)
        _require(root not in output.parents or root / "dist" in output.parents)
        files = _sources(root, configuration, video)
        stream = io.BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                entry = ZipInfo(addon_id + "/" + name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, data)
        data = stream.getvalue()
        _require(len(data) <= MAX_ZIP)
        with ZipFile(io.BytesIO(data)) as archive:
            _require(archive.testzip() is None and len(archive.infolist()) == len(files))
            _manifest(archive.read(addon_id + "/addon.xml"), video)
        digest = hashlib.sha256(data).hexdigest()
        name = addon_id + "-" + VERSION + "-" + digest + ".zip"
        checksum = (digest + "  " + name + "\n").encode("ascii")
        expected = {name: data, name + ".sha256": checksum}
        if output.exists():
            _require(output.is_dir() and {path.name for path in output.iterdir()} == set(expected))
            _require(all(_read(output / filename, MAX_ZIP) == content
                         for filename, content in expected.items()))
            return output / name
        output.parent.mkdir(parents=True, exist_ok=True)
        _no_symlinks(output.parent)
        with tempfile.TemporaryDirectory(prefix=".homefx-development-", dir=str(output.parent)) as temporary:
            staged = Path(temporary) / "output"
            staged.mkdir()
            for filename, content in expected.items():
                with (staged / filename).open("xb") as target:
                    target.write(content)
            _require(not output.exists() and not output.is_symlink())
            os.rename(str(staged), str(output))
        return output / name
    except Exception:
        raise BuildError("development test build failed") from None


def main(argv=None, environment=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "dist/development-test",
                        help="Fresh or identical development artifact directory")
    args = parser.parse_args(argv)
    try:
        build(args.output, os.environ if environment is None else environment)
    except BuildError:
        print("Development test build failed.", file=sys.stderr)
        return 1
    print("Prepared Development test ZIP and SHA-256. Public application configuration is included; nothing published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
