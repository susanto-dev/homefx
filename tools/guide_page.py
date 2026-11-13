"""Render the reviewed installation Markdown as a bounded, static guide page."""
from pathlib import Path
import re
import stat

from markdown_it import MarkdownIt


MAX_SOURCE_BYTES = 64 * 1024
MAX_PAGE_BYTES = 256 * 1024


def render(source):
    """Render original documentation, with raw HTML and embedded images disabled."""
    if not isinstance(source, str) or not source.strip() or len(source.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValueError('Invalid installation guide')
    markdown = MarkdownIt('commonmark', {'html': False}).disable('image')
    tokens = markdown.parse(source)
    used = set()
    for index, token in enumerate(tokens):
        if token.type == 'heading_open':
            title = tokens[index + 1].content.lower()
            base = re.sub(r'[^a-z0-9 -]', '', title).replace(' ', '-') or 'section'
            anchor, suffix = base, 0
            while anchor in used:
                suffix += 1
                anchor = base + '-' + str(suffix)
            used.add(anchor)
            token.attrSet('id', anchor)
    body = markdown.renderer.render(tokens, markdown.options, {})
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Install HomeFX on Android and Google TV</title>
<meta name="description" content="Repository-first HomeFX preview installation, first-use checks and demo widgets for Kodi on Android and Google TV.">
<style>
*{box-sizing:border-box}body{margin:0;background:#18263a;color:#eef5fa;font:18px/1.65 system-ui,sans-serif}
.wrap{max-width:48rem;margin:auto;padding:1rem clamp(1rem,4vw,2rem) 3rem}a{color:#9ce3ef;overflow-wrap:anywhere}
a:focus-visible{outline:3px solid #fff;outline-offset:4px}nav{border-bottom:1px solid #65788f;margin-bottom:1.5rem}
nav a{display:inline-block;padding:.65rem .15rem;margin-right:1rem}h1{font-size:clamp(2rem,7vw,2.8rem);line-height:1.15}
h2{font-size:1.5rem;line-height:1.3;margin-top:2.5rem}h3{font-size:1.15rem;margin-top:1.8rem}li{margin:.65rem 0}
ol,ul{padding-left:1.5rem}code{font-size:.92em;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}
blockquote{margin:1.25rem 0;padding:.25rem 1rem;border-left:4px solid #9ce3ef;background:#22364f}
footer{margin-top:2.5rem;border-top:1px solid #65788f;padding-top:1rem;font-size:.9rem}
</style></head><body><div class="wrap">
<nav aria-label="Guide navigation"><a href="index.html">HomeFX downloads</a><a href="https://github.com/susanto-dev/homefx/blob/main/docs/install.md">Read on GitHub</a></nav>
<main>''' + body + '''</main>
<footer>Original HomeFX documentation. <a href="LICENSE.txt">MIT licence</a>. No analytics, scripts, external fonts or account forms.</footer>
</div></body></html>'''
    if len(page.encode('utf-8')) > MAX_PAGE_BYTES:
        raise ValueError('Installation guide exceeds bounds')
    return page


def build(source):
    """Read only the bounded regular guide file; source tree must be quiescent."""
    source = Path(source).absolute()
    if any(path.is_symlink() for path in (source,) + tuple(source.parents)):
        raise ValueError('Unsafe installation guide source')
    if not stat.S_ISREG(source.stat().st_mode):
        raise ValueError('Unsafe installation guide source')
    with source.open('rb') as stream:
        content = stream.read(MAX_SOURCE_BYTES + 1)
    if len(content) > MAX_SOURCE_BYTES:
        raise ValueError('Installation guide exceeds bounds')
    return render(content.decode('utf-8'))
