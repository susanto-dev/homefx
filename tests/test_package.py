import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from defusedxml import ElementTree as ET
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
            profile = src / "profile" / "trakt"
            profile.mkdir(parents=True)
            (profile / "tokens.sqlite3").write_bytes(b"synthetic private state")
            (profile / "tokens.sqlite3-journal").write_bytes(b"synthetic journal")
            first = p.build(src, root / "one")
            second = p.build(src, root / "two")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()),
                                 {"plugin.video.homefx/" + x for x in p.FILES})
                self.assertIsNone(archive.testzip())

    def test_validator_rejects_actual_manifest_defects(self):
        mutations = [('version="' + p.validate() + '"', 'version="invalid"'),
                     ('version="3.0.1"', 'version="9.0.0"'),
                     ('library="default.py"', 'library="missing.py"'),
                     ('resources/art/icon.png', 'private/icon.png')]
        for old, new in mutations:
            with self.subTest(mutation=new), tempfile.TemporaryDirectory() as temp:
                src = Path(temp) / "source"
                shutil.copytree(p.ADDON, src)
                manifest = src / "addon.xml"
                original = manifest.read_text()
                self.assertIn(old, original, "Mutation must alter the real manifest")
                manifest.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    p.build(src, Path(temp) / "out")

    def test_current_manifest_has_independently_expected_contract(self):
        manifest = ET.fromstring((ROOT / "addons/plugin.video.homefx/addon.xml").read_bytes())
        self.assertEqual(manifest.tag, "addon")
        self.assertEqual(manifest.get("id"), "plugin.video.homefx")
        self.assertEqual(len(manifest.findall("requires")), 1)
        self.assertEqual([(node.tag, node.attrib) for node in manifest.find("requires")],
                         [("import", {"addon": "xbmc.python", "version": "3.0.1"})])
        self.assertEqual([node.get("point") for node in manifest.findall("extension")],
                         ["xbmc.python.pluginsource", "xbmc.addon.metadata"])
        plugin = manifest.find("./extension[@point='xbmc.python.pluginsource']")
        self.assertEqual(plugin.get("library"), "default.py")
        self.assertEqual([(node.tag, node.text) for node in plugin], [("provides", "video")])
        metadata = manifest.find("./extension[@point='xbmc.addon.metadata']")
        self.assertEqual([node.text for node in metadata.findall("license")], ["MIT"])
        self.assertEqual([node.text for node in metadata.findall("platform")], ["all"])
        self.assertEqual(len(metadata.findall("assets")), 1)
        self.assertEqual([(node.tag, node.text) for node in metadata.find("assets")],
                         [("icon", "resources/art/icon.png")])
        self.assertEqual(p.validate(), manifest.get("version"))

    def test_source_contract_rejects_ambiguous_or_inconsistent_declarations_before_packaging(self):
        original = (p.ADDON / "addon.xml").read_text()
        dependency = '<import addon="xbmc.python" version="3.0.1"/>'
        requires = '<requires>' + dependency + '</requires>'
        plugin = ('<extension point="xbmc.python.pluginsource" library="default.py">'
                  '<provides>video</provides></extension>')
        metadata = original[original.index('  <extension point="xbmc.addon.metadata">'):
                            original.index('</addon>')]
        assets = '<assets><icon>resources/art/icon.png</icon></assets>'
        mutations = [
            ("missing name", 'name="HomeFX Preview"', ""),
            ("empty name", 'name="HomeFX Preview"', 'name=""'),
            ("blank name", 'name="HomeFX Preview"', 'name="  "'),
            ("missing provider", 'provider-name="susanto-dev"', ""),
            ("empty provider", 'provider-name="susanto-dev"', 'provider-name=""'),
            ("blank provider", 'provider-name="susanto-dev"', 'provider-name="  "'),
            ("missing requires", requires, ""),
            ("duplicate requires", requires, requires * 2),
            ("empty requires", dependency, ""),
            ("duplicate import", dependency, dependency * 2),
            ("additional dependency", dependency, dependency + '<import addon="script.module.extra" version="1.0.0"/>'),
            ("unknown dependency element", dependency, dependency + '<unexpected/>'),
            ("wrong dependency identity", 'addon="xbmc.python"', 'addon="script.module.extra"'),
            ("optional Python dependency", dependency, dependency.replace('/>', ' optional="true"/>')),
            ("nested dependency", dependency, dependency.replace('/>', '><unexpected/></import>')),
            ("missing plugin", plugin, ""),
            ("duplicate plugin", plugin, plugin * 2),
            ("missing metadata", metadata, ""),
            ("duplicate metadata", metadata, metadata * 2),
            ("unknown extension", plugin, plugin + '<extension point="xbmc.service" library="default.py"/>'),
            ("missing provides", '<provides>video</provides>', ""),
            ("duplicate provides", '<provides>video</provides>', '<provides>video</provides><provides>audio</provides>'),
            ("wrong provides", '<provides>video</provides>', '<provides>audio</provides>'),
            ("nested provides", '<provides>video</provides>', '<provides>video<unexpected/></provides>'),
            ("missing license", '<license>MIT</license>', ""),
            ("duplicate license", '<license>MIT</license>', '<license>MIT</license><license>GPL-3.0-only</license>'),
            ("different license", '<license>MIT</license>', '<license>GPL-3.0-only</license>'),
            ("missing platform", '<platform>all</platform>', ""),
            ("duplicate platform", '<platform>all</platform>', '<platform>all</platform><platform>linux</platform>'),
            ("different platform", '<platform>all</platform>', '<platform>linux</platform>'),
            ("missing assets", assets, ""),
            ("duplicate assets", assets, assets * 2),
            ("missing icon", assets, '<assets><poster>resources/art/poster.png</poster></assets>'),
            ("duplicate icon", '<icon>resources/art/icon.png</icon>', '<icon>resources/art/icon.png</icon>' * 2),
            ("unknown asset", assets, assets.replace('</assets>', '<unknown>resources/art/poster.png</unknown></assets>')),
            ("non-art asset", 'resources/art/icon.png', 'default.py'),
            ("mismatched artwork", 'resources/art/icon.png', 'resources/art/poster.png'),
            ("nested artwork", '<icon>resources/art/icon.png</icon>', '<icon>resources/art/icon.png<unexpected/></icon>'),
        ]
        for label, old, new in mutations:
            with self.subTest(contract=label), tempfile.TemporaryDirectory() as temp:
                self.assertIn(old, original, "Mutation must alter the real manifest")
                src, output = Path(temp) / "source", Path(temp) / "out"
                shutil.copytree(p.ADDON, src)
                (src / "addon.xml").write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    p.build(src, output)
                self.assertFalse(output.exists(), "Reject the contract before creating package output")

    def test_equivalent_dependency_and_reviewed_optional_artwork_remain_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source"
            shutil.copytree(p.ADDON, src)
            manifest = src / "addon.xml"
            original = manifest.read_text()
            original = original.replace('name="HomeFX Preview"', 'name="Fixture Display"')
            original = original.replace('provider-name="susanto-dev"', 'provider-name="Fixture Provider"')
            changed = original.replace('addon="xbmc.python" version="3.0.1"',
                                       'addon="xbmc.python" version="3.0.1" optional="false"')
            changed = changed.replace('</assets>', '<poster>resources/art/poster.png</poster>'
                                      '<fanart>resources/art/fanart.png</fanart></assets>')
            manifest.write_text(changed)
            archive = p.build(src, Path(temp) / "out")
            with ZipFile(archive) as packed:
                self.assertEqual(packed.read("plugin.video.homefx/addon.xml"), manifest.read_bytes())

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
