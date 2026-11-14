"""Required checks stay visible and publication integrity does not depend on scope."""
from pathlib import Path
import unittest

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(yaml is None, 'Workflow structure checks require PyYAML; security job installs it')
class ScopeWorkflowTests(unittest.TestCase):
    def workflow(self, name):
        return yaml.load((ROOT / '.github/workflows' / name).read_text(), Loader=yaml.BaseLoader)

    def steps(self, job):
        return {step['name']: step for step in job['steps'] if 'name' in step}

    def test_validation_required_matrix_names_and_documentation_route(self):
        workflow = self.workflow('validation.yml')
        self.assertNotIn('paths', workflow['on']['pull_request'])
        self.assertNotIn('paths-ignore', workflow['on']['pull_request'])
        job = workflow['jobs']['test']
        self.assertNotIn('if', job)
        self.assertEqual(job['name'], 'Python ${{ matrix.python }} tests and package')
        self.assertEqual({item['python'] for item in job['strategy']['matrix']['include']}, {'3.11', '3.12'})
        self.assertEqual(job['steps'][0]['with']['fetch-depth'], '0')
        steps = self.steps(job)
        self.assertEqual(steps['Select checks from changed files']['run'], 'python tools/ci_scope.py')
        self.assertEqual(steps['Test synthetic behavior']['if'], "steps.scope.outputs.mode != 'docs'")
        docs = steps['Check documentation links and rendering']
        self.assertEqual(docs['if'], "steps.scope.outputs.mode == 'docs' && matrix.python == '3.12'")
        self.assertIn('--documentation --summary', docs['run'])
        for name in ('Protect published release history', 'Validate package and preview site',
                     'Verify embedded preview repository', 'Build inactive repository candidate',
                     'Verify candidate before upload', 'Check reproducible release output'):
            self.assertEqual(steps[name]['if'], "steps.scope.outputs.mode != 'docs'")

    def test_security_retains_weekly_manual_scans_and_fail_closed_gate(self):
        workflow = self.workflow('security.yml')
        self.assertIn('schedule', workflow['on'])
        self.assertIn('workflow_dispatch', workflow['on'])
        job = workflow['jobs']['scan']
        self.assertNotIn('if', job)
        self.assertEqual(job['name'], 'Python code and dependencies')
        self.assertEqual(job['steps'][0]['with']['fetch-depth'], '0')
        steps = self.steps(job)
        for name in ('Scan Python code', 'Audit Python runtime inventory',
                     'Audit development tools and transitive dependencies'):
            self.assertEqual(steps[name]['if'], "steps.scope.outputs.mode != 'docs'")
        gate = steps['Require successful scans']
        self.assertEqual(gate['if'], "always() && steps.scope.outputs.mode != 'docs'")
        for outcome in ('CODE_OUTCOME', 'RUNTIME_OUTCOME', 'TOOLING_OUTCOME'):
            self.assertIn('test "$' + outcome + '" = success', gate['run'])
        actions = self.steps(workflow['jobs']['actions'])
        self.assertNotIn('if', actions['Check local pins'])
        self.assertIn('test_ci_scope*.py', actions['Test changed-file selection and workflow gates']['run'])
        self.assertEqual(actions['Inspect nested pins and available releases']['if'],
                         "github.event_name != 'pull_request'")

    def test_pages_artifact_checks_and_deployment_are_never_scope_skipped(self):
        workflow = self.workflow('pages.yml')
        jobs = workflow['jobs']
        steps = self.steps(jobs['build'])
        self.assertEqual(jobs['build']['permissions'], {'contents': 'read', 'actions': 'read'})
        baseline = steps['Select checks since the last verified publication']
        self.assertIn('pages.yml/runs?status=success&branch=main&per_page=1', baseline['run'])
        self.assertIn('PUBLISHED_BASE="$baseline" python tools/ci_scope.py --publication', baseline['run'])
        self.assertIn('|| baseline=""', baseline['run'])
        self.assertEqual(steps['Test preview']['if'], "steps.scope.outputs.mode != 'docs'")
        self.assertEqual(steps['Check documentation links and rendering']['if'], "steps.scope.outputs.mode == 'docs'")
        for name in ('Protect published release history', 'Build download site with separate Development test ZIP',
                     'Verify embedded preview repository', 'Check reproducible release output', 'Archive Pages content'):
            self.assertNotIn('if', steps[name])
        for job in jobs.values():
            self.assertEqual(job['if'], "github.ref == 'refs/heads/main'")
        self.assertEqual(jobs['deploy']['needs'], 'build')
        self.assertEqual(jobs['verify-published']['needs'], 'deploy')
        verify = self.steps(jobs['verify-published'])['Check deployed bytes against the uploaded artifact']
        self.assertNotIn('if', verify)
        self.assertEqual(verify['run'], 'python tools/check_published.py "$RUNNER_TEMP/published-site"')
