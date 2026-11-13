"""Validate and reproducibly package only reviewed runtime files."""
import ast
import hashlib
import os
import re
import stat
import tempfile
from defusedxml import ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "plugin.video.homefx"
FILES = ("LICENSE", "addon.xml", "default.py", "resources/__init__.py",
         "resources/lib/__init__.py", "resources/lib/catalogue.py",
         "resources/lib/routes.py", "resources/lib/state.py",
         "resources/lib/trakt_auth.py", "resources/lib/trakt_tokens.py",
         "resources/lib/trakt_client.py", "resources/lib/trakt_views.py",
         "resources/lib/trakt_transport.py", "resources/lib/trakt_session.py",
         "resources/lib/trakt_library.py", "resources/lib/trakt_calendar.py", "resources/lib/request_limits.py",
         "resources/lib/trakt_preferences.py", "resources/lib/trakt_actions.py",
         "resources/lib/readiness.py", "resources/lib/account_flow.py",
         "resources/lib/account_ui.py", "resources/lib/service_runtime.py",
         "resources/lib/trakt_list_ui.py", "resources/lib/trakt_widget_routes.py",
         "resources/lib/trakt_widget_ui.py",
         "resources/lib/trakt_video.py",
         "resources/lib/storage_probe.py",
         "resources/lib/debrid_auth.py", "resources/lib/debrid_client.py",
         "resources/lib/playback.py", "resources/lib/playback_events.py", "resources/lib/debrid_store.py",
         "resources/lib/debrid_transport.py", "resources/lib/debrid_session.py",
         "resources/art/icon.png", "resources/art/poster.png", "resources/art/fanart.png")


def parse_manifest(data):
    """Reject oversized input, DTDs and entities in source and ZIP manifests."""
    if len(data) > 1024 * 1024:
        raise ValueError("Manifest exceeds 1 MiB limit")
    return ET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def _no_symlinks(path):
    if any(item.is_symlink() for item in (path,) + tuple(path.parents)):
        raise ValueError("Unsafe package path")


