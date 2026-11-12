import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

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
