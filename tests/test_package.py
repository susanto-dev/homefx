import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from defusedxml.common import DefusedXmlException

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("packager", ROOT / "tools/package.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PackageTests(unittest.TestCase):
    def test_reproducibility_and_private_file_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "source"
            shutil.copytree(p.ADDON, src)
            (src / "demo.json").write_text('{"private": "fixture"}')
            (src / ".env").write_text("EXAMPLE=synthetic")
            first = p.build(src, root / "one")
            second = p.build(src, root / "two")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"plugin.video.homefx/" + x for x in p.FILES})
                self.assertIsNone(archive.testzip())

    def test_validator_rejects_actual_manifest_defects(self):
        mutations = [('version="0.1.0"', 'version="invalid"'),
                     ('version="3.0.1"', 'version="9.0.0"'),
                     ('library="default.py"', 'library="missing.py"'),
                     ('resources/art/icon.png', 'private/icon.png')]
        for old, new in mutations:
            with self.subTest(mutation=new), tempfile.TemporaryDirectory() as temp:
                src = Path(temp) / "source"
                shutil.copytree(p.ADDON, src)
                manifest = src / "addon.xml"
                manifest.write_text(manifest.read_text().replace(old, new))
                with self.assertRaises(ValueError):
                    p.build(src, Path(temp) / "out")

    def test_missing_runtime_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source"
            shutil.copytree(p.ADDON, src)
            (src / "default.py").unlink()
            with self.assertRaises(ValueError):
                p.validate(src)

    def test_rejects_dtd_and_entities_in_source_manifest(self):
        payloads = [
            b'<!DOCTYPE addon><addon/>',
            b'<!DOCTYPE addon [<!ENTITY x "expanded">]><addon>&x;</addon>',
            b'<!DOCTYPE addon [<!ENTITY x SYSTEM "file:///does-not-exist">]><addon>&x;</addon>',
        ]
        for payload in payloads:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temp:
                src = Path(temp) / "source"
                shutil.copytree(p.ADDON, src)
                (src / "addon.xml").write_bytes(payload)
                with self.assertRaises(DefusedXmlException):
                    p.build(src, Path(temp) / "out")
                self.assertFalse((Path(temp) / "out").exists())

    def test_rejects_dtd_in_packaged_manifest_readback(self):
        class AlteredReadback(ZipFile):
            def read(self, name, *args, **kwargs):
                if name == "plugin.video.homefx/addon.xml":
                    return b'<!DOCTYPE addon><addon/>'
                return super().read(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temp, patch.object(p, "ZipFile", AlteredReadback):
            with self.assertRaises(DefusedXmlException):
                p.build(output=Path(temp))
            self.assertFalse(list(Path(temp).glob("*.sha256")))

    def test_oversized_source_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp)
            (src / "addon.xml").write_bytes(b" " * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ValueError, "1 MiB"):
                p.validate(src)

    def test_build_dependencies_are_in_audited_tool_inventory(self):
        declared = {line for line in (ROOT / 'tools/build-requirements.txt').read_text().splitlines()
                    if line and not line.startswith('#')}
        audited = set((ROOT / 'tools/security-requirements.txt').read_text().splitlines())
        self.assertTrue(declared)
        self.assertTrue(declared <= audited)
