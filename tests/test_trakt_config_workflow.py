"""Protect the real-configuration boundary without real values or provider calls."""
from pathlib import Path
import unittest

try:
    import yaml
except ImportError:
    yaml = None


@unittest.skipIf(yaml is None, 'Workflow structure checks require PyYAML; security job installs it')
class TraktConfigurationWorkflowTests(unittest.TestCase):
    def test_real_configuration_is_main_only_and_not_a_publish_or_login_job(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / '.github/workflows/trakt-configuration.yml').read_text()
        workflow = yaml.load(source, Loader=yaml.BaseLoader)
        events = workflow['on']
        self.assertEqual(set(events), {'push', 'workflow_dispatch'})
        self.assertEqual(events['push']['branches'], ['main'])
        choice = events['workflow_dispatch']['inputs']['environment']
        self.assertEqual(choice['type'], 'choice')
        self.assertEqual(choice['options'], ['Development', 'Production'])
        self.assertEqual(choice['default'], 'Development')
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        self.assertEqual(set(workflow['jobs']), {'configuration'})
        job = workflow['jobs']['configuration']
        self.assertEqual(job['if'], "github.ref == 'refs/heads/main'")
        self.assertNotIn('permissions', job)
        steps = job['steps']
        run_steps = [step for step in steps if 'run' in step]
        self.assertEqual(len(run_steps), 1)
        step = run_steps[0]
        self.assertEqual(step['run'], 'python tools/check_trakt_config.py')
        self.assertEqual(job['environment']['name'],
                         "${{ github.event_name == 'workflow_dispatch' && inputs.environment || 'Development' }}")
        self.assertEqual(step['env']['HOMEFX_TRAKT_ENVIRONMENT'], job['environment']['name'])
        self.assertEqual(step['env']['TRAKT_CLIENT_ID'], '${{ vars.TRAKT_CLIENT_ID }}')
        self.assertEqual(step['env']['TRAKT_REDIRECT_URI'], '${{ vars.TRAKT_REDIRECT_URI }}')
        self.assertEqual(set(step['env']), {'HOMEFX_TRAKT_ENVIRONMENT', 'TRAKT_CLIENT_ID', 'TRAKT_REDIRECT_URI'})
        self.assertNotIn('secrets.', source)
        self.assertNotIn('TRAKT_APP_MODE', source)
        actions = [step for step in steps if 'uses' in step]
        self.assertEqual(len(actions), 2)
        self.assertTrue(actions[0]['uses'].startswith('actions/checkout@'))
        self.assertEqual(actions[0]['with']['persist-credentials'], 'false')
        self.assertTrue(actions[1]['uses'].startswith('actions/setup-python@'))
        # Real variables must not affect immutable packages or ordinary PR tests.
        for name in ('pages.yml', 'validation.yml', 'security.yml'):
            content = (root / '.github/workflows' / name).read_text()
            self.assertNotIn('vars.TRAKT_', content)
            self.assertNotIn('check_trakt_config.py', content)
