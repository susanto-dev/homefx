"""Development configuration reaches only explicit main-only test ZIP builds."""
from pathlib import Path
import unittest

try:
    import yaml
except ImportError:
    yaml = None


@unittest.skipIf(yaml is None, 'Workflow structure checks require PyYAML; security job installs it')
class DevelopmentWorkflowTests(unittest.TestCase):
    def test_real_configuration_is_explicit_development_artifact_only(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / '.github/workflows/development-device-test.yml').read_text()
        workflow = yaml.load(source, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        inputs = workflow['on']['workflow_dispatch']['inputs']
        self.assertEqual(set(inputs), {'confirm_readiness'})
        self.assertEqual(inputs['confirm_readiness']['type'], 'boolean')
        self.assertEqual(inputs['confirm_readiness']['default'], 'false')
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(set(workflow['jobs']), {'build'})
        job = workflow['jobs']['build']
        self.assertEqual(job['if'], "github.ref == 'refs/heads/main' && inputs.confirm_readiness == true")
        self.assertEqual(job['environment'], 'Development')
        self.assertNotIn('permissions', job)
        steps = job['steps']
        configured = [step for step in steps if 'TRAKT_CLIENT_ID' in step.get('env', {})]
        self.assertEqual(len(configured), 1)
        step = configured[0]
        self.assertEqual(step['run'], 'python tools/build_development_test.py dist/development-test')
        self.assertEqual(step['env'], {
            'HOMEFX_TRAKT_ENVIRONMENT': 'Development',
            'TRAKT_CLIENT_ID': '${{ vars.TRAKT_CLIENT_ID }}',
            'TRAKT_REDIRECT_URI': '${{ vars.TRAKT_REDIRECT_URI }}'})
        build_index = steps.index(step)
        self.assertTrue(any('tools/run_tests.py' in item.get('run', '') for item in steps[:build_index]))
        guards = [item for item in steps[:build_index] if 'EXPECTED_SHA' in item.get('env', {})]
        self.assertEqual(len(guards), 1)
        self.assertIn('test "$current_sha" = "$EXPECTED_SHA"', guards[0]['run'])
        upload = steps[-1]
        self.assertTrue(upload['uses'].startswith('actions/upload-artifact@'))
        self.assertEqual(upload['with']['path'], 'dist/development-test/')
        self.assertEqual(upload['with']['retention-days'], '3')
        self.assertIn('github.run_id', upload['with']['name'])
        self.assertEqual(steps[0]['with']['persist-credentials'], 'false')
        for forbidden in ('secrets.', 'Production', 'TRAKT_CLIENT_SECRET', 'TRAKT_APP_MODE',
                          'deploy-pages', 'build_site.py', 'prepare_release.py'):
            self.assertNotIn(forbidden, source)
        for name in ('validation.yml', 'security.yml'):
            public = (root / '.github/workflows' / name).read_text()
            self.assertNotIn('vars.TRAKT_', public)
            self.assertNotIn('build_development_test.py', public)

    def test_pages_public_config_is_main_only_and_limited_to_test_download(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / '.github/workflows/pages.yml').read_text()
        workflow = yaml.load(source, Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow['on']), {'push', 'workflow_dispatch'})
        self.assertEqual(workflow['on']['push']['branches'], ['main'])
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        build = workflow['jobs']['build']
        self.assertEqual(build['if'], "github.ref == 'refs/heads/main'")
        self.assertEqual(build['environment'], 'Development')
        self.assertNotIn('permissions', build)
        steps = build['steps']
        configured = [step for step in steps if 'TRAKT_CLIENT_ID' in step.get('env', {})]
        self.assertEqual([step['run'] for step in configured], [
            'python3 tools/build_site.py --development',
            'python3 tools/check_reproducibility.py --development'])
        for step in configured:
            self.assertEqual(step['env'], {
                'HOMEFX_TRAKT_ENVIRONMENT': 'Development',
                'TRAKT_CLIENT_ID': '${{ vars.TRAKT_CLIENT_ID }}',
                'TRAKT_REDIRECT_URI': '${{ vars.TRAKT_REDIRECT_URI }}'})
        self.assertTrue(any('tools/run_tests.py' in step.get('run', '')
                            for step in steps[:steps.index(configured[0])]))
        for name in ('deploy', 'verify-published'):
            job = workflow['jobs'][name]
            self.assertEqual(job['if'], "github.ref == 'refs/heads/main'")
            self.assertNotIn('TRAKT_', str(job))
        deploy = workflow['jobs']['deploy']
        self.assertEqual(deploy['needs'], 'build')
        self.assertTrue(any('"$current_sha" != "$EXPECTED_SHA"' in step.get('run', '')
                            for step in deploy['steps']))
        verify = workflow['jobs']['verify-published']
        self.assertEqual(verify['needs'], 'deploy')
        self.assertTrue(any('tools/check_published.py' in step.get('run', '')
                            for step in verify['steps']))
        for forbidden in ('secrets.', 'Production', 'TRAKT_CLIENT_SECRET', 'TRAKT_APP_MODE'):
            self.assertNotIn(forbidden, source)
