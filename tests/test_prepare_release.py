"""Release proposals use local fixtures and never modify the source checkout."""
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package
import prepare_release as prepare
import release_history
import repository


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "project"
        self.root.mkdir()
        self.releases = self.root / "releases"
        self.releases.mkdir()
        candidate = repository.build(self.parent / "candidate")
        generated = json.loads((candidate / "release-inventory.json").read_text())
        for record in generated["packages"]:
            source = candidate / record["path"]
            record["path"] = "archives/" + source.name
            target = self.releases / record["path"]
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(source.read_bytes())
        self.inventory = self.releases / "inventory.json"
        self.inventory.write_text(json.dumps(generated))
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.commit()
        self.patcher = patch.object(prepare, "ROOT", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root)] + list(args), check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def commit(self):
        self.git("add", "releases")
        self.git("commit", "-qm", "Fixture inventory")
        self.base = self.git("rev-parse", "HEAD")

    def snapshot(self):
        return {p.relative_to(self.releases).as_posix(): p.read_bytes()
                for p in self.releases.rglob("*") if p.is_file()}

    def records(self):
        return json.loads(self.inventory.read_text())

    def assert_rejected(self, name="proposal", base=None):
        output = self.parent / name
        with self.assertRaisesRegex(prepare.PreparationError, "^release preparation failed$"):
            prepare.prepare(base or self.base, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.parent.glob(".release-proposal-*")))

    def test_identical_versions_are_reused_without_input_writes(self):
        before = self.snapshot()
        first = prepare.prepare(self.base, self.parent / "first")
        second = prepare.prepare(self.base, self.parent / "second")
        self.assertEqual(before, self.snapshot())
        self.assertEqual(release_history.verify_history(first / "inventory.json")["packages"], 2)
        self.assertEqual({p.relative_to(first).as_posix(): p.read_bytes() for p in first.rglob("*") if p.is_file()},
                         {p.relative_to(second).as_posix(): p.read_bytes() for p in second.rglob("*") if p.is_file()})
        for record in self.records()["packages"]:
            self.assertEqual((first / record["path"]).read_bytes(), (self.releases / record["path"]).read_bytes())
        with self.assertRaises(prepare.PreparationError):
            prepare.prepare(self.base, first)
        self.assertEqual(before, self.snapshot())

    def test_new_current_version_is_added_while_old_record_and_bytes_stay(self):
        old_source = self.parent / "old-source"
        shutil.copytree(package.ADDON, old_source)
        manifest = old_source / "addon.xml"
        manifest.write_text(manifest.read_text().replace('version="' + package.validate() + '"', 'version="0.0.1"', 1))
        old_zip = package.build(old_source, self.releases / "archives")
        value = self.records()
        value["packages"] = [r for r in value["packages"] if r["id"] != "plugin.video.homefx"]
        old = dict(id="plugin.video.homefx", version="0.0.1", path="archives/" + old_zip.name,
                   sha256=hashlib.sha256(old_zip.read_bytes()).hexdigest())
        value["packages"].append(old)
        self.inventory.write_text(json.dumps(value))
        self.commit()
        before = self.snapshot()
        output = prepare.prepare(self.base, self.parent / "proposal")
        proposed = release_history._read(output / "inventory.json")
        self.assertEqual(len(proposed), 3)
        self.assertEqual(proposed[("plugin.video.homefx", "0.0.1")], old)
        self.assertIn(("plugin.video.homefx", package.validate()), proposed)
        self.assertEqual((output / old["path"]).read_bytes(), old_zip.read_bytes())
        self.assertEqual(before, self.snapshot())

    def test_same_version_changed_archive_is_never_replaced(self):
        value = self.records()
        row = next(r for r in value["packages"] if r["id"] == "plugin.video.homefx")
        archive = self.releases / row["path"]
        with ZipFile(archive) as source:
            members = [(info, source.read(info.filename)) for info in source.infolist()]
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as target:
            for info, data in members:
                if info.filename.endswith("/default.py"):
                    data += b"\n# Different reviewed fixture.\n"
                target.writestr(info, data)
        row["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.inventory.write_text(json.dumps(value))
        self.commit()
        before = self.snapshot()
        self.assert_rejected()
        self.assertEqual(before, self.snapshot())

    def test_base_history_removal_or_rewrite_fails_before_proposal(self):
        original = self.records()
        for mutation in ("remove", "hash", "path"):
            value = json.loads(json.dumps(original))
            if mutation == "remove":
                value["packages"].pop()
            elif mutation == "hash":
                value["packages"][0]["sha256"] = "0" * 64
            else:
                value["packages"][0]["path"] = "different/" + Path(value["packages"][0]["path"]).name
            self.inventory.write_text(json.dumps(value))
            self.assert_rejected(mutation)
        self.inventory.write_text(json.dumps(original))
        self.assert_rejected(base="HEAD^")

    def test_corrupt_paths_symlinks_and_bounds_fail_without_outside_writes(self):
        original = self.records()
        row = original["packages"][0]
        archive = self.releases / row["path"]
        saved = archive.read_bytes()
        archive.write_bytes(b"corrupt")
        self.assert_rejected("corrupt")
        archive.write_bytes(saved)
        value = json.loads(json.dumps(original))
        value["packages"][0]["path"] = "../outside.zip"
        self.inventory.write_text(json.dumps(value))
        self.assert_rejected("traversal")
        self.inventory.write_text(json.dumps(original))
        archive.unlink()
        outside = self.parent / "outside.zip"
        outside.write_bytes(saved)
        archive.symlink_to(outside)
        self.assert_rejected("link")
        self.assertEqual(outside.read_bytes(), saved)
        archive.unlink()
        archive.write_bytes(saved)
        with patch.object(repository, "MAX_RETAINED_BYTES", 1):
            self.assert_rejected("bound")

    def test_output_cannot_target_sources_or_escape_dist_via_dotdot(self):
        before = self.snapshot()
        (self.root / "dist").mkdir()
        for output in (self.releases / "proposal", self.root / "docs-proposal",
                       self.root / "dist" / ".." / "releases" / "proposal"):
            with self.assertRaises(prepare.PreparationError):
                prepare.prepare(self.base, output)
            self.assertFalse(output.exists())
        alias = self.parent / "alias"
        alias.symlink_to(self.parent, target_is_directory=True)
        with self.assertRaises(prepare.PreparationError):
            prepare.prepare(self.base, alias / "proposal")
        self.assertEqual(before, self.snapshot())
        self.assertTrue(prepare.prepare(self.base, self.root / "dist" / "proposal").is_dir())

    def test_cli_requires_base_and_redacts_failure(self):
        error = io.StringIO()
        with patch.object(sys, "argv", ["prepare_release.py", str(self.parent / "proposal"), "--base-ref", "missing"]), redirect_stderr(error):
            with self.assertRaises(SystemExit) as failure:
                prepare.main()
        self.assertEqual(failure.exception.code, 1)
        self.assertEqual(error.getvalue(), "Release preparation failed.\n")
