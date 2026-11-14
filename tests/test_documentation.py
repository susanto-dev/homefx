"""Offline installation-journey links; no remote requests or live-account data."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_site
import guide_page


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'a':
            self.links.append(values.get('href', ''))
        if 'id' in values:
            self.ids.add(values['id'])


def markdown_links(source):
    for token in MarkdownIt('commonmark').parse(source):
        for child in token.children or ():
            if child.type == 'link_open':
                yield child.attrGet('href')


def local_target(source, href):
    """Map project GitHub links to checkout files; external URLs stay unchecked."""
    parsed = urlsplit(href)
    prefix = '/susanto-dev/homefx/blob/main/'
    if parsed.scheme or parsed.netloc:
        if parsed.scheme == 'https' and parsed.netloc == 'github.com' and parsed.path.startswith(prefix):
            return ROOT / unquote(parsed.path[len(prefix):]), unquote(parsed.fragment)
        return None
    return source.parent / unquote(parsed.path) if parsed.path else source, unquote(parsed.fragment)


class DocumentationTests(unittest.TestCase):
    def test_installation_journey_links_resolve_in_checkout(self):
        documents = sorted([*ROOT.glob('*.md'), *(ROOT / 'docs').rglob('*.md')])
        for source in documents:
            relative = source.relative_to(ROOT).as_posix()
            for href in markdown_links(source.read_text(encoding='utf-8')):
                with self.subTest(source=relative, href=href):
                    target = local_target(source, href)
                    if target is None:
                        continue
                    path, fragment = target
                    self.assertTrue(path.resolve().is_relative_to(ROOT), 'Link escapes checkout')
                    self.assertTrue(path.is_file(), 'Missing linked file')
                    if fragment and path.suffix == '.md':
                        parsed = Elements()
                        parsed.feed(guide_page.render(path.read_text(encoding='utf-8')))
                        self.assertIn(fragment, parsed.ids, 'Missing heading anchor')

    def test_readme_landing_and_guide_navigation_stay_connected(self):
        readme = set(markdown_links((ROOT / 'README.md').read_text(encoding='utf-8')))
        self.assertIn('docs/install.md', readme)
        self.assertIn('https://susanto-dev.github.io/homefx/install.html', readme)
        landing = Elements()
        landing.feed(build_site._page('0.0.0', 'plugin.video.homefx-0.0.0.zip',
                                      'repository.homefx-0.0.0.zip', '0' * 64))
        self.assertIn('install.html', landing.links)
        guide = Elements()
        guide.feed(guide_page.build(ROOT / 'docs/install.md'))
        self.assertIn('index.html', guide.links)
        self.assertIn('LICENSE.txt', guide.links)
        for href in guide.links:
            if href.startswith('#'):
                self.assertIn(unquote(href[1:]), guide.ids)

    def test_markdown_links_include_reference_links_but_ignore_code_examples(self):
        source = '[Read][guide]\n\n[guide]: guide.md#start\n\n`[not a link](missing.md)`\n'
        self.assertEqual(list(markdown_links(source)), ['guide.md#start'])