def _regular_source(path):
    _no_symlinks(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Unsafe packaged source file")


def validate(source=ADDON):
    source = Path(source).absolute()
    _no_symlinks(source)
    manifest_path = source / "addon.xml"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Missing or unsafe packaged manifest")
    _regular_source(manifest_path)
    with manifest_path.open("rb") as stream:
        manifest = parse_manifest(stream.read(1024 * 1024 + 1))
    if manifest.tag != "addon" or manifest.get("id") != "plugin.video.homefx":
        raise ValueError("Unexpected add-on ID")
    # Require meaningful current-source identity without freezing display branding.
    if any(not manifest.get(name, "").strip() for name in ("name", "provider-name")):
        raise ValueError("Expected nonempty add-on name and provider-name")
    version = manifest.get("version", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected numeric major.minor.patch version")
    # This is the current source contract; retained releases keep their separate
    # archive validator so a build-policy change cannot redefine release history.
    requires = manifest.findall("requires")
    if len(requires) != 1 or len(requires[0]) != 1:
        raise ValueError("Expected one Kodi Python dependency")
    dep = requires[0][0]
    if (dep.tag != "import" or dep.get("addon") != "xbmc.python"
            or dep.get("version") != "3.0.1" or len(dep)
            or dep.get("optional", "false") != "false"):
        raise ValueError("Preview requires Kodi Python API 3.0.1 without third-party dependencies")
    extensions = manifest.findall("extension")
    if (len(extensions) != 2 or {node.get("point") for node in extensions} != {
            "xbmc.python.pluginsource", "xbmc.addon.metadata"}):
        raise ValueError("Expected one plugin and one metadata extension")
    plugin = manifest.find("./extension[@point='xbmc.python.pluginsource']")
    if (plugin.get("library") != "default.py" or len(plugin) != 1
            or plugin[0].tag != "provides" or plugin[0].text != "video" or len(plugin[0])):
        raise ValueError("Invalid plugin entry point")
    metadata = manifest.find("./extension[@point='xbmc.addon.metadata']")
    for name, expected in (("license", "MIT"), ("platform", "all")):
        nodes = metadata.findall(name)
        if len(nodes) != 1 or nodes[0].text != expected or len(nodes[0]):
            raise ValueError("Invalid metadata " + name)
    assets = metadata.findall("assets")
    if len(assets) != 1:
        raise ValueError("Expected one metadata assets declaration")
    expected_assets = {"icon": "resources/art/icon.png", "poster": "resources/art/poster.png",
                       "fanart": "resources/art/fanart.png"}
    names = [asset.tag for asset in assets[0]]
    if "icon" not in names or len(names) != len(set(names)):
        raise ValueError("Expected one metadata icon and unique asset declarations")
    for asset in assets[0]:
        if asset.tag not in expected_assets or asset.text != expected_assets[asset.tag] or len(asset):
            raise ValueError("Manifest asset differs from reviewed artwork")
    for path in FILES:
        file = source / path
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing or unsafe packaged file: " + path)
        _regular_source(file)
        if path.endswith(".py"):
            ast.parse(file.read_text(encoding="utf-8"), feature_version=(3, 11))
    for asset in manifest.findall("./extension[@point='xbmc.addon.metadata']/assets/*"):
        if asset.text not in FILES:
            raise ValueError("Manifest asset not in package allowlist")
    if (source / "LICENSE").read_bytes() != (ROOT / "LICENSE").read_bytes():
        raise ValueError("Package licence differs from root licence")
    return version


def build(source=ADDON, output=None):
    """Stage a validated ZIP/checksum pair; accept only fresh or identical output.

    Source and destination trees must be quiescent. Exclusive links prevent an
    existing target from being overwritten; ordinary publication errors roll back
    newly linked files. A process crash can leave an incomplete pair, which a later
    build rejects rather than repairing or replacing it automatically.
    """
    source = Path(source).absolute()
    version = validate(source)
    output = (Path(output) if output is not None else ROOT / "dist").absolute()
    _no_symlinks(output)
    output.mkdir(parents=True, exist_ok=True)
    dest = output / ("plugin.video.homefx-" + version + ".zip")
    checksum = dest.with_suffix(".zip.sha256")
    with tempfile.TemporaryDirectory(prefix=".homefx-package-", dir=str(output)) as temporary:
        staged = Path(temporary) / dest.name
        staged_checksum = staged.with_suffix(".zip.sha256")
        with ZipFile(staged, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(FILES):
                entry = ZipInfo("plugin.video.homefx/" + path, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, (source / path).read_bytes())
        with ZipFile(staged) as archive:
            if archive.testzip() is not None:
                raise ValueError("Corrupt package")
            packed = parse_manifest(archive.read("plugin.video.homefx/addon.xml"))
            if packed.get("version") != version:
                raise ValueError("ZIP/manifest version mismatch")
        archive_bytes = staged.read_bytes()
        digest = hashlib.sha256(archive_bytes).hexdigest()
        checksum_bytes = (digest + "  " + dest.name + "\n").encode("ascii")
        staged_checksum.write_bytes(checksum_bytes)
        exists = []
        for path, expected in ((dest, archive_bytes), (checksum, checksum_bytes)):
            _no_symlinks(path)
            present = path.exists()
            exists.append(present)
            if present:
                if not stat.S_ISREG(path.stat().st_mode):
                    raise ValueError("Unsafe package output")
                with path.open("rb") as stream:
                    if stream.read(len(expected) + 1) != expected:
                        raise ValueError("Package output differs; use a fresh output directory")
        if any(exists):
            if not all(exists):
                raise ValueError("Incomplete package output; use a fresh output directory")
            return dest
        created = []
        try:
            for prepared, target in ((staged, dest), (staged_checksum, checksum)):
                os.link(str(prepared), str(target))
                created.append(target)
        except Exception:
            for target in reversed(created):
                target.unlink()
            raise
    return dest


if __name__ == "__main__":
    print(build())
