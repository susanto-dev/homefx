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
import check_published


class SiteBoundaryTests(unittest.TestCase):
    def test_site_contains_verified_repository_and_matching_bootstrap(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = build_site.build_site(Path(temporary) / 'site')
            verified = verify_repository.verify(site / 'repository', channel='preview')
            video = 'plugin.video.homefx-' + package.validate() + '.zip'
            bootstrap = 'repository.homefx-' + verified['current']['repository.homefx'] + '.zip'
            indexed = list((site / 'repository').glob('*/*.zip'))
            expected = {'repository', 'advanced', 'index.html', 'install.html', 'LICENSE.txt'}
            for source in indexed:
                for suffix in ('', '.sha256'):
                    expected.add(source.name + suffix)
                    self.assertEqual((site / (source.name + suffix)).read_bytes(),
                                     Path(str(source) + suffix).read_bytes())
            self.assertEqual({p.name for p in site.iterdir()}, expected)
            self.assertEqual((site / 'advanced' / video).read_bytes(), (site / video).read_bytes())
            page = (site / 'index.html').read_text()
            self.assertIn('href="install.html"', page)
            self.assertIn('Device readiness', (site / 'install.html').read_text())
            self.assertIn('No Trakt login', page)
            self.assertIn('Experimental repository', page)
            self.assertIn('https://susanto-dev.github.io/homefx/', page)
            self.assertIn('Install from repository', page)
            self.assertIn('href="' + bootstrap + '"', page)
            self.assertIn('does not include or redistribute a skin', page)
            self.assertNotIn('{{', page)
            self.assertFalse((site / 'repository' / 'CANDIDATE.txt').exists())
            self.assertTrue((site / 'repository' / 'CHANNEL.txt').exists())

    def test_historical_root_alias_must_remain_identical_to_indexed_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = build_site.build_site(Path(temporary) / 'site')
            current = 'plugin.video.homefx-' + package.validate() + '.zip'
            historical = next(path for path in site.glob('plugin.video.homefx-*.zip') if path.name != current)
            original = historical.read_bytes()
            indexed = site / 'repository/plugin.video.homefx' / historical.name
            for replacement in (None, b'changed old archive'):
                if replacement is None:
                    historical.unlink()
                else:
                    historical.write_bytes(replacement)
                with self.assertRaises(check_published.PublishedCheckError):
                    check_published._expected(site)
                self.assertEqual(indexed.read_bytes(), original)
                historical.write_bytes(original)
            check_published._expected(site)

    def test_kodi_main_listing_keeps_only_repository_with_manual_zip_in_advanced(self):
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
            self.assertGreaterEqual(len(names), 2)
            parser = ListingLinks()
            parser.feed((site / 'index.html').read_text())
            bootstrap = 'repository.homefx-' + verify_repository.verify(site / 'repository', channel='preview')['current']['repository.homefx'] + '.zip'
            # Only one ZIP is offered on the unconfigured main source page.
            self.assertEqual({name for name in parser.links if name.endswith('.zip')}, {bootstrap})
            self.assertIn('advanced/', parser.links)
            advanced = ListingLinks()
            advanced.feed((site / 'advanced/index.html').read_text())
            self.assertEqual({name for name in advanced.links if name.endswith('.zip')},
                             {'plugin.video.homefx-' + package.validate() + '.zip'})
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

    def test_guide_render_failure_does_not_promote_partial_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / 'site'
            with patch.object(build_site.guide_page, 'build', side_effect=ValueError('invalid guide')):
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
