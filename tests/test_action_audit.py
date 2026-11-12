"""Pin guard failure fixtures and mocked upstream discovery."""
import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
    import requests
except ImportError:
    yaml = None


@unittest.skipIf(yaml is None, 'Optional Action audit tests require PyYAML; security job installs it')
class AuditTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('action_audit', Path(__file__).resolve().parents[1] / 'tools/action_audit.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / '.github/workflows').mkdir(parents=True)
        self.file = self.root / '.github/workflows/test.yml'

    def write(self, action):
        self.file.write_text('jobs:\n  test:\n    steps:\n      - uses: ' + action + '\n')

    def test_floating_short_and_dynamic_refs_rejected(self):
        for ref in ['owner/repo@main', 'owner/repo@v1', 'owner/repo@abcdef1', 'owner/repo@${{ inputs.ref }}']:
            with self.subTest(ref=ref):
                self.write(ref)
                self.assertTrue(self.module.audit(self.root)['errors'])

    def test_pinned_reusable_workflow_accepted(self):
        self.write('owner/repo/.github/workflows/build.yml@' + 'a' * 40)
        self.assertFalse(self.module.audit(self.root)['errors'])

    def test_nested_floating_pin_and_new_release_reported(self):
        self.write('owner/repo@' + 'a' * 40)
        def get(path):
            if path.endswith('/releases/latest'):
                return {'tag_name': 'v2.0.0'}
            if '/git/ref/tags/' in path:
                return {'object': {'type': 'tag', 'sha': 'c' * 40}}
            if '/git/tags/' in path:
                return {'object': {'type': 'commit', 'sha': 'b' * 40}}
            if '/compare/' in path:
                return {'status': 'ahead'}
            return {'content': base64.b64encode(b'runs:\n  using: composite\n  steps:\n    - uses: another/action@v1\n').decode()}
        report = self.module.audit(self.root, True, get)
        self.assertIn('update available', report['releases'][0]['status'])
        self.assertEqual(report['releases'][0]['latest_sha'], 'b' * 40)
        self.assertTrue(any('another/action@v1' in x for x in report['errors']))

    def test_network_error_is_not_clean_scan(self):
        self.write('owner/repo@' + 'a' * 40)
        def get(path):
            raise OSError('offline')
        self.assertTrue(self.module.audit(self.root, True, get)['errors'])

    def test_unused_local_composite_is_checked(self):
        self.write('owner/repo@' + 'a' * 40)
        local = self.root / '.github/actions/local'
        local.mkdir(parents=True)
        (local / 'action.yml').write_text('runs:\n  steps:\n    - uses: other/action@v1\n')
        self.assertTrue(self.module.audit(self.root)['errors'])
