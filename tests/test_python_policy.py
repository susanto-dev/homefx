"""Target Kodi's Python grammar without reinterpreting published archive history."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import package
import repository
from tools import check_quality


PYTHON_311 = b'try:\n    raise ExceptionGroup("synthetic", [ValueError()])\nexcept* ValueError:\n    pass\n'
PYTHON_312 = b'type SyntheticAlias = int\n'


class PythonPolicyTests(unittest.TestCase):
    def test_current_source_accepts_python311_exception_groups(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            shutil.copytree(package.ADDON, source)
            (source / 'default.py').write_bytes(PYTHON_311)
            self.assertEqual(package.validate(source), package.validate())
            archive = package.build(source, Path(temporary) / 'out')
            self.assertTrue(archive.is_file())

    def test_current_source_rejects_python312_only_syntax(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            shutil.copytree(package.ADDON, source)
            (source / 'default.py').write_bytes(PYTHON_312)
            output = Path(temporary) / 'out'
            with self.assertRaises(SyntaxError):
                package.build(source, output)
            self.assertFalse(output.exists())

    def video_manifest(self, version):
        manifest = package.parse_manifest((package.ADDON / 'addon.xml').read_bytes())
        manifest.set('version', version)
        return manifest

    def test_existing_video_versions_keep_legacy_python38_syntax(self):
        for version in ('0.8.0', '0.16.1', '0.17.0', '0.17.1', '0.17.2'):
            with self.subTest(version=version):
                manifest = self.video_manifest(version)
                repository._retained_contract(manifest, {'default.py': b'pass\n'}, 'plugin.video.homefx')
                with self.assertRaisesRegex(ValueError, '^Invalid retained Python syntax$'):
                    repository._retained_contract(manifest, {'default.py': PYTHON_311}, 'plugin.video.homefx')

    def test_future_video_versions_accept_python311_but_not_python312(self):
        for version in ('0.17.3', '0.18.0', '1.0.0'):
            with self.subTest(version=version):
                manifest = self.video_manifest(version)
                repository._retained_contract(manifest, {'default.py': PYTHON_311}, 'plugin.video.homefx')
                with self.assertRaisesRegex(ValueError, '^Invalid retained Python syntax$'):
                    repository._retained_contract(manifest, {'default.py': PYTHON_312}, 'plugin.video.homefx')

    def test_repository_archive_contract_is_not_broadened_with_video_policy(self):
        manifest = package.parse_manifest((repository.REPOSITORY / 'addon.xml').read_bytes())
        repository._retained_contract(manifest, {'fixture.py': b'pass\n'}, 'repository.homefx')
        with self.assertRaisesRegex(ValueError, '^Invalid retained Python syntax$'):
            repository._retained_contract(manifest, {'fixture.py': PYTHON_311}, 'repository.homefx')

    def test_quality_gate_targets_python311(self):
        with patch.object(check_quality.importlib.metadata, 'version', return_value=check_quality.RUFF_VERSION), \
                patch.object(check_quality.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(check_quality.check(), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index('--target-version') + 1], 'py311')
        self.assertFalse(run.call_args.kwargs.get('shell', False))
