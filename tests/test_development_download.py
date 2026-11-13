"""Direct-source Development downloads use fabricated public configuration only."""
from contextlib import redirect_stdout
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_development_test as builder
import build_site
import check_published
import check_reproducibility
import development_download as download
import unpack_site

CONFIG = {'HOMEFX_TRAKT_ENVIRONMENT': 'Development', 'TRAKT_CLIENT_ID': 'fabricated-public-id',
          'TRAKT_REDIRECT_URI': 'urn:homefx:fabricated'}


class DevelopmentDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.plain = build_site.build_site(cls.root / 'plain')
        cls.site = build_site.build_site(cls.root / 'configured', development_environment=CONFIG)
        cls.files, _ = build_site._tree_bytes(cls.site)
        cls.name = download.verify(cls.files)
        cls.pair = {name: cls.files[name] for name in (cls.name, cls.name + '.sha256')}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def rewrite(self, transform):
        with ZipFile(io.BytesIO(self.pair[self.name])) as source:
            entries = [(entry, source.read(entry)) for entry in source.infolist()]
        entries = transform(entries)
        output = io.BytesIO()
        with ZipFile(output, 'w') as archive:
            for entry, data in entries:
                archive.writestr(entry, data)
        data = output.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        name = download.PREFIX + builder.VERSION + '-' + digest + '.zip'
        return {name: data, name + '.sha256': (digest + '  ' + name + '\n').encode('ascii')}

    def reject(self, files):
        with self.assertRaisesRegex(download.DownloadError, '^invalid Development download$'):
            download.verify(files)

    def test_download_is_listable_and_existing_repository_bytes_are_unchanged(self):
        plain_files, plain_dirs = build_site._tree_bytes(self.plain)
        files, directories = build_site._tree_bytes(self.site)
        self.assertEqual(directories, plain_dirs)
        video_name = download.verify(files, video=True)
        self.assertIsNotNone(video_name)
        self.assertEqual(set(files) - set(plain_files), set(self.pair) | {video_name, video_name + '.sha256'})
        self.assertNotIn(b'plugin.video.homefx.development', files['repository/addons.xml'])
        for name, data in plain_files.items():
            if name != 'index.html':
                self.assertEqual(files[name], data)
        self.assertNotIn(b'script.homefx.development', files['repository/addons.xml'])
        self.assertEqual(download.verify(plain_files), None)

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.active = None
                self.found = set()

            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.active = [attrs[0][1], ''] if attrs and attrs[0][0] == 'href' else None

            def handle_data(self, text):
                if self.active is not None:
                    self.active[1] += text

            def handle_endtag(self, tag):
                if tag == 'a' and self.active is not None:
                    name, label = self.active
                    if name == label.strip():
                        self.found.add(name)
                    self.active = None

        links = Links()
        links.feed(files['index.html'].decode('utf-8'))
        self.assertIn(self.name, links.found)
        self.assertIn(video_name, links.found)
        self.assertIn('Development account test', files['index.html'].decode('utf-8'))
        self.assertIn('No file transfer is needed', files['index.html'].decode('utf-8'))
        self.assertNotIn(CONFIG['TRAKT_CLIENT_ID'], files['index.html'].decode('utf-8'))
        self.assertEqual(build_site.build_site(self.site, development_environment=CONFIG), self.site)

    def test_incomplete_extra_wrong_hash_and_checksum_pairs_fail(self):
        mutations = [
            {self.name: self.pair[self.name]},
            {self.name + '.sha256': self.pair[self.name + '.sha256']},
            dict(self.pair, **{self.name + '.extra': b'private'}),
            dict(self.pair, **{self.name: self.pair[self.name] + b'changed'}),
            dict(self.pair, **{self.name + '.sha256': b'wrong'}),
        ]
        for files in mutations:
            with self.subTest(names=sorted(files)):
                self.reject(files)
        with patch.object(builder, 'MAX_ZIP', len(self.pair[self.name]) - 1):
            self.reject(self.pair)

    def test_rehashed_unknown_members_paths_links_and_source_changes_fail(self):
        def append(name, mode=stat.S_IFREG | 0o644):
            def transform(entries):
                entry = ZipInfo(name)
                entry.external_attr = mode << 16
                return entries + [(entry, b'private')]
            return transform

        def linked_existing(entries):
            entries[0][0].external_attr = (stat.S_IFLNK | 0o777) << 16
            return entries

        def extra_metadata(entries):
            entries[0][0].comment = b'private'
            return entries

        transforms = [linked_existing, extra_metadata, append(builder.ADDON_ID + '/private-token.json'),
                      append('../outside'), append('/absolute'),
                      append(builder.ADDON_ID + '/link', stat.S_IFLNK | 0o777),
                      lambda entries: entries + [entries[0]],
                      lambda entries: [(entry, b'changed' if entry.filename.endswith('/default.py') else data)
                                       for entry, data in entries],
                      lambda entries: entries[1:]]
        for index, transform in enumerate(transforms):
            with self.subTest(index=index):
                self.reject(self.rewrite(transform))
        with patch.object(builder, 'MAX_TOTAL', 1):
            self.reject(self.pair)
        with patch.object(builder, 'MAX_FILE', 1):
            self.reject(self.pair)

    def test_rehashed_private_production_and_noncanonical_configuration_fail(self):
        valid = {'schema': 1, 'environment': 'Development', 'client_id': CONFIG['TRAKT_CLIENT_ID'],
                 'redirect_uri': CONFIG['TRAKT_REDIRECT_URI']}
        invalid = [dict(valid, client_secret='PRIVATE'), dict(valid, environment='Production'),
                   dict(valid, schema=True), dict(valid, redirect_uri='/PRIVATE'),
                   dict(valid, client_id=''), {'schema': 1}]
        values = [json.dumps(value).encode() for value in invalid]
        values.extend((b'x' * (download.MAX_CONFIG_BYTES + 1),
                       json.dumps(valid).encode(),  # valid values, noncanonical packaged bytes
                       json.dumps(valid).replace('"schema": 1', '"schema": 1, "schema": 1').encode()))
        for data in values:
            with self.subTest(size=len(data)):
                def transform(entries):
                    return [(entry, data if entry.filename == download.CONFIG_PATH else content)
                            for entry, content in entries]
                self.reject(self.rewrite(transform))

    def test_explicit_configuration_and_rebuild_failure_preserve_existing_output(self):
        before = build_site._tree_bytes(self.site)
        with self.assertRaisesRegex(ValueError, 'Site output differs'):
            build_site.build_site(self.site, development_environment=dict(CONFIG, TRAKT_CLIENT_ID='other-app'))
        self.assertEqual(build_site._tree_bytes(self.site), before)
        fresh = self.root / 'invalid-config'
        with self.assertRaises(builder.BuildError):
            build_site.build_site(fresh, development_environment={})
        self.assertFalse(fresh.exists())
        with patch.object(build_site, 'build_site', return_value='output') as build, redirect_stdout(io.StringIO()):
            build_site.main([], CONFIG)
            build.assert_called_once_with(development_environment=None)
            build.reset_mock()
            build_site.main(['--development'], CONFIG)
            build.assert_called_once_with(development_environment=CONFIG)

    def test_published_verifier_checks_every_download_byte_and_rejects_partial_extension(self):
        requests = []
        def fetch(url, limit, timeout):
            name = url.removeprefix(check_published.BASE_URL)
            requests.append(name)
            self.assertEqual(limit, len(self.files[name]) + 1)
            return self.files[name]
        result = check_published.check(self.site, fetch=fetch)
        self.assertEqual(set(requests), set(self.files))
        self.assertEqual(result['files'], len(self.files))
        self.assertIn(self.name, requests)
        for bad in (self.name, self.name + '.sha256'):
            def corrupted(url, limit, timeout):
                name = url.removeprefix(check_published.BASE_URL)
                return b'wrong' if name == bad else self.files[name]
            with self.assertRaises(check_published.PublishedCheckError):
                check_published.check(self.site, fetch=corrupted)
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / 'site'
            shutil.copytree(self.site, site)
            (site / (self.name + '.sha256')).unlink()
            fetch = Mock()
            with self.assertRaises(check_published.PublishedCheckError):
                check_published.check(site, fetch=fetch)
            fetch.assert_not_called()
            (site / self.name).unlink()
            with self.assertRaises(check_published.PublishedCheckError):
                check_published.check(site, fetch=fetch)
            fetch.assert_not_called()
            (site / self.name).write_bytes(self.pair[self.name])
            (site / (self.name + '.sha256')).write_bytes(self.pair[self.name + '.sha256'])
            (site / 'index.html').write_text('missing link')
            with self.assertRaises(check_published.PublishedCheckError):
                check_published.check(site, fetch=fetch)
            fetch.assert_not_called()

    def test_unpack_accepts_configured_site_and_rejects_tampered_download_without_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / 'site.tar'
            with tarfile.open(archive, 'w') as bundle:
                bundle.add(self.site, arcname='.')
            unpack_site.unpack(archive, root / 'valid')
            self.assertEqual(check_published._expected(root / 'valid'), self.files)
            (root / 'valid' / self.name).write_bytes(b'wrong')
            with tarfile.open(archive, 'w') as bundle:
                bundle.add(root / 'valid', arcname='.')
            with self.assertRaises(unpack_site.UnpackError):
                unpack_site.unpack(archive, root / 'invalid')
            self.assertFalse((root / 'invalid').exists())

    def test_configured_reproducibility_and_cli_require_explicit_opt_in(self):
        result = check_reproducibility.check(development_environment=CONFIG)
        self.assertEqual(result['site_files'], len(self.files))
        with patch.object(check_reproducibility, 'check', return_value=result) as check, redirect_stdout(io.StringIO()):
            check_reproducibility.main([], CONFIG)
            check.assert_called_once_with(development_environment=None)
            check.reset_mock()
            check_reproducibility.main(['--development'], CONFIG)
            check.assert_called_once_with(development_environment=CONFIG)
