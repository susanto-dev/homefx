"""Static guide rendering, safe source reads and usable local navigation."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import guide_page


class PageElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.tags = []
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        if 'id' in attributes:
            self.ids.append(attributes['id'])
        if tag == 'a':
            self.links.append(attributes.get('href', ''))
        if tag == 'meta' and 'name' in attributes:
            self.metadata[attributes['name']] = attributes.get('content', '')


class GuidePageTests(unittest.TestCase):
    def test_phone_metadata_headings_and_fragment_navigation_are_preserved(self):
        source = '# Install HomeFX\n\n[Start](#1-before-you-begin)\n\n## 1. Before you begin\n\nFirst.\n\n## Repeat\n\n## Repeat\n'
        page = guide_page.render(source)
        self.assertEqual(guide_page.render(source), page)
        parsed = PageElements()
        parsed.feed(page)
        self.assertEqual(parsed.ids, ['install-homefx', '1-before-you-begin', 'repeat', 'repeat-1'])
        self.assertEqual(parsed.metadata['viewport'], 'width=device-width,initial-scale=1')
        self.assertIn('#1-before-you-begin', parsed.links)
        self.assertIn('index.html', parsed.links)
        self.assertIn('LICENSE.txt', parsed.links)
        self.assertIn('https://github.com/susanto-dev/homefx/blob/main/docs/install.md', parsed.links)
        self.assertIn('main', parsed.tags)
        self.assertNotIn('script', parsed.tags)

    def test_raw_html_scripts_images_and_active_urls_are_not_embedded(self):
        page = guide_page.render('# Fixture\n\n<script>synthetic()</script>\n\n'
                                 '<iframe src="https://example.invalid/"></iframe>\n\n'
                                 '[unsafe](javascript:synthetic())\n\n'
                                 '![image](https://example.invalid/picture.png)\n')
        parsed = PageElements()
        parsed.feed(page)
        self.assertFalse({'script', 'iframe', 'img', 'form'} & set(parsed.tags))
        self.assertFalse(any(href.lower().startswith('javascript:') for href in parsed.links))
        self.assertIn('&lt;script&gt;', page)

    def test_guide_source_and_output_are_bounded_and_blank_input_rejected(self):
        for source in ('', ' \n', 'x' * (guide_page.MAX_SOURCE_BYTES + 1), None):
            with self.subTest(kind=type(source).__name__):
                with self.assertRaises(ValueError):
                    guide_page.render(source)
        with patch.object(guide_page, 'MAX_PAGE_BYTES', 10):
            with self.assertRaises(ValueError):
                guide_page.render('# Fixture')

    def test_regular_source_read_rejects_symlink_parent_and_oversize(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'guide.md'
            source.write_text('# Fixture\n')
            self.assertIn('<h1 id="fixture">Fixture</h1>', guide_page.build(source))
            link = root / 'alias.md'
            link.symlink_to(source)
            with self.assertRaises(ValueError):
                guide_page.build(link)
            alias = root / 'directory'
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                guide_page.build(alias / 'guide.md')
            with self.assertRaises(ValueError):
                guide_page.build(root)
            source.write_bytes(b'x' * (guide_page.MAX_SOURCE_BYTES + 1))
            with self.assertRaises(ValueError):
                guide_page.build(source)

    def test_canonical_guide_has_resolvable_fragments_and_no_external_embeds(self):
        parsed = PageElements()
        parsed.feed(guide_page.build(ROOT / 'docs/install.md'))
        self.assertEqual(len(parsed.ids), len(set(parsed.ids)))
        for target in parsed.links:
            if target.startswith('#'):
                self.assertIn(target[1:], parsed.ids)
        self.assertFalse({'script', 'iframe', 'img', 'form'} & set(parsed.tags))
