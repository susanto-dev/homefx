"""Changed-path selection fails closed without services or repository credentials."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_scope


class ScopeTests(unittest.TestCase):
    def test_only_nonempty_markdown_allowlist_is_light(self):
        self.assertEqual(ci_scope.classify(['README.md', 'docs/install.md', 'docs/nested/guide.md']),
                         ('docs', 'documentation_only'))
        for path in ('addons/plugin.video.homefx/default.py', 'addons/license.md', 'LICENSE',
                     'requirements.txt', 'tools/ci_scope.py', 'tests/test_model.py',
                     '.github/workflows/pages.yml', 'docs/example.py', 'docs/image.png',
                     'docs/../requirements.txt', '/docs/install.md', 'docs/new\nline.md',
                     'docs/guide.md/extra', 'new-directory/README.md', None):
            with self.subTest(path=path):
                self.assertEqual(ci_scope.classify(['docs/backlog.md', path])[0], 'full')
        self.assertEqual(ci_scope.classify([]), ('full', 'empty_diff'))

    def test_manual_schedule_unknown_or_malformed_input_is_full(self):
        with patch.object(ci_scope, 'git_output') as git:
            for event in ('workflow_dispatch', 'schedule', 'unknown'):
                self.assertEqual(ci_scope.select(event, {}), ('full', 'manual_or_scheduled'))
            for event in ({}, None, {'before': '0' * 40}, {'before': '--help'}, {'before': 'a' * 39}):
                self.assertEqual(ci_scope.select('push', event), ('full', 'unknown_base'))
            git.assert_not_called()

    def test_missing_history_git_failures_and_invalid_diff_are_full(self):
        for failure in (OSError(), subprocess.TimeoutExpired('git', 20),
                        subprocess.CalledProcessError(1, 'git')):
            with patch.object(ci_scope, 'git_output', side_effect=failure):
                self.assertEqual(ci_scope.select('push', {'before': 'a' * 40}), ('full', 'unknown_base'))
        for raw in (b'docs/install.md', b'docs/\xff.md\0'):
            with patch.object(ci_scope, 'git_output', side_effect=[b'', raw]):
                self.assertEqual(ci_scope.select('push', {'before': 'a' * 40}), ('full', 'unknown_base'))

    def test_real_diff_covers_add_delete_rename_and_mixed_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()

            git('init')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            (root / 'docs').mkdir()
            (root / 'docs/old.md').write_text('old')
            (root / 'runtime.py').write_text('original')
            git('add', '.')
            git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD')
            (root / 'docs/old.md').rename(root / 'docs/new.md')
            git('add', '-A')
            git('commit', '-m', 'rename guide')
            self.assertEqual(ci_scope.select('push', {'before': base}, root)[0], 'docs')
            self.assertEqual(ci_scope.select('pull_request', {'pull_request': {'base': {'sha': base}}}, root)[0], 'docs')
            # Deleting code and renaming it to Markdown must retain the old code path.
            (root / 'runtime.py').rename(root / 'docs/runtime.md')
            git('add', '-A')
            git('commit', '-m', 'mixed rename')
            self.assertEqual(ci_scope.select('push', {'before': base}, root)[0], 'full')
            self.assertEqual(ci_scope.select('push', {'before': git('rev-parse', 'HEAD')}, root)[0], 'full')

    def test_publication_compares_cumulative_changes_and_requires_known_ancestor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()

            git('init')
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.invalid')
            (root / 'README.md').write_text('original')
            (root / 'runtime.py').write_text('original')
            git('add', '.')
            git('commit', '-m', 'published')
            published = git('rev-parse', 'HEAD')
            (root / 'runtime.py').write_text('unpublished change')
            git('add', '.')
            git('commit', '-m', 'code not yet published')
            code = git('rev-parse', 'HEAD')
            (root / 'README.md').write_text('new documentation')
            git('add', '.')
            git('commit', '-m', 'later docs')
            event = {'before': code}
            self.assertEqual(ci_scope.select('push', event, root)[0], 'docs')
            self.assertEqual(ci_scope.select('push', event, root, publication=True,
                                             published_base=published)[0], 'full')
            self.assertEqual(ci_scope.select('push', event, root, publication=True,
                                             published_base=code)[0], 'docs')
            for base in (None, '', 'f' * 40):
                self.assertEqual(ci_scope.select('push', event, root, publication=True,
                                                 published_base=base)[0], 'full')
            head = git('rev-parse', 'HEAD')
            git('checkout', '--detach', published)
            (root / 'README.md').write_text('different branch')
            git('add', '.')
            git('commit', '-m', 'non-ancestor')
            unrelated = git('rev-parse', 'HEAD')
            git('checkout', '--detach', head)
            self.assertEqual(ci_scope.select('push', event, root, publication=True,
                                             published_base=unrelated)[0], 'full')
            self.assertEqual(ci_scope.select('workflow_dispatch', event, root, publication=True,
                                             published_base=code)[0], 'full')

    def test_cli_outputs_only_fixed_scope_and_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event, output, summary = (root / name for name in ('event', 'output', 'summary'))
            event.write_text(json.dumps({'before': 'PRIVATE invalid value'}))
            env = {'GITHUB_EVENT_NAME': 'push', 'GITHUB_EVENT_PATH': str(event),
                   'GITHUB_OUTPUT': str(output), 'GITHUB_STEP_SUMMARY': str(summary)}
            capture = io.StringIO()
            with patch.dict(os.environ, env), patch('sys.argv', ['ci_scope.py']), contextlib.redirect_stdout(capture):
                self.assertEqual(ci_scope.main(), 0)
            self.assertEqual(output.read_text(), 'mode=full\n')
            self.assertNotIn('PRIVATE', capture.getvalue() + summary.read_text())
            self.assertIn('unknown_base', capture.getvalue())
