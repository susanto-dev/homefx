"""Compare the public preview with a verified, quiescent local site artifact.

Run explicitly after publication from the same build artifact. HTTP integrity does
not establish Kodi installation, updates, navigation or playback. No retries are
made: propagation failures require investigation before manually rerunning.
"""
import argparse
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

import package
import guide_page
import verify_repository
import development_download

BASE_URL = "https://susanto-dev.github.io/homefx/"
REQUEST_TIMEOUT = 10
TOTAL_TIMEOUT = 300


class PublishedCheckError(ValueError):
    """Fixed categories and verified public paths, never response bodies or raw errors."""


def _public_name(name):
    # Names reach this boundary only after complete local artifact validation.
    # Keep diagnostics bounded even if a future caller changes that contract.
    if (type(name) is str and re.fullmatch(r"[A-Za-z0-9_./-]{1,240}", name)
            and not name.startswith("/") and ".." not in name.split("/")):
        return name
    return "unavailable"


def _request_diagnostic(name, error):
    category, status = "request_unavailable", "unavailable"
    if isinstance(error, HTTPError):
        category = "http_status"
        if type(error.code) is int and 100 <= error.code <= 599:
            status = str(error.code)
    else:
        reason = error.reason if isinstance(error, URLError) else error
        if isinstance(reason, TimeoutError):
            category = "timeout"
        elif isinstance(reason, ssl.SSLCertVerificationError):
            category = "certificate_verification"
        elif isinstance(reason, ssl.SSLError):
            category = "tls_error"
        elif (isinstance(error, PublishedCheckError) and error.args
              and error.args[0] == "published redirect rejected"):
            category = "redirect_rejected"
        elif (isinstance(error, PublishedCheckError) and error.args
              and error.args[0] == "published response rejected"):
            category = "response_rejected"
    return ("published request failed; file: " + _public_name(name)
            + "; category: " + category + "; HTTP status: " + status)


def _require(condition, message):
    if not condition:
        raise PublishedCheckError(message)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PublishedCheckError("published redirect rejected")


def _fetch(url, limit, timeout):
    # Default HTTPS certificate validation and environment proxy support are kept.
    # Only check() supplies URLs, from its fixed origin and validated file names.
    opener = build_opener(_NoRedirect())
    with opener.open(Request(url), timeout=timeout) as response:
        _require(response.status == 200, "published response rejected")
        _require(response.geturl() == url, "published redirect rejected")
        return response.read(limit)


def _expected(site):
    result = verify_repository.verify(Path(site) / "repository", channel="preview")
    files, directories = verify_repository._snapshot(site)
    roots = {'index.html', 'install.html', 'LICENSE.txt', 'advanced/index.html'}
    current_video = 'plugin.video.homefx-' + result['current']['plugin.video.homefx'] + '.zip'
    advanced_names = {current_video}
    for video, prefix in ((False, development_download.PREFIX),
                          (True, development_download.builder.VIDEO_ID + '-')):
        development_archive = development_download.verify(files, video=video)
        page = 'index.html' if video else 'advanced/index.html'
        if development_archive is not None:
            roots.update({development_archive, development_archive + '.sha256'})
            link = ('<a href="' + development_archive + '">' + development_archive + '</a>').encode('ascii')
            _require(link in files.get(page, b''), 'local Development download link')
            if not video:
                advanced_names.add(development_archive)
                _require(('href="' + development_archive + '"').encode('ascii') not in files['index.html'],
                         'diagnostic download on main page')
        else:
            _require(('href="' + prefix).encode('ascii') not in files.get(page, b''),
                     'missing local Development download')
    # Every validated indexed package keeps an identical root URL, including old versions.
    for name, data in files.items():
        parts = name.split('/')
        if len(parts) == 3 and parts[0] == 'repository' and name.endswith(('.zip', '.zip.sha256')):
            roots.add(parts[-1])
            _require(files.get(parts[-1]) == data, 'local download mismatch')
    for name in advanced_names:
        for suffix in ('', '.sha256'):
            target = 'advanced/' + name + suffix
            roots.add(target)
            _require(files.get(target) == files.get(name + suffix), 'advanced download mismatch')
        _require(('<a href="' + name + '">' + name + '</a>').encode('ascii')
                 in files.get('advanced/index.html', b''), 'advanced download link')
    _require(b'<a href="advanced/">advanced/</a>' in files['index.html'], 'advanced folder link')
    _require(('href="' + current_video + '"').encode('ascii') not in files['index.html'],
             'manual download on main page')
    _require({name for name in files if not name.startswith('repository/')} == roots, 'local site topology')
    _require(all(name in {'repository', 'advanced'} or name.startswith('repository/') for name in directories),
             'local site topology')
    _require(0 < len(files['advanced/index.html']) <= guide_page.MAX_PAGE_BYTES, 'advanced page bounds')
    _require(files["LICENSE.txt"] == (package.ROOT / "LICENSE").read_bytes(), "local site licence")
    _require(bool(files["index.html"]), "local site page")
    _require(0 < len(files["install.html"]) <= guide_page.MAX_PAGE_BYTES, "local guide bounds")
    return files


def check(site, fetch=None):
    """Read-only check of every expected file; injected fetch(url, limit, timeout).

    The timeout budget is checked between operations and after each fetch. Socket
    timeouts bound network operations, but operating-system DNS resolution can
    exceed them; the budget is not a hard process deadline. Unexpected hosted
    files are not enumerated. Use an immutable build artifact as the local input.
    """
    deadline = time.monotonic() + TOTAL_TIMEOUT
    try:
        files = _expected(site)
    except Exception:
        raise PublishedCheckError("local site verification failed") from None
    fetch = _fetch if fetch is None else fetch
    for name, expected in sorted(files.items()):
        remaining = deadline - time.monotonic()
        _require(remaining > 0, "published check budget exceeded")
        url = BASE_URL + quote(name, safe="/")
        try:
            actual = fetch(url, len(expected) + 1, min(REQUEST_TIMEOUT, remaining))
        except Exception as error:
            raise PublishedCheckError(_request_diagnostic(name, error)) from None
        _require(time.monotonic() <= deadline, "published check budget exceeded")
        _require(type(actual) is bytes and actual == expected, "published content mismatch; file: " + _public_name(name))
    return {"files": len(files), "bytes": sum(map(len, files.values()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.site)
    except PublishedCheckError as error:
        parser.exit(1, "Published check failed: " + str(error) + "\n")
    print("Checked {files} public files ({bytes} bytes).".format(**result))
    print("HTTP integrity checked; Kodi and device acceptance remain separate.")


if __name__ == "__main__":
    main()
