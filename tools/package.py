"""Validate and reproducibly package only reviewed runtime files."""
import ast
import hashlib
import re
from defusedxml import ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "plugin.video.homefx"
FILES = ("LICENSE", "addon.xml", "default.py", "resources/__init__.py",
         "resources/lib/__init__.py", "resources/lib/catalogue.py",
         "resources/lib/routes.py", "resources/lib/state.py",
         "resources/art/icon.png", "resources/art/poster.png", "resources/art/fanart.png")


def parse_manifest(data):
    """Reject oversized input, DTDs and entities in source and ZIP manifests."""
    if len(data) > 1024 * 1024:
        raise ValueError("Manifest exceeds 1 MiB limit")
    return ET.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def validate(source=ADDON):
    manifest_path = source / "addon.xml"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Missing or unsafe packaged manifest")
    with manifest_path.open("rb") as stream:
        manifest = parse_manifest(stream.read(1024 * 1024 + 1))
    if manifest.tag != "addon" or manifest.get("id") != "plugin.video.homefx":
        raise ValueError("Unexpected add-on ID")
    version = manifest.get("version", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected numeric major.minor.patch version")
    dep = manifest.find("./requires/import[@addon='xbmc.python']")
    if dep is None or dep.get("version") != "3.0.1":
        raise ValueError("Preview targets Kodi Python API 3.0.1")
    plugin = manifest.find("./extension[@point='xbmc.python.pluginsource']")
    if plugin is None or plugin.get("library") != "default.py" or plugin.findtext("provides") != "video":
        raise ValueError("Invalid plugin entry point")
    for path in FILES:
        file = source / path
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing or unsafe packaged file: " + path)
        if path.endswith(".py"):
            ast.parse(file.read_text(encoding="utf-8"), feature_version=(3, 8))
    for asset in manifest.findall("./extension[@point='xbmc.addon.metadata']/assets/*"):
        if asset.text not in FILES:
            raise ValueError("Manifest asset not in package allowlist")
    if (source / "LICENSE").read_bytes() != (ROOT / "LICENSE").read_bytes():
        raise ValueError("Package licence differs from root licence")
    return version


def build(source=ADDON, output=None):
    version = validate(source)
    output = Path(output) if output else ROOT / "dist"
    output.mkdir(parents=True, exist_ok=True)
    dest = output / ("plugin.video.homefx-" + version + ".zip")
    with ZipFile(dest, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(FILES):
            entry = ZipInfo("plugin.video.homefx/" + path, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, (source / path).read_bytes())
    with ZipFile(dest) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt package")
        packed = parse_manifest(archive.read("plugin.video.homefx/addon.xml"))
        if packed.get("version") != version:
            raise ValueError("ZIP/manifest version mismatch")
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.with_suffix(".zip.sha256").write_text(digest + "  " + dest.name + "\n")
    return dest


if __name__ == "__main__":
    print(build())
