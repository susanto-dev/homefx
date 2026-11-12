"""The public manual-download site must not activate the candidate repository."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_site
import package


class SiteBoundaryTests(unittest.TestCase):
    def test_site_contains_only_manual_video_downloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = build_site.build_site(Path(temporary) / 'site')
            archive = 'plugin.video.homefx-' + package.validate() + '.zip'
            self.assertEqual({p.name for p in site.iterdir()},
                             {archive, archive + '.sha256', 'index.html', 'LICENSE.txt'})
            page = (site / 'index.html').read_text()
            self.assertIn('No Trakt login', page)
            self.assertNotIn('repository.homefx', page)
            self.assertNotIn('addons.xml', page)
