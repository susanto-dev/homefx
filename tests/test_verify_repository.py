"""Detached candidate checks use only locally generated original fixtures."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import package
import repository
import verify_repository as verifier


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        repository.build(self.candidate)

    def inventory(self):
        return json.loads((self.candidate / "release-inventory.json").read_bytes())

    def write_inventory(self, inventory):
        (self.candidate / "release-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")

    def index(self, data):
        (self.candidate / "addons.xml").write_bytes(data)
        (self.candidate / "addons.xml.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")

    def rejected(self):
        with self.assertRaises(verifier.VerificationError) as raised:
            verifier.verify(self.candidate)
        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertNotIn("private", str(raised.exception))

    def rewrite_zip(self, change):
        inventory = self.inventory()
        item = next(i for i in inventory["packages"] if i["id"] == "plugin.video.homefx"
                    and i["version"] == package.validate())
        target = self.candidate / item["path"]
        with ZipFile(target) as archive:
            contents = {entry.filename: archive.read(entry) for entry in archive.infolist()}
        change(contents)
        data = io.BytesIO()
        with ZipFile(data, "w") as archive:
            for name, content in contents.items():
                archive.writestr(name, content)
        target.write_bytes(data.getvalue())
        item["sha256"] = hashlib.sha256(data.getvalue()).hexdigest()
        target.with_suffix(".zip.sha256").write_text(item["sha256"] + "  " + target.name + "\n")
        self.write_inventory(inventory)

    def test_valid_candidate_is_read_only(self):
        def snapshot():
            return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.candidate.rglob("*") if p.is_file()}
        before = snapshot()
        result = verifier.verify(self.candidate)
        self.assertEqual(result["packages"], 2)
        self.assertEqual(result["retained"], 0)
        self.assertEqual(result["current"]["plugin.video.homefx"], package.validate())
        self.assertEqual(before, snapshot())

    def test_preview_channel_is_explicit_and_read_only(self):
        preview = repository.build(self.root / "preview", channel="preview")
        before = repository._tree_bytes(preview)
        self.assertEqual(verifier.verify(preview, channel="preview")["packages"], 2)
        self.assertEqual(before, repository._tree_bytes(preview))
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(preview)
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.candidate, channel="preview")
        for value in (None, [], True, "live"):
            with self.subTest(channel=value), self.assertRaises(verifier.VerificationError):
                verifier.verify(preview, channel=value)

    def test_preview_notice_extra_candidate_notice_and_corruption_are_rejected(self):
        for mutation in ("notice", "extra", "index", "package"):
            with self.subTest(mutation=mutation):
                preview = repository.build(self.root / mutation, channel="preview")
                if mutation == "notice":
                    (preview / "CHANNEL.txt").write_text("Stable production channel")
                elif mutation == "extra":
                    (preview / "CANDIDATE.txt").write_text(repository.CANDIDATE_NOTICE)
                elif mutation == "index":
                    (preview / "addons.xml").write_bytes(b"changed")
                else:
                    target = next(preview.rglob("*.zip"))
                    target.write_bytes(target.read_bytes() + b"changed")
                with self.assertRaises(verifier.VerificationError):
                    verifier.verify(preview, channel="preview")

    def test_preview_current_package_completeness_and_retention_are_preserved(self):
        self.retained_candidate()
        retained_inventory = self.candidate / "release-inventory.json"
        self.candidate = repository.build(self.root / "preview-retained",
                                           retain_manifest=retained_inventory, channel="preview")
        self.assertEqual(verifier.verify(self.candidate, channel="preview")["retained"], 1)
        runtime = next(name for name in package.FILES
                       if name.startswith("resources/lib/") and name.endswith(".py")
                       and not name.endswith("__init__.py"))
        self.rewrite_zip(lambda contents: contents.pop("plugin.video.homefx/" + runtime))
        with self.assertRaises(verifier.VerificationError):
            verifier.verify(self.candidate, channel="preview")

    def test_index_checksum(self):
        (self.candidate / "addons.xml").write_bytes(b"changed")
        self.rejected()

    def test_package_sidecar(self):
        path = next(self.candidate.rglob("*.zip.sha256"))
        path.write_text("0" * 64 + "\n")
        self.rejected()

    def test_package_checksum(self):
        path = next(self.candidate.rglob("*.zip"))
        path.write_bytes(path.read_bytes() + b"changed")
        self.rejected()

    def test_wrong_manifest_after_rehash(self):
        def change(contents):
            key = "plugin.video.homefx/addon.xml"
            contents[key] = contents[key].replace(b'id="plugin.video.homefx"', b'id="plugin.video.other"')
        self.rewrite_zip(change)
        self.rejected()

    def test_manifest_different_from_index_after_rehash(self):
        def change(contents):
            key = "plugin.video.homefx/addon.xml"
            contents[key] = contents[key].replace(b'name="HomeFX Preview"', b'name="Changed"')
        self.rewrite_zip(change)
        self.rejected()

    def test_extra_archive_file_after_rehash(self):
        self.rewrite_zip(lambda contents: contents.update({"plugin.video.homefx/private.json": b"{}"}))
        self.rejected()

    def test_current_runtime_file_missing_after_rehash(self):
        # Remove a non-core module while keeping both outer hashes consistent.
        runtime = next(name for name in package.FILES
                       if name.startswith("resources/lib/")
                       and name.endswith(".py") and not name.endswith("__init__.py"))
        self.rewrite_zip(lambda contents: contents.pop("plugin.video.homefx/" + runtime))
        self.rejected()

    def test_invalid_api_after_rehash(self):
        def change(contents):
            key = "plugin.video.homefx/addon.xml"
            contents[key] = contents[key].replace(b'version="3.0.1"', b'version="2.0.0"')
        self.rewrite_zip(change)
        self.rejected()

    def test_changed_licence_after_rehash(self):
        self.rewrite_zip(lambda contents: contents.update({"plugin.video.homefx/LICENSE": b"changed"}))
        self.rejected()

    def test_missing_inventory_entry(self):
        inventory = self.inventory()
        inventory["packages"].pop()
        self.write_inventory(inventory)
        self.rejected()

    def test_invalid_index_identity(self):
        data = (self.candidate / "addons.xml").read_bytes()
        self.index(data.replace(b'id="repository.homefx"', b'id="plugin.video.homefx"'))
        self.rejected()

    def test_malformed_index(self):
        self.index(b"<addons>")
        self.rejected()

    def test_missing_file(self):
        next(self.candidate.rglob("*.zip")).unlink()
        self.rejected()

    def test_extra_private_file(self):
        (self.candidate / "private.json").write_text("{}")
        self.rejected()

    def test_extra_empty_directory(self):
        (self.candidate / "profile").mkdir()
        self.rejected()

    def test_symlink(self):
        (self.candidate / "private.json").symlink_to(self.candidate / "addons.xml")
        self.rejected()

    def test_unsafe_xml(self):
        self.index(b'<!DOCTYPE addons [<!ENTITY value "content">]><addons>&value;</addons>')
        self.rejected()

    def test_inactive_notice(self):
        (self.candidate / "CANDIDATE.txt").write_text("Published")
        self.rejected()

    def test_inventory_mutations(self):
        original = self.inventory()
        changes = (
            lambda d: d.update(extra=True),
            lambda d: d["packages"][0].update(extra=True),
            lambda d: d["packages"][0].update(sha256="z" * 64),
            lambda d: d["packages"][0].update(path="../private.zip"),
            lambda d: d["packages"].append(d["packages"][0]),
            lambda d: d.update(schema=True),
        )
        for change in changes:
            with self.subTest(change=change):
                value = json.loads(json.dumps(original))
                change(value)
                self.write_inventory(value)
                self.rejected()

    def test_inventory_duplicate_key(self):
        target = self.candidate / "release-inventory.json"
        target.write_text(target.read_text().replace('"schema": 1', '"schema": 1, "schema": 1'))
        self.rejected()

    def test_changed_index_asset(self):
        target = next(p for p in self.candidate.rglob("*.png"))
        target.write_bytes(b"changed")
        self.rejected()

    def retained_candidate(self, subset=False):
        source = self.root / "older-source"
        shutil.copytree(package.ADDON, source)
        manifest = source / "addon.xml"
        manifest.write_text(manifest.read_text().replace('version="' + package.validate() + '"', 'version="0.0.1"', 1))
        archive = package.build(source, self.root / "older")
        if subset:
            with ZipFile(archive) as zipped:
                contents = {entry.filename: zipped.read(entry) for entry in zipped.infolist()}
            removable = next(name for name in contents
                             if "/resources/lib/" in name and name.endswith(".py")
                             and not name.endswith("__init__.py"))
            del contents[removable]
            with ZipFile(archive, "w") as zipped:
                for name, data in contents.items():
                    zipped.writestr(name, data)
        inventory = self.root / "retained.json"
        inventory.write_text(json.dumps({"schema": 1, "packages": [{"id": "plugin.video.homefx", "version": "0.0.1", "path": "older/" + archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}]}))
        self.candidate = self.root / "with-retained"
        repository.build(self.candidate, retain_manifest=inventory)
        return archive

    def test_retained_release_roundtrip(self):
        self.retained_candidate()
        self.assertEqual(verifier.verify(self.candidate)["retained"], 1)

    def test_retained_historical_runtime_subset(self):
        self.retained_candidate(subset=True)
        self.assertEqual(verifier.verify(self.candidate)["retained"], 1)

    def test_index_must_select_latest_inventory_version(self):
        self.retained_candidate()
        data = (self.candidate / "addons.xml").read_bytes()
        self.index(data.replace(('version="' + package.validate() + '"').encode(), b'version="0.0.1"', 1))
        self.rejected()

    def test_bounds_before_inventory_parse(self):
        (self.candidate / "release-inventory.json").write_bytes(b" " * (repository.MAX_INVENTORY + 1))
        self.rejected()


if __name__ == "__main__":
    unittest.main()
