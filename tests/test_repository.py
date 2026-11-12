"""Local repository tests build original packages only; nothing is published."""
import hashlib
import importlib.util
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("repository_builder", ROOT / "tools/repository.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RepositoryTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
