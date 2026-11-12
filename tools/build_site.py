"""Build a static, credential-free preview download directory."""
import html
import shutil
from pathlib import Path
from package import ROOT, build, validate


def build_site(output=None):
    archive = build()
    version = validate()
    site = Path(output) if output else ROOT / 'dist/site'
    site.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, site / archive.name)
    shutil.copyfile(archive.with_suffix('.zip.sha256'), site / (archive.name + '.sha256'))
    shutil.copyfile(ROOT / 'LICENSE', site / 'LICENSE.txt')
    digest = archive.with_suffix('.zip.sha256').read_text().split()[0]
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeFX — Kodi preview</title>
<style>body{font:18px/1.6 system-ui,sans-serif;background:#18263a;color:#eef5fa;max-width:48rem;margin:4rem auto;padding:0 1.5rem}a{color:#9ce3ef}h1{font-size:3rem;line-height:1.1}code{overflow-wrap:anywhere}li{margin:.5rem 0}.download{display:inline-block;background:#9ce3ef;color:#18263a;padding:.8rem 1.2rem;border-radius:.4rem;font-weight:700}a:focus-visible{outline:3px solid white;outline-offset:5px}</style>
</head><body><main><p>Kodi 21.2 · Arctic Zephyr Reloaded</p><h1>HomeFX Preview</h1>
<p>Version VERSION — a small prototype for movie lists, episode browsing and home-screen widgets.</p>
<p><strong>Synthetic data only.</strong> No Trakt login, playable sources or playback. Watched changes affect local demo data only. Kodi installation and TV compatibility have not yet been verified.</p>
<p><a class="download" href="ARCHIVE">Download preview ZIP</a></p>
<p><a href="ARCHIVE.sha256">SHA-256 checksum</a></p><p><code>DIGEST</code></p>
<h2>Try it on your TV</h2><ol><li>Download the ZIP and transfer it to your device.</li>
<li>In Kodi, open Add-ons → Install from zip file and select the downloaded file.</li>
<li>Open Video add-ons → HomeFX Preview. Browse the demo lists and series.</li>
<li>In your skin’s widget settings, choose a folder from HomeFX Preview as a widget source.</li></ol>
<p><a href="https://github.com/susanto-dev/homefx/blob/main/docs/testing-on-tv.md">Full TV test checklist</a> · <a href="https://github.com/susanto-dev/homefx">Source and documentation</a></p>
<p>This is a manual ZIP preview, not a Kodi add-on repository or automatic update channel. Keep your existing skin.</p>
<p>Original code and geometric placeholder artwork. <a href="LICENSE.txt">MIT licence</a>. No paid plugin, analytics, external fonts or account credentials are used by this download page.</p>
</main></body></html>'''
    for token, value in [('VERSION', version), ('ARCHIVE', archive.name), ('DIGEST', digest)]:
        page = page.replace(token, html.escape(value))
    (site / 'index.html').write_text(page, encoding='utf-8')
    return site


if __name__ == '__main__':
    print(build_site())
