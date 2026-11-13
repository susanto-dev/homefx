"""Stage a static experimental Kodi repository and credential-free preview page."""
import html
import os
from pathlib import Path
import shutil
import tempfile

from package import ROOT, build, validate
import repository
import guide_page
import verify_repository


def _tree_bytes(root):
    """Bound an existing destination before accepting an identical rebuild."""
    files, directories, total, nodes = {}, set(), 0, 0
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Unsafe site output")
    for directory, subdirs, names in os.walk(str(root), followlinks=False):
        for name in subdirs + names:
            nodes += 1
            path = Path(directory) / name
            if nodes > 512 or path.is_symlink():
                raise ValueError("Unsafe site output")
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                directories.add(relative)
            elif path.is_file():
                with path.open("rb") as stream:
                    data = stream.read(repository.MAX_CONTENT + 1)
                total += len(data)
                if len(data) > repository.MAX_CONTENT or total > 128 * 1024 * 1024:
                    raise ValueError("Site output exceeds bounds")
                files[relative] = data
            else:
                raise ValueError("Unsafe site output")
    return files, directories


def _page(version, archive, bootstrap, digest):
    page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeFX — Kodi preview repository</title>
<style>body{font:18px/1.6 system-ui,sans-serif;background:#18263a;color:#eef5fa;max-width:48rem;margin:4rem auto;padding:0 1.5rem}a{color:#9ce3ef}h1{font-size:3rem;line-height:1.1}code{overflow-wrap:anywhere}li{margin:.5rem 0}.download{display:inline-block;background:#9ce3ef;color:#18263a;padding:.8rem 1.2rem;border-radius:.4rem;font-weight:700}a:focus-visible{outline:3px solid white;outline-offset:5px}</style>
</head><body><main><p>Kodi 21.2 · Personal home-screen widgets</p><h1>HomeFX Preview</h1>
<p>Video add-on version {{VERSION}} — movie lists, episode browsing and home-screen widgets.</p>
<p><strong>Experimental repository. Synthetic data only.</strong> No Trakt login, playable sources or playback. Watched changes affect local demo data only. Kodi installation, updates and TV compatibility have not yet been verified.</p>
<p><a href="install.html" class="download">Installation and first-use guide</a></p>
<p>New to Kodi? Follow the phone-friendly guide for Android/Google TV installation, restart, safe checks and demo widget setup.</p>
<p>Download the repository ZIP:</p>
<p><a href="{{BOOTSTRAP}}" class="download">{{BOOTSTRAP}}</a></p>
<p><a href="{{BOOTSTRAP}}.sha256">Repository ZIP SHA-256 checksum</a></p>
<h2>Install the repository first</h2><ol>
<li>In Kodi, open Settings → File manager → Add source. Enter <code>https://susanto-dev.github.io/homefx/</code> and name it HomeFX.</li>
<li>Open Add-ons → Install from zip file → HomeFX, then select <code>{{BOOTSTRAP}}</code>. Review any Unknown sources prompt before proceeding. Alternatively, download that ZIP above and transfer it to the TV.</li>
<li>Choose Install from repository → HomeFX Preview Repository → Video add-ons → HomeFX Preview → Install.</li>
<li>Open HomeFX Preview and browse the demo lists. In your existing skin's widget settings, choose a HomeFX folder as a widget source.</li></ol>
<p>The repository supplies HomeFX preview installation and updates. Keep your existing skin installed separately: this repository does not include or redistribute a skin. Availability of this website is not a successful Kodi installation or upgrade test.</p>
<h2>Manual video add-on download</h2>
<p><a href="{{ARCHIVE}}">{{ARCHIVE}}</a> · <a href="{{ARCHIVE}}.sha256">Video ZIP SHA-256 checksum</a></p><p><code>{{DIGEST}}</code></p>
<p><a href="https://github.com/susanto-dev/homefx/blob/main/docs/testing-on-tv.md">TV test checklist</a> · <a href="https://github.com/susanto-dev/homefx">Source and documentation</a></p>
<p>Original code and geometric placeholder artwork. <a href="LICENSE.txt">MIT licence</a>. No paid plugin, analytics, external fonts or account credentials are used by this download page.</p>
</main></body></html>'''
    for token, value in (("VERSION", version), ("ARCHIVE", archive),
                         ("BOOTSTRAP", bootstrap), ("DIGEST", digest)):
        page = page.replace("{{" + token + "}}", html.escape(value))
    return page


def build_site(output=None, package_output=None, retain_manifest=None):
    """Build a fresh or identical complete site; never mutate an existing release.

    No network/publication occurs. Package scratch output is temporary unless the
    caller explicitly supplies package_output; it must be outside the site tree.
    A checked-in inventory, when present, is the default retention input.
    """
    site = Path(output) if output is not None else ROOT / "dist/site"
    site = site.absolute()
    if any(path.is_symlink() for path in (site,) + tuple(site.parents)):
        raise ValueError("Unsafe site output")
    if package_output is not None:
        scratch = Path(package_output).absolute()
        if scratch == site or site in scratch.parents:
            raise ValueError("Package output must be outside site")
    if retain_manifest is None:
        default = ROOT / "releases/inventory.json"
        if default.exists() or default.is_symlink():
            retain_manifest = default
    site.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".homefx-site-", dir=str(site.parent)) as temporary:
        temporary = Path(temporary)
        staged = temporary / "site"
        staged.mkdir()
        archive = build(output=package_output if package_output is not None else temporary / "package")
        version = validate()
        repo = repository.build(staged / "repository", retain_manifest=retain_manifest,
                                channel="preview")
        verified = verify_repository.verify(repo, channel="preview")
        bootstrap = "repository.homefx-" + verified["current"]["repository.homefx"] + ".zip"
        repo_archive = repo / "repository.homefx" / bootstrap
        video_archive = repo / "plugin.video.homefx" / archive.name
        if (archive.read_bytes() != video_archive.read_bytes()
                or archive.with_suffix(".zip.sha256").read_bytes()
                != video_archive.with_suffix(".zip.sha256").read_bytes()):
            raise ValueError("Video package differs from repository")
        for source in (video_archive, repo_archive):
            shutil.copyfile(source, staged / source.name)
            shutil.copyfile(source.with_suffix(".zip.sha256"), staged / (source.name + ".sha256"))
        shutil.copyfile(ROOT / "LICENSE", staged / "LICENSE.txt")
        digest = archive.with_suffix(".zip.sha256").read_text().split()[0]
        (staged / "index.html").write_text(_page(version, archive.name, bootstrap, digest), encoding="utf-8")
        (staged / "install.html").write_text(guide_page.build(ROOT / "docs/install.md"), encoding="utf-8")
        if site.exists():
            if _tree_bytes(site) != _tree_bytes(staged):
                raise ValueError("Site output differs; use a fresh output directory")
        else:
            os.rename(str(staged), str(site))
    return site


if __name__ == "__main__":
    print(build_site())
