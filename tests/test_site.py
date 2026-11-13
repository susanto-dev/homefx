"""The public preview contains only its verified repository and install artifacts."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_site
import package
import verify_repository


class SiteBoundaryTests(unittest.TestCase):
    def test_site_contains_verified_repository_and_matching_bootstrap(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = build_site.build_site(Path(temporary) / 'site')
            verified = verify_repository.verify(site / 'repository', channel='preview')
            video = 'plugin.video.homefx-' + package.validate() + '.zip'
            bootstrap = 'repository.homefx-' + verified['current']['repository.homefx'] + '.zip'
            self.assertEqual({p.name for p in site.iterdir()},
                             {video, video + '.sha256', bootstrap, bootstrap + '.sha256',
                              'repository', 'index.html', 'LICENSE.txt'})
            for ident, name in (('plugin.video.homefx', video), ('repository.homefx', bootstrap)):
                for suffix in ('', '.sha256'):
                    self.assertEqual((site / (name + suffix)).read_bytes(),
                                     (site / 'repository' / ident / (name + suffix)).read_bytes())
            page = (site / 'index.html').read_text()
            self.assertIn('No Trakt login', page)
            self.assertIn('Experimental repository', page)
            self.assertIn('https://susanto-dev.github.io/homefx/', page)
            self.assertIn('Install from repository', page)
            self.assertIn('href="' + bootstrap + '"', page)
            self.assertIn('does not include or redistribute a skin', page)
            self.assertNotIn('{{', page)
            self.assertFalse((site / 'repository' / 'CANDIDATE.txt').exists())
            self.assertTrue((site / 'repository' / 'CHANNEL.txt').exists())

    def test_kodi_directory_listing_can_discover_both_zip_filenames(self):
        # Kodi 21.2 HTTPDirectory requires href first and filename display text.
        # This original HTMLParser fixture checks those documented constraints;
        # it does not reproduce Kodi's parser or constitute a device test.
        # https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/filesystem/HTTPDirectory.cpp
        class ListingLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.active = None
                self.links = set()

            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.active = [attrs[0][1], ''] if attrs and attrs[0][0] == 'href' else None

            def handle_data(self, data):
                if self.active is not None:
                    self.active[1] += data

            def handle_endtag(self, tag):
                if tag == 'a' and self.active is not None:
                    target, label = self.active
                    if target == label.strip():
                        self.links.add(target)
                    self.active = None

        with tempfile.TemporaryDirectory() as temporary:
            site = build_site.build_site(Path(temporary) / 'site')
            names = {path.name for path in site.glob('*.zip')}
            self.assertEqual(len(names), 2)
            parser = ListingLinks()
            parser.feed((site / 'index.html').read_text())
            self.assertTrue(names <= parser.links)
            # Ensure the fixture rejects the two browser-valid failure modes.
            for name in names:
                for invalid in ('<a class="download" href="{0}">{0}</a>',
                                '<a href="{0}">Download repository ZIP</a>'):
                    rejected = ListingLinks()
                    rejected.feed(invalid.format(name))
                    self.assertNotIn(name, rejected.links)

    def test_identical_site_is_accepted_but_changed_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = build_site.build_site(Path(temporary) / 'site')
            before = build_site._tree_bytes(site)
            self.assertEqual(build_site.build_site(site), site)
            self.assertEqual(build_site._tree_bytes(site), before)
            (site / 'index.html').write_text('existing release')
            with self.assertRaisesRegex(ValueError, 'Site output differs'):
                build_site.build_site(site)
            self.assertEqual((site / 'index.html').read_text(), 'existing release')
            self.assertEqual(list(Path(temporary).glob('.homefx-site-*')), [])

    def test_failed_verification_does_not_leave_publishable_partial_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / 'site'
            with patch.object(build_site.verify_repository, 'verify', side_effect=ValueError('bad')):
                with self.assertRaises(ValueError):
                    build_site.build_site(site)
            self.assertFalse(site.exists())
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_default_inventory_is_forwarded_and_failed_retention_never_downgrades(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'releases').mkdir()
            inventory = root / 'releases/inventory.json'
            inventory.write_text('invalid retention')
            original = build_site.repository.build
            with patch.object(build_site, 'ROOT', root), \
                    patch.object(build_site.repository, 'build', wraps=original) as builder:
                with self.assertRaises(ValueError):
                    build_site.build_site(root / 'site')
                self.assertEqual(builder.call_args.kwargs['retain_manifest'], inventory)
                self.assertEqual(builder.call_args.kwargs['channel'], 'preview')
            self.assertFalse((root / 'site').exists())

    def test_reviewed_retained_archive_is_in_public_tree_but_not_current_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'old-source'
            shutil.copytree(package.ADDON, source)
            manifest = source / 'addon.xml'
            manifest.write_text(manifest.read_text().replace('version="' + package.validate() + '"',
                                                            'version="0.0.1"', 1))
            archive = package.build(source, root / 'archives')
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps({'schema': 1, 'packages': [{
                'id': 'plugin.video.homefx', 'version': '0.0.1',
                'path': 'archives/' + archive.name,
                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}]}))
            site = build_site.build_site(root / 'site', retain_manifest=inventory)
            retained = site / 'repository/plugin.video.homefx' / archive.name
            self.assertEqual(retained.read_bytes(), archive.read_bytes())
            verified = verify_repository.verify(site / 'repository', channel='preview')
            self.assertEqual(verified['retained'], 1)
            self.assertEqual(verified['current']['plugin.video.homefx'], package.validate())
            self.assertNotIn('version="0.0.1"', (site / 'repository/addons.xml').read_text())

    def test_unsafe_destination_and_package_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'target'
            target.mkdir()
            link = root / 'site'
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Unsafe site output'):
                build_site.build_site(link)
            site = root / 'actual-site'
            with self.assertRaisesRegex(ValueError, 'Package output must be outside site'):
                build_site.build_site(site, package_output=site / 'package')
            self.assertFalse(site.exists())
