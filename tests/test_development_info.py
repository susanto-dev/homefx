"""Build identity and local-report boundaries use only fabricated configuration."""
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_development_test as builder

spec = importlib.util.spec_from_file_location('development_info',
    ROOT / 'addons/plugin.video.homefx.development/resources/lib/development_info.py')
info = importlib.util.module_from_spec(spec)
spec.loader.exec_module(info)
CONFIG = {'HOMEFX_TRAKT_ENVIRONMENT': 'Development', 'TRAKT_CLIENT_ID': 'synthetic-public',
          'TRAKT_REDIRECT_URI': 'urn:homefx:synthetic'}


class DevelopmentInfoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / 'build.json'
        self.value = {'schema': 1, 'source_version': '0.17.14', 'runtime_sha256': 'a' * 64}
        self.path.write_text(json.dumps(self.value))

    def report(self, **kwargs):
        callbacks = {'kodi_version': lambda: '21.2 (build suffix)',
                     'skin_id': lambda: 'skin.arctic.zephyr.mod', 'skin_version': lambda: '3.0.3'}
        callbacks.update(kwargs)
        return info.report(self.path, **callbacks, python_version=(3, 11, 7))

    def test_safe_fixed_report_exposes_versions_and_public_build_only(self):
        with patch.object(socket, 'create_connection', side_effect=AssertionError('No network')):
            report = self.report()
        for text in ('Source version: 0.17.14', 'Runtime fingerprint: ' + 'a' * 64,
                     'Kodi: 21.2', 'Python: 3.11.7', 'Active skin: Arctic Zephyr Reloaded',
                     'Skin version: 3.0.3', 'not the ZIP checksum', 'No network'):
            self.assertIn(text, report)
        self.assertNotIn(str(self.root), report)
        self.assertNotIn('build suffix', report)
        self.assertLess(len(report), 1500)

    def test_missing_invalid_or_linked_records_never_disclose_content_or_paths(self):
        cases = [dict(self.value, token='DO-NOT-REPORT'), dict(self.value, schema=True),
                 dict(self.value, source_version='DO-NOT-REPORT'),
                 dict(self.value, runtime_sha256='DO-NOT-REPORT'), [], None]
        for value in cases:
            self.path.write_text(json.dumps(value))
            report = self.report()
            self.assertIn('Source version: unavailable', report)
            self.assertNotIn('DO-NOT-REPORT', report)
        for raw in ('{"schema":1,"schema":1}', 'x' * (info.MAX_FILE + 1), '\udcff'):
            self.path.write_bytes(raw.encode('utf-8', errors='surrogatepass'))
            self.assertIn('Runtime fingerprint: unavailable', self.report())
        self.path.unlink()
        self.assertIn('Source version: unavailable', self.report())
        target = self.root / 'other.json'
        target.write_text(json.dumps(self.value))
        self.path.symlink_to(target)
        self.assertIn('Source version: unavailable', self.report())
        self.path.unlink()
        self.path.mkdir()
        self.assertIn('Source version: unavailable', self.report())

    def test_callback_failures_and_foreign_skin_are_fixed_not_raw_diagnostics(self):
        def fail():
            raise RuntimeError('DO-NOT-REPORT')
        report = self.report(kodi_version=fail, skin_id=fail, skin_version=fail)
        self.assertIn('Kodi: unavailable', report)
        self.assertIn('Active skin: unavailable', report)
        self.assertNotIn('DO-NOT-REPORT', report)
        report = self.report(kodi_version=lambda: '[B]DO-NOT-REPORT',
                             skin_id=lambda: '/private/DO-NOT-REPORT', skin_version=fail)
        self.assertIn('Active skin: other skin', report)
        self.assertIn('Skin version: unavailable', report)
        self.assertNotIn('DO-NOT-REPORT', report)
        self.assertIn('Python: unavailable', info.report(self.path, fail, fail, fail,
                                                        python_version=(True, 11, 7)))

    def test_build_identity_ignores_app_configuration_but_tracks_runtime_bytes(self):
        first = builder._sources(ROOT, builder._configuration(CONFIG), video=True)
        other_config = dict(CONFIG, TRAKT_CLIENT_ID='different-public',
                            TRAKT_REDIRECT_URI='urn:homefx:alternate')
        second = builder._sources(ROOT, builder._configuration(other_config), video=True)
        self.assertEqual(first['resources/build.json'], second['resources/build.json'])
        self.assertNotEqual(first['resources/development.json'], second['resources/development.json'])
        record = json.loads(first['resources/build.json'])
        self.assertEqual(set(record), {'schema', 'source_version', 'runtime_sha256'})
        original = builder._read
        def changed(path, bound=builder.MAX_FILE):
            data = original(path, bound)
            return data + b'\n# Synthetic source change.\n' if path.name == 'development_info.py' else data
        with patch.object(builder, '_read', changed):
            changed_files = builder._sources(ROOT, builder._configuration(CONFIG), video=True)
        self.assertNotEqual(record['runtime_sha256'],
                            json.loads(changed_files['resources/build.json'])['runtime_sha256'])
        program = builder._sources(ROOT, builder._configuration(CONFIG))
        self.assertNotIn('resources/build.json', program)
        self.assertNotIn('resources/lib/development_info.py', program)

    def test_real_video_archive_report_survives_reopen_and_is_reproducible(self):
        first = builder.build(self.root / 'first', CONFIG, video=True)
        second = builder.build(self.root / 'second', CONFIG, video=True)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with ZipFile(first) as packed:
            record = packed.read(builder.VIDEO_ID + '/resources/build.json')
            self.assertIn(builder.VIDEO_ID + '/resources/lib/development_info.py', packed.namelist())
        self.path.write_bytes(record)
        self.assertEqual(self.report(), self.report())
        self.assertNotIn('synthetic-public', self.report())
        self.assertNotIn('unavailable', self.report())


if __name__ == '__main__':
    unittest.main()
