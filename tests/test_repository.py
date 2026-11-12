"""Local repository tests build original packages only; nothing is published."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("repository_builder", ROOT / "tools/repository.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RepositoryTests(unittest.TestCase):
    def older_video(self, root, version="0.2.0"):
        source = root / ("source-" + version)
        shutil.copytree(r.package.ADDON, source)
        manifest = source / "addon.xml"
        current = r.package.validate(source)
        manifest.write_text(manifest.read_text().replace('version="' + current + '"',
                                                        'version="' + version + '"', 1))
        archive = r.package.build(source, root / "archives")
        return archive

    def inventory(self, root, archives):
        entries = []
        for archive, ident, version in archives:
            entries.append({"id": ident, "version": version,
                            "path": archive.relative_to(root).as_posix(),
                            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()})
        path = root / "retain.json"
        path.write_text(json.dumps({"schema": 1, "packages": entries}))
        return path

    def test_complete_candidate_topology_and_exact_index_checksum(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = r.build(Path(temporary) / "candidate")
            index = r.package.parse_manifest((output / "addons.xml").read_bytes())
            self.assertEqual(index.tag, "addons")
            self.assertEqual([x.get("id") for x in index], ["plugin.video.homefx", "repository.homefx"])
            self.assertEqual((output / "addons.xml.sha256").read_text().strip(),
                             hashlib.sha256((output / "addons.xml").read_bytes()).hexdigest())
            for addon in index:
                ident, version = addon.get("id"), addon.get("version")
                package = output / ident / (ident + "-" + version + ".zip")
                self.assertTrue(package.is_file())
                self.assertEqual(package.with_suffix(".zip.sha256").read_text().split()[0],
                                 hashlib.sha256(package.read_bytes()).hexdigest())
                with ZipFile(package) as archive:
                    actual = r.package.parse_manifest(archive.read(ident + "/addon.xml"))
                    self.assertEqual(r.ET.tostring(addon).strip(), r.ET.tostring(actual).strip())
            repo = index.find("./addon[@id='repository.homefx']/extension[@point='xbmc.addon.repository']/dir")
            self.assertEqual(repo.get("minversion"), "21.0.0")
            self.assertEqual(repo.findtext("checksum"), r.BASE_URL + "addons.xml.sha256")
            self.assertEqual(repo.findtext("datadir"), r.BASE_URL)
            self.assertEqual(repo.findtext("hashes"), "sha256")
            self.assertEqual(repo.find("checksum").get("verify"), "sha256")
            self.assertTrue((output / "plugin.video.homefx/resources/art/icon.png").is_file())
            self.assertIn("NOT AN ACTIVE UPDATE CHANNEL", (output / "CANDIDATE.txt").read_text())

    def test_reproducible_idempotent_and_private_files_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "repo-source"
            shutil.copytree(r.REPOSITORY, source)
            (source / "private.json").write_text('{"synthetic": "private"}')
            (source / "profile").mkdir()
            (source / "profile/tokens.sqlite3").write_bytes(b"synthetic private state")
            first = r.build(root / "first", repository_source=source)
            second = r.build(root / "second", repository_source=source)
            self.assertEqual(r._tree_bytes(first), r._tree_bytes(second))
            self.assertEqual(r.build(first, repository_source=source), first)
            with ZipFile(next((first / "repository.homefx").glob("*.zip"))) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"repository.homefx/LICENSE", "repository.homefx/addon.xml"})
            self.assertFalse(any("private" in key or "profile" in key for key in r._tree_bytes(first)))

    def test_existing_different_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = r.build(Path(temporary) / "candidate")
            extra = output / "keep-me.txt"
            extra.write_text("unrelated")
            before = r._tree_bytes(output)
            with self.assertRaisesRegex(ValueError, "fresh output"):
                r.build(output)
            self.assertEqual(r._tree_bytes(output), before)

    def test_repository_manifest_contract_mutations_are_rejected(self):
        mutations = [("https://", "http://"), ('minversion="21.0.0"', 'minversion="20.0.0"'),
                     ("repository.homefx", "../escape"), ('version="0.1.0"', 'version="bad"'),
                     ("<hashes>sha256</hashes>", "<hashes>false</hashes>"),
                     ("addons.xml.sha256", "different.xml.sha256")]
        for old, new in mutations:
            with self.subTest(value=new), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                shutil.copytree(r.REPOSITORY, source)
                manifest = source / "addon.xml"
                original = manifest.read_text()
                self.assertIn(old, original)
                manifest.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    r.build(root / "output", repository_source=source)
                self.assertFalse((root / "output").exists())

    def test_manifest_entities_and_symlinked_sources_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            shutil.copytree(r.REPOSITORY, source)
            (source / "addon.xml").write_bytes(b'<!DOCTYPE addon><addon/>')
            with self.assertRaises(r.ET.DTDForbidden):
                r.build(root / "output", repository_source=source)
            (source / "addon.xml").unlink()
            (source / "addon.xml").symlink_to(r.REPOSITORY / "addon.xml")
            with self.assertRaisesRegex(ValueError, "unsafe source"):
                r.build(root / "output", repository_source=source)

    def test_corrupt_archive_and_identity_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "repository.homefx-0.1.0.zip"
            path.write_bytes(b"not a ZIP")
            with self.assertRaisesRegex(ValueError, "Invalid ZIP"):
                r.inspect_package(path, "repository.homefx", "0.1.0", r.REPO_FILES)
            with ZipFile(path, "w") as archive:
                archive.writestr("repository.homefx/LICENSE", (ROOT / "LICENSE").read_bytes())
                archive.writestr("repository.homefx/addon.xml",
                                 (r.REPOSITORY / "addon.xml").read_bytes().replace(b'"0.1.0"', b'"0.2.0"'))
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                r.inspect_package(path, "repository.homefx", "0.1.0", r.REPO_FILES)

    def test_unexpected_duplicate_or_symlink_zip_entries_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "repository.homefx-0.1.0.zip"
            for extra in ("../outside", "repository.homefx/private.json", "repository.homefx/addon.xml"):
                with self.subTest(extra=extra), ZipFile(path, "w") as archive:
                    archive.writestr("repository.homefx/LICENSE", (ROOT / "LICENSE").read_bytes())
                    archive.writestr("repository.homefx/addon.xml", (r.REPOSITORY / "addon.xml").read_bytes())
                    archive.writestr(extra, b"synthetic")
                with self.assertRaisesRegex(ValueError, "allowlist"):
                    r.inspect_package(path, "repository.homefx", "0.1.0", r.REPO_FILES)
            with ZipFile(path, "w") as archive:
                archive.writestr("repository.homefx/LICENSE", (ROOT / "LICENSE").read_bytes())
                entry = ZipInfo("repository.homefx/addon.xml")
                entry.create_system = 3
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, b"outside")
            with self.assertRaisesRegex(ValueError, "Unsafe ZIP"):
                r.inspect_package(path, "repository.homefx", "0.1.0", r.REPO_FILES)

    def test_duplicate_addon_ids_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = r.build(Path(temporary) / "candidate")
            path = next((output / "repository.homefx").glob("*.zip"))
            item = (path, "repository.homefx", "0.1.0", r.REPO_FILES)
            with self.assertRaisesRegex(ValueError, "Duplicate add-on ID"):
                r._write_index([item, item], output)

    def test_output_symlink_and_oversized_archive_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            output = root / "candidate"
            output.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Unsafe output"):
                r.build(output)
            path = root / "repository.homefx-0.1.0.zip"
            with path.open("wb") as stream:
                stream.truncate(r.MAX_PACKAGE + 1)
            with self.assertRaisesRegex(ValueError, "oversized"):
                r.inspect_package(path, "repository.homefx", "0.1.0", r.REPO_FILES)

    def test_retained_versions_are_reproducible_without_changing_advertised_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = self.older_video(root)
            inventory = self.inventory(root, [(old, "plugin.video.homefx", "0.2.0")])
            first = r.build(root / "first", retain_manifest=inventory)
            second = r.build(root / "second", retain_manifest=inventory)
            self.assertEqual(r._tree_bytes(first), r._tree_bytes(second))
            self.assertEqual(r.build(first, retain_manifest=inventory), first)
            retained = first / "plugin.video.homefx" / old.name
            self.assertEqual(retained.read_bytes(), old.read_bytes())
            self.assertEqual(retained.with_suffix(".zip.sha256").read_text().split()[0],
                             hashlib.sha256(old.read_bytes()).hexdigest())
            index = r.package.parse_manifest((first / "addons.xml").read_bytes())
            self.assertEqual(index.find("./addon[@id='plugin.video.homefx']").get("version"),
                             r.package.validate())
            self.assertEqual(len(index), 2)
            output_inventory = json.loads((first / "release-inventory.json").read_text())
            self.assertEqual(len(output_inventory["packages"]), 3)

    def test_generated_inventory_can_be_reused_without_repacking_identical_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = r.build(root / "first")
            second = r.build(root / "second", retain_manifest=first / "release-inventory.json")
            self.assertEqual(r._tree_bytes(first), r._tree_bytes(second))

    def test_retained_older_package_can_omit_new_modules_but_not_core_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.older_video(root)
            with ZipFile(archive) as stream:
                members = {name: stream.read(name) for name in stream.namelist()
                           if "/trakt_" not in name}
            with ZipFile(archive, "w") as stream:
                for name, content in members.items():
                    stream.writestr(name, content)
            inventory = self.inventory(root, [(archive, "plugin.video.homefx", "0.2.0")])
            output = r.build(root / "accepted", retain_manifest=inventory)
            self.assertEqual((output / "plugin.video.homefx" / archive.name).read_bytes(), archive.read_bytes())
            del members["plugin.video.homefx/default.py"]
            with ZipFile(archive, "w") as stream:
                for name, content in members.items():
                    stream.writestr(name, content)
            self.inventory(root, [(archive, "plugin.video.homefx", "0.2.0")])
            with self.assertRaisesRegex(ValueError, "allowlist"):
                r.build(root / "rejected", retain_manifest=inventory)

    def test_inventory_hash_schema_duplicates_and_bounds_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.older_video(root)
            inventory = self.inventory(root, [(archive, "plugin.video.homefx", "0.2.0")])
            valid = json.loads(inventory.read_text())
            mutations = [dict(valid, schema=True), dict(valid, extra="not allowed"),
                         dict(valid, packages=valid["packages"] * 2),
                         dict(valid, packages=valid["packages"] * (r.MAX_RETAINED + 1))]
            for key, value in [("sha256", "0" * 64), ("id", "plugin.other"),
                               ("version", "0.02.0"), ("version", "0.0.0")]:
                entry = dict(valid["packages"][0], **{key: value})
                mutations.append(dict(valid, packages=[entry]))
            for index, value in enumerate(mutations):
                with self.subTest(index=index):
                    inventory.write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        r.build(root / ("out-" + str(index)), retain_manifest=inventory)
            inventory.write_text('{"schema":1,"schema":1,"packages":[]}')
            with self.assertRaisesRegex(ValueError, "Invalid release inventory"):
                r.build(root / "duplicate-field", retain_manifest=inventory)
            inventory.write_bytes(b" " * (r.MAX_INVENTORY + 1))
            with self.assertRaisesRegex(ValueError, "size bound"):
                r.build(root / "large", retain_manifest=inventory)

    def test_inventory_paths_and_symlink_components_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.older_video(root)
            inventory = self.inventory(root, [(archive, "plugin.video.homefx", "0.2.0")])
            valid = json.loads(inventory.read_text())
            for index, relative in enumerate((str(archive), "../" + archive.name,
                                              "archives/../" + archive.name,
                                              "archives\\" + archive.name)):
                entry = dict(valid["packages"][0], path=relative)
                inventory.write_text(json.dumps(dict(valid, packages=[entry])))
                with self.assertRaisesRegex(ValueError, "Unsafe inventory path"):
                    r.build(root / ("out-" + str(index)), retain_manifest=inventory)
            (root / "alias").symlink_to(root / "archives", target_is_directory=True)
            entry = dict(valid["packages"][0], path="alias/" + archive.name)
            inventory.write_text(json.dumps(dict(valid, packages=[entry])))
            with self.assertRaisesRegex(ValueError, "Symlinked"):
                r.build(root / "symlink", retain_manifest=inventory)

    def test_aggregate_byte_and_total_release_bounds_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.older_video(root)
            inventory = self.inventory(root, [(archive, "plugin.video.homefx", "0.2.0")])
            with patch.object(r, 'MAX_RETAINED_BYTES', archive.stat().st_size - 1):
                with self.assertRaisesRegex(ValueError, 'total size bound'):
                    r.build(root / 'oversized', retain_manifest=inventory)
            with patch.object(r, 'MAX_RETAINED', 2):
                with self.assertRaisesRegex(ValueError, 'release count bound'):
                    r.build(root / 'too-many', retain_manifest=inventory)
            self.assertFalse((root / 'oversized').exists())
            self.assertFalse((root / 'too-many').exists())

    def test_future_release_and_same_version_changed_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            newer = self.older_video(root, "10.0.0")
            current_source = root / "current-source"
            shutil.copytree(r.package.ADDON, current_source)
            manifest = current_source / "addon.xml"
            manifest.write_text(manifest.read_text().replace('version="' + r.package.validate() + '"',
                                                            'version="9.0.0"', 1))
            inventory = self.inventory(root, [(newer, "plugin.video.homefx", "10.0.0")])
            with self.assertRaisesRegex(ValueError, "newer"):
                r.build(root / "future", video_source=current_source, retain_manifest=inventory)
            same = self.older_video(root, r.package.validate())
            with ZipFile(same, "a") as archive:
                archive.comment = b"changed package identity"
            inventory = self.inventory(root, [(same, "plugin.video.homefx", r.package.validate())])
            with self.assertRaisesRegex(ValueError, "different package bytes"):
                r.build(root / "changed", retain_manifest=inventory)

    def test_hash_matching_malicious_or_corrupt_retained_content_is_still_rejected(self):
        for mutation in ("private", "dtd", "syntax", "corrupt", "version", "service"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archive = self.older_video(root)
                with ZipFile(archive) as stream:
                    contents = {name: stream.read(name) for name in stream.namelist()}
                if mutation == "private":
                    contents["plugin.video.homefx/profile/tokens.sqlite3"] = b"synthetic"
                elif mutation == "dtd":
                    contents["plugin.video.homefx/addon.xml"] = b'<!DOCTYPE addon><addon/>'
                elif mutation == "syntax":
                    contents["plugin.video.homefx/default.py"] = b"def broken("
                elif mutation == "version":
                    contents["plugin.video.homefx/addon.xml"] = contents["plugin.video.homefx/addon.xml"].replace(
                        b'version="0.2.0"', b'version="0.1.0"', 1)
                elif mutation == "service":
                    contents["plugin.video.homefx/addon.xml"] = contents["plugin.video.homefx/addon.xml"].replace(
                        b"</addon>", b'<extension point="xbmc.service" library="default.py"/></addon>')
                with ZipFile(archive, "w") as stream:
                    for name, value in contents.items():
                        stream.writestr(name, value)
                if mutation == "corrupt":
                    archive.write_bytes(b"not a zip")
                inventory = self.inventory(root, [(archive, "plugin.video.homefx", "0.2.0")])
                with self.assertRaises((ValueError, r.ET.DTDForbidden)):
                    r.build(root / "out", retain_manifest=inventory)


if __name__ == "__main__":
    unittest.main()
