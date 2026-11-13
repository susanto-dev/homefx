"""Release integrity and immutable-history mutations use temporary local artifacts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import package
import release_history as history
import repository


class ReleaseHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.releases = self.root / 'releases'
        repository.build(self.releases)
        self.inventory = self.releases / 'inventory.json'
        (self.releases / 'release-inventory.json').rename(self.inventory)
        self.original = json.loads(self.inventory.read_text())

    def write(self, value):
        self.inventory.write_text(json.dumps(value))

    def previous(self, value=None):
        result = self.root / 'prior.json'
        result.write_text(json.dumps(self.original if value is None else value))
        return result

    def old_archive(self):
        source = self.root / 'old-source'
        shutil.copytree(package.ADDON, source)
        manifest = source / 'addon.xml'
        manifest.write_text(manifest.read_text().replace('version="' + package.validate() + '"',
                                                       'version="0.0.1"', 1))
        archive = package.build(source, self.releases / 'plugin.video.homefx')
        record = {'id': 'plugin.video.homefx', 'version': '0.0.1',
                  'path': archive.relative_to(self.releases).as_posix(),
                  'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        value = json.loads(self.inventory.read_text())
        value['packages'].append(record)
        self.write(value)
        return record, archive

    def test_current_packages_and_retention_are_verified_without_changing_inputs(self):
        record, archive = self.old_archive()
        before = {str(p): p.read_bytes() for p in self.releases.rglob('*') if p.is_file()}
        result = history.verify_history(self.inventory, self.previous())
        self.assertEqual(result['packages'], 3)
        self.assertEqual(result['previous'], 2)
        self.assertEqual({str(p): p.read_bytes() for p in self.releases.rglob('*') if p.is_file()}, before)
        self.assertTrue(archive.exists())
        self.assertEqual(result['current']['plugin.video.homefx'], package.validate())

    def test_missing_or_corrupt_current_archive_fails(self):
        for mutation in ('missing', 'hash', 'bytes'):
            with self.subTest(mutation=mutation):
                value = json.loads(json.dumps(self.original))
                item = value['packages'][0]
                archive = self.releases / item['path']
                saved = archive.read_bytes()
                if mutation == 'missing':
                    value['packages'].pop(0)
                elif mutation == 'hash':
                    item['sha256'] = '0' * 64
                else:
                    archive.write_bytes(saved + b'changed')
                    item['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.write(value)
                with self.assertRaises(history.HistoryError):
                    history.verify_history(self.inventory)
                archive.write_bytes(saved)
        self.write(self.original)

    def test_prior_identity_path_hash_and_presence_are_immutable(self):
        record, archive = self.old_archive()
        original = json.loads(self.inventory.read_text())
        previous = self.previous(original)
        for mutation in ('remove', 'path', 'hash', 'version'):
            with self.subTest(mutation=mutation):
                value = json.loads(json.dumps(original))
                item = value['packages'][-1]
                if mutation == 'remove':
                    value['packages'].pop()
                elif mutation == 'path':
                    item['path'] = 'archive/' + archive.name
                elif mutation == 'hash':
                    item['sha256'] = 'f' * 64
                else:
                    item['version'] = '0.0.2'
                    item['path'] = item['path'].replace('0.0.1', '0.0.2')
                self.write(value)
                with self.assertRaisesRegex(history.HistoryError, 'published history changed'):
                    history.verify_history(self.inventory, previous)

    def test_archive_contract_and_aggregate_bounds_are_enforced(self):
        _, archive = self.old_archive()
        archive.write_bytes(b'not a zip')
        value = json.loads(self.inventory.read_text())
        value['packages'][-1]['sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.write(value)
        with self.assertRaises(history.HistoryError):
            history.verify_history(self.inventory)
        self.write(self.original)
        with patch.object(repository, 'MAX_RETAINED_BYTES', 1), self.assertRaises(history.HistoryError):
            history.verify_history(self.inventory)

    def test_malformed_duplicate_oversized_and_symlinked_inputs_fail(self):
        for raw in ('{"schema":1,"schema":1,"packages":[]}', '[]',
                    ' ' * (repository.MAX_INVENTORY + 1)):
            self.inventory.write_text(raw)
            with self.assertRaises(history.HistoryError):
                history.verify_history(self.inventory)
        self.write(self.original)
        alias = self.root / 'alias.json'
        alias.symlink_to(self.inventory)
        with self.assertRaises(history.HistoryError):
            history.verify_history(alias)
        prior = self.previous()
        prior.write_text('{broken')
        with self.assertRaises(history.HistoryError):
            history.verify_history(self.inventory, prior)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip().decode()

    def init_git(self, with_inventory):
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'fixture.txt').write_text('synthetic')
        self.git('add', 'fixture.txt')
        if with_inventory:
            self.git('add', 'releases/inventory.json')
        self.git('commit', '-qm', 'Synthetic fixture')
        return self.git('rev-parse', 'HEAD')

    def test_git_base_preserves_history_and_valid_missing_manifest_bootstraps(self):
        base = self.init_git(False)
        self.assertEqual(history.verify_history(self.inventory, base_ref=base,
                         git_root=self.root)['previous'], 0)
        self.git('add', 'releases/inventory.json')
        self.git('commit', '-qm', 'Record synthetic releases')
        recorded = self.git('rev-parse', 'HEAD')
        self.assertEqual(history.verify_history(self.inventory, base_ref=recorded,
                         git_root=self.root)['previous'], 2)
        value = json.loads(json.dumps(self.original))
        value['packages'][0]['sha256'] = '0' * 64
        self.write(value)
        with self.assertRaisesRegex(history.HistoryError, 'published history changed'):
            history.verify_history(self.inventory, base_ref=recorded, git_root=self.root)

    def test_git_missing_ref_invalid_refs_and_oversized_prior_never_bootstrap(self):
        base = self.init_git(True)
        for ref in ('missing-ref', '--help', 'HEAD:secrets', 'HEAD;touch unsafe', '../main'):
            with self.subTest(ref=ref), self.assertRaises(history.HistoryError):
                history.verify_history(self.inventory, base_ref=ref, git_root=self.root)
        self.inventory.write_text(' ' * (repository.MAX_INVENTORY + 1))
        self.git('add', 'releases/inventory.json')
        self.git('commit', '-qm', 'Oversized fixture')
        self.write(self.original)
        with self.assertRaisesRegex(history.HistoryError, 'base inventory bounds'):
            history.verify_history(self.inventory, base_ref='HEAD', git_root=self.root)
        with self.assertRaisesRegex(history.HistoryError, 'ambiguous prior history'):
            history.verify_history(self.inventory, self.previous(), base_ref=base, git_root=self.root)

    def test_cli_errors_are_fixed_and_do_not_echo_input_path(self):
        with patch.object(sys, 'argv', ['release_history.py', '/private/missing-inventory']), \
                patch('sys.stderr') as stderr, self.assertRaises(SystemExit) as exited:
            history.main()
        self.assertEqual(exited.exception.code, 1)
        message = ''.join(str(call.args[0]) for call in stderr.write.call_args_list)
        self.assertNotIn('/private', message)
        self.assertIn('Release history check failed', message)
