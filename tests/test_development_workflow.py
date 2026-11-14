"""Development configuration reaches only explicit main-only test ZIP builds."""
from pathlib import Path
import unittest

try:
    import yaml
except ImportError:
    yaml = None


class DevelopmentWorkflowTests(unittest.TestCase):
    def test_pr_checks_do_not_receive_real_configuration(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('validation.yml', 'security.yml'):
            public = (root / '.github/workflows' / name).read_text()
            self.assertNotIn('vars.TRAKT_', public)
            self.assertNotIn('build_development_test.py', public)

    @unittest.skipIf(yaml is None, 'Workflow structure checks require PyYAML; security job installs it')
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
