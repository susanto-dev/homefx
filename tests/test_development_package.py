"""Development artifact boundaries use fabricated public configuration only."""
from contextlib import redirect_stderr, redirect_stdout
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
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_development_test as builder

CONFIG = {"HOMEFX_TRAKT_ENVIRONMENT": "Development", "TRAKT_CLIENT_ID": "synthetic-public",
          "TRAKT_REDIRECT_URI": "urn:homefx:synthetic"}
MANIFEST = '''<addon id="script.homefx.development" name="HomeFX Development Test" version="0.1.0" provider-name="susanto-dev">
<requires><import addon="xbmc.python" version="3.0.1"/></requires>
<extension point="xbmc.python.script" library="default.py"><provides>executable</provides></extension>
<extension point="xbmc.addon.metadata"><license>MIT</license><platform>all</platform><assets><icon>resources/art/icon.png</icon></assets></extension></addon>'''


class DevelopmentPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "project"
        self.runtime = self.root / "addons/plugin.video.homefx"
        self.script = self.root / "addons/script.homefx.development"
        self.script.mkdir(parents=True)
        self.runtime.mkdir(parents=True)
        shutil.copyfile(ROOT / "LICENSE", self.root / "LICENSE")
        shutil.copyfile(ROOT / "LICENSE", self.runtime / "LICENSE")
        for name in builder.RUNTIME_FILES:
            target = self.runtime / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "addons/plugin.video.homefx" / name, target)
        (self.script / "addon.xml").write_text(MANIFEST)
        (self.script / "default.py").write_text('"""Synthetic entry point."""\n')
        (self.script / "resources/lib").mkdir(parents=True)
        (self.script / "resources/lib/development_test.py").write_text('"""Synthetic runner."""\n')
        self.patcher = patch.object(builder, "ROOT", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def build(self, name="output", environment=None):
        return builder.build(self.parent / name, CONFIG if environment is None else environment)

    def test_reproducible_configured_archive_is_content_addressed_and_idempotent(self):
        (self.script / "private-token.json").write_text("DO-NOT-PACK")
        (self.script / "resources/development.json").write_text("DO-NOT-PACK")
        (self.runtime / "resources/lib/private-history.json").write_text("DO-NOT-PACK")
        environment = dict(CONFIG, CLIENT_SECRET="DO-NOT-PACK", ACCESS_TOKEN="DO-NOT-PACK")
        with patch("socket.create_connection", side_effect=AssertionError("Network forbidden")):
            first = self.build(environment=environment)
            second = self.build("second", environment)
            self.assertEqual(self.build(environment=environment), first)
        data = first.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(first.name, "script.homefx.development-0.1.0-" + digest + ".zip")
        self.assertEqual(data, second.read_bytes())
        self.assertEqual(first.with_suffix(".zip.sha256").read_text(), digest + "  " + first.name + "\n")
        self.assertEqual(len(list(first.parent.iterdir())), 2)
        with ZipFile(first) as archive:
            prefix = "script.homefx.development/"
            expected = set(builder.SCRIPT_FILES) | set(builder.RUNTIME_FILES) | {"LICENSE", "resources/development.json"}
            self.assertEqual(set(archive.namelist()), {prefix + name for name in expected})
            self.assertEqual(json.loads(archive.read(prefix + "resources/development.json")), {
                "schema": 1, "environment": "Development", "client_id": "synthetic-public",
                "redirect_uri": "urn:homefx:synthetic"})
            self.assertEqual(archive.read(prefix + "LICENSE"), (ROOT / "LICENSE").read_bytes())
            self.assertEqual(archive.read(prefix + "resources/lib/trakt_tokens.py"),
                             (self.runtime / "resources/lib/trakt_tokens.py").read_bytes())
            self.assertNotEqual(archive.read(prefix + "default.py"),
                                (ROOT / "addons/plugin.video.homefx/default.py").read_bytes())
            self.assertNotIn(b"DO-NOT-PACK", b"".join(archive.read(name) for name in archive.namelist()))
            self.assertTrue(all(item.date_time == (2026, 1, 1, 0, 0, 0) for item in archive.infolist()))

    def test_configuration_failure_has_no_output_or_disclosure(self):
        invalid = ({}, dict(CONFIG, HOMEFX_TRAKT_ENVIRONMENT="Production"),
                   dict(CONFIG, TRAKT_CLIENT_ID=""), dict(CONFIG, TRAKT_REDIRECT_URI="/private/secret"))
        for index, environment in enumerate(invalid):
            output = self.parent / ("invalid" + str(index))
            with self.subTest(index=index), self.assertRaisesRegex(builder.BuildError, '^development test build failed$'):
                builder.build(output, environment)
            self.assertFalse(output.exists())
        stream = io.StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            code = builder.main([str(self.parent / "cli")], dict(CONFIG, TRAKT_REDIRECT_URI="/private/secret"))
        self.assertEqual(code, 1)
        self.assertEqual(stream.getvalue(), "Development test build failed.\n")

    def test_changed_configuration_and_partial_or_extra_output_are_preserved(self):
        first = self.build()
        before = {path.name: path.read_bytes() for path in first.parent.iterdir()}
        with self.assertRaises(builder.BuildError):
            self.build(environment=dict(CONFIG, TRAKT_CLIENT_ID="different-public"))
        self.assertEqual(before, {path.name: path.read_bytes() for path in first.parent.iterdir()})
        alternate = self.build("alternate", dict(CONFIG, TRAKT_CLIENT_ID="different-public"))
        self.assertNotEqual(first.name, alternate.name)
        first.with_suffix(".zip.sha256").unlink()
        with self.assertRaises(builder.BuildError):
            self.build()
        self.assertEqual(first.read_bytes(), before[first.name])
        (first.parent / "unexpected.txt").write_text("retain")
        with self.assertRaises(builder.BuildError):
            self.build()
        self.assertEqual((first.parent / "unexpected.txt").read_text(), "retain")

    def test_source_manifest_syntax_licence_and_size_fail_closed(self):
        manifest = self.script / "addon.xml"
        for data in (MANIFEST.replace('script.homefx.development', 'plugin.video.homefx'),
                     MANIFEST.replace('0.1.0', '1.0.0'),
                     MANIFEST.replace('xbmc.python.script', 'xbmc.python.pluginsource'),
                     MANIFEST.replace('3.0.1', '2.0.0'),
                     '<!DOCTYPE x [<!ENTITY x "bad">]>' + MANIFEST):
            manifest.write_text(data)
            with self.assertRaises(builder.BuildError):
                self.build()
            self.assertFalse((self.parent / "output").exists())
        manifest.write_text(MANIFEST)
        runner = self.script / "default.py"
        runner.write_text('def invalid(:\n')
        with self.assertRaises(builder.BuildError): self.build()
        runner.write_bytes(b'x' * (builder.MAX_FILE + 1))
        with self.assertRaises(builder.BuildError): self.build()
        runner.write_text('pass\n')
        (self.runtime / "LICENSE").write_text('different')
        with self.assertRaises(builder.BuildError): self.build()
        self.assertFalse((self.parent / "output").exists())

    def test_symlinks_special_sources_and_tracked_output_are_rejected(self):
        source = self.script / "default.py"
        source.unlink()
        source.symlink_to(ROOT / "addons/plugin.video.homefx/default.py")
        with self.assertRaises(builder.BuildError): self.build()
        source.unlink()
        source.mkdir()
        with self.assertRaises(builder.BuildError): self.build()
        source.rmdir()
        source.write_text('pass\n')
        link = self.parent / "alias"
        link.symlink_to(self.parent, target_is_directory=True)
        with self.assertRaises(builder.BuildError): builder.build(link / "output", CONFIG)
        for output in (self.root, self.script / "output", self.root / "releases/output"):
            with self.assertRaises(builder.BuildError): builder.build(output, CONFIG)
        existing = self.build()
        checksum = existing.with_suffix('.zip.sha256')
        checksum.unlink()
        checksum.symlink_to(existing)
        with self.assertRaises(builder.BuildError): self.build()

    def test_aggregate_and_archive_bounds_reject_before_output(self):
        for constant in ("MAX_TOTAL", "MAX_ZIP"):
            with self.subTest(constant=constant), patch.object(builder, constant, 1):
                with self.assertRaises(builder.BuildError):
                    self.build()
            self.assertFalse((self.parent / "output").exists())

    def test_actual_sources_build_without_mutating_release_inventory(self):
        before = (ROOT / "releases/inventory.json").read_bytes()
        with patch.object(builder, "ROOT", ROOT):
            archive = self.build("actual")
        self.assertEqual(before, (ROOT / "releases/inventory.json").read_bytes())
        with ZipFile(archive) as packed:
            prefix = builder.ADDON_ID + '/'
            self.assertEqual(packed.read(prefix + 'default.py'),
                             (ROOT / 'addons/script.homefx.development/default.py').read_bytes())
            self.assertEqual(packed.read(prefix + 'resources/lib/development_test.py'),
                             (ROOT / 'addons/script.homefx.development/resources/lib/development_test.py').read_bytes())

    def test_packaged_entry_cancel_imports_only_bundled_runtime_without_io(self):
        with patch.object(builder, "ROOT", ROOT):
            archive = self.build("smoke-artifact")
        extracted = self.parent / "unpacked"
        with ZipFile(archive) as packed:
            for member in packed.infolist():
                relative = Path(member.filename)
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                target = extracted / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(packed.read(member))
        addon = extracted / builder.ADDON_ID
        code = r'''import pathlib, runpy, socket, sys, types
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
events = []
def forbidden(*args, **kwargs):
    events.append("forbidden")
    raise AssertionError("Operation forbidden during cancellation")
class Addon:
    getAddonInfo = forbidden
class Dialog:
    def select(self, title, options):
        events.append("select")
        return -1
    yesno = forbidden
    textviewer = forbidden
class Monitor:
    abortRequested = forbidden
    waitForAbort = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden
sys.modules.update({
    "xbmc": types.SimpleNamespace(Monitor=Monitor),
    "xbmcaddon": types.SimpleNamespace(Addon=Addon),
    "xbmcgui": types.SimpleNamespace(Dialog=Dialog, DialogProgress=forbidden),
    "xbmcvfs": types.SimpleNamespace(translatePath=forbidden)})
sys.dont_write_bytecode = True
runpy.run_path(str(root / "default.py"), run_name="__main__")
assert events == ["select"], "Cancelled packaged entry performed an operation"
for name, module in tuple(sys.modules.items()):
    if name == "resources" or name.startswith("resources."):
        assert pathlib.Path(module.__file__).is_relative_to(root), "Unbundled runtime import"
assert "resources.lib.development_test" in sys.modules
print("Packaged cancellation passed.")
'''
        before = {path.relative_to(extracted).as_posix(): path.read_bytes()
                  for path in extracted.rglob('*') if path.is_file()}
        result = subprocess.run([sys.executable, "-I", "-c", code, str(addon)],
                                cwd=self.parent, capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Packaged cancellation passed.\n")
        self.assertEqual(before, {path.relative_to(extracted).as_posix(): path.read_bytes()
                                  for path in extracted.rglob('*') if path.is_file()})
