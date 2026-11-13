"""Compare the public preview with a verified, quiescent local site artifact.

Run explicitly after publication from the same build artifact. HTTP integrity does
not establish Kodi installation, updates, navigation or playback. No retries are
made: propagation failures require investigation before manually rerunning.
"""
import argparse
from pathlib import Path
import time
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
    """A fixed diagnostic that never includes response bodies or request errors."""


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
    roots = {"index.html", "install.html", "LICENSE.txt"}
    development_archive = development_download.verify(files)
    if development_archive is not None:
        roots.update({development_archive, development_archive + ".sha256"})
        link = ('<a href="' + development_archive + '">' + development_archive + '</a>').encode("ascii")
        _require(link in files.get("index.html", b""), "local Development download link")
    else:
        _require(('href="' + development_download.PREFIX).encode("ascii")
                 not in files.get("index.html", b""), "missing local Development download")
    for ident, version in result["current"].items():
        name = ident + "-" + version + ".zip"
        for suffix in ("", ".sha256"):
            target = name + suffix
            roots.add(target)
            _require(files.get(target) == files.get("repository/" + ident + "/" + target),
                     "local download mismatch")
    _require({name for name in files if not name.startswith("repository/")} == roots,
             "local site topology")
    _require(all(name == "repository" or name.startswith("repository/") for name in directories),
             "local site topology")
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
        except Exception:
            raise PublishedCheckError("published request failed") from None
        _require(time.monotonic() <= deadline, "published check budget exceeded")
        _require(type(actual) is bytes and actual == expected, "published content mismatch")
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
