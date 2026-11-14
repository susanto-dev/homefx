"""Hosted verification exercises injected transports, never external networking."""
from pathlib import Path
import shutil
import sys
import ssl
from urllib.error import HTTPError, URLError
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_published as published
import repository
import build_site


class PublishedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name) / "site"
        repo = repository.build(self.site / "repository", channel="preview")
        result = published.verify_repository.verify(repo, channel="preview")
        for ident, version in result["current"].items():
            name = ident + "-" + version + ".zip"
            for suffix in ("", ".sha256"):
                shutil.copyfile(repo / ident / (name + suffix), self.site / (name + suffix))
        (self.site / "LICENSE.txt").write_bytes((ROOT / "LICENSE").read_bytes())
        (self.site / 'index.html').write_text('<a href="advanced/">advanced/</a>')
        advanced = self.site / 'advanced'
        advanced.mkdir()
        video = 'plugin.video.homefx-' + result['current']['plugin.video.homefx'] + '.zip'
        for suffix in ('', '.sha256'):
            shutil.copyfile(self.site / (video + suffix), advanced / (video + suffix))
        (advanced / 'index.html').write_text(build_site._advanced_page(video))
        (self.site / "install.html").write_text("<!doctype html><title>HomeFX installation guide</title>")
        self.files, _ = published.verify_repository._snapshot(self.site)
        self.requests = []

    def fetch(self, url, limit, timeout):
        self.requests.append((url, limit, timeout))
        self.assertTrue(url.startswith(published.BASE_URL))
        name = url[len(published.BASE_URL):]
        self.assertEqual(limit, len(self.files[name]) + 1)
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, 10)
        return self.files[name]

    def test_all_files_exactly_once_and_input_unchanged(self):
        result = published.check(self.site, fetch=self.fetch)
        self.assertEqual(result, {"files": len(self.files), "bytes": sum(map(len, self.files.values()))})
        self.assertEqual(len(self.requests), len(self.files))
        self.assertEqual(len({url for url, _, _ in self.requests}), len(self.files))
        self.assertEqual(published.verify_repository._snapshot(self.site)[0], self.files)

    def test_remote_missing_corrupt_oversize_or_wrong_type_fails(self):
        for returned in (b"", b"corrupt", b"x" * 10000, "not bytes", None):
            with self.subTest(returned=type(returned).__name__):
                with self.assertRaisesRegex(published.PublishedCheckError, "published content mismatch"):
                    published.check(self.site, fetch=lambda *args: returned)

    def test_corrupt_hosted_index_checksum_archive_or_notice_fails(self):
        targets = ["repository/addons.xml", "repository/addons.xml.sha256",
                   "repository/CHANNEL.txt", "index.html", "install.html"]
        targets.extend(name for name in self.files if name.startswith("repository/") and name.endswith(".zip"))
        for target in targets:
            with self.subTest(target=target):
                def fetch(url, limit, timeout):
                    data = self.fetch(url, limit, timeout)
                    return data + b"!" if url == published.BASE_URL + target else data
                with self.assertRaisesRegex(published.PublishedCheckError, "published content mismatch"):
                    published.check(self.site, fetch=fetch)

    def test_local_topology_rejected_before_network(self):
        for name in ("private-token.txt", "repository/extra", "CANDIDATE.txt"):
            target = self.site / name
            target.write_text("private")
            fetch = Mock()
            with self.assertRaisesRegex(published.PublishedCheckError, "local site verification failed"):
                published.check(self.site, fetch=fetch)
            fetch.assert_not_called()
            target.unlink()

    def test_advanced_copy_corruption_or_missing_folder_fails_before_fetch(self):
        paths = [self.site / 'advanced/index.html', *self.site.glob('advanced/*.zip')]
        for target in paths:
            original = target.read_bytes()
            for replacement in (None, b'changed'):
                if replacement is None:
                    target.unlink()
                else:
                    target.write_bytes(replacement)
                fetch = Mock()
                with self.assertRaises(published.PublishedCheckError):
                    published.check(self.site, fetch=fetch)
                fetch.assert_not_called()
                target.write_bytes(original)

    def test_missing_empty_or_oversized_guide_fails_before_network(self):
        target = self.site / 'install.html'
        for data in (None, b'', b'x' * (published.guide_page.MAX_PAGE_BYTES + 1)):
            with self.subTest(mutation='missing' if data is None else len(data)):
                if data is None:
                    target.unlink()
                else:
                    target.write_bytes(data)
                fetch = Mock()
                with self.assertRaises(published.PublishedCheckError):
                    published.check(self.site, fetch=fetch)
                fetch.assert_not_called()
                target.write_bytes(self.files['install.html'])

    def test_root_bootstrap_and_checksum_must_match_verified_repository(self):
        for name in self.files:
            if "/" in name or not (name.endswith(".zip") or name.endswith(".sha256")):
                continue
            with self.subTest(name=name):
                (self.site / name).write_bytes(b"wrong")
                fetch = Mock()
                with self.assertRaises(published.PublishedCheckError):
                    published.check(self.site, fetch=fetch)
                fetch.assert_not_called()
                (self.site / name).write_bytes(self.files[name])

    def test_symlink_and_candidate_channel_rejected(self):
        page = self.site / "index.html"
        page.unlink()
        page.symlink_to(ROOT / "README.md")
        with self.assertRaises(published.PublishedCheckError):
            published.check(self.site, fetch=Mock())
        page.unlink()
        page.write_bytes(self.files["index.html"])
        (self.site / "repository/CHANNEL.txt").rename(self.site / "repository/CANDIDATE.txt")
        with self.assertRaises(published.PublishedCheckError):
            published.check(self.site, fetch=Mock())

    def test_remote_errors_redacted_and_not_retried(self):
        fetch = Mock(side_effect=OSError("secret body https://private.invalid/token"))
        with self.assertRaises(published.PublishedCheckError) as raised:
            published.check(self.site, fetch=fetch)
        self.assertEqual(str(raised.exception), "published request failed; file: LICENSE.txt; "
                         "category: request_unavailable; HTTP status: unavailable")
        self.assertTrue(raised.exception.__suppress_context__)
        fetch.assert_called_once()

    def test_request_diagnostics_identify_public_file_without_private_error_details(self):
        cases = (
            (HTTPError("https://private.invalid/token", 503, "SECRET", {"Authorization": "SECRET"}, None),
             "http_status", "503"),
            (HTTPError("SECRET", "SECRET", "SECRET", {}, None), "http_status", "unavailable"),
            (URLError(TimeoutError("SECRET")), "timeout", "unavailable"),
            (URLError(ssl.SSLCertVerificationError("SECRET")), "certificate_verification", "unavailable"),
            (ssl.SSLError("SECRET"), "tls_error", "unavailable"),
            (published.PublishedCheckError("published redirect rejected"), "redirect_rejected", "unavailable"),
            (published.PublishedCheckError("published response rejected"), "response_rejected", "unavailable"),
        )
        for error, category, status in cases:
            self.requests.clear()
            def fail_later(url, limit, timeout):
                if url == published.BASE_URL + 'index.html':
                    raise error
                return self.fetch(url, limit, timeout)
            fetch = Mock(side_effect=fail_later)
            with self.assertRaises(published.PublishedCheckError) as result:
                published.check(self.site, fetch=fetch)
            self.assertEqual(str(result.exception), "published request failed; file: index.html; category: "
                             + category + "; HTTP status: " + status)
            self.assertEqual(fetch.call_count, sorted(self.files).index('index.html') + 1)
            self.assertTrue(result.exception.__suppress_context__)

    def test_mismatch_identifies_file_without_printing_received_bytes(self):
        def mismatch(url, limit, timeout):
            if url == published.BASE_URL + 'index.html':
                return b'SECRET private response'
            return self.fetch(url, limit, timeout)
        with self.assertRaises(published.PublishedCheckError) as result:
            published.check(self.site, fetch=mismatch)
        self.assertEqual(str(result.exception), 'published content mismatch; file: index.html')

    def test_diagnostic_path_fallback_rejects_control_absolute_and_traversal_names(self):
        for name in ('../SECRET', '/SECRET', 'SECRET\nheader', 'https://SECRET', 'a' * 241, None):
            self.assertEqual(published._public_name(name), 'unavailable')

    def test_budget_checked_before_and_after_fetch(self):
        for times, calls in (([0, 301], 0), ([0, 1, 301], 1)):
            fetch = Mock(side_effect=self.fetch)
            with patch.object(published.time, "monotonic", side_effect=times):
                with self.assertRaisesRegex(published.PublishedCheckError, "budget exceeded"):
                    published.check(self.site, fetch=fetch)
            self.assertEqual(fetch.call_count, calls)

    def test_http_transport_bounds_reads_and_rejects_status_or_redirect(self):
        response = Mock(status=200)
        response.geturl.return_value = published.BASE_URL + "index.html"
        response.read.return_value = b"data"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(published, "build_opener", return_value=opener) as factory:
            self.assertEqual(published._fetch(response.geturl(), 5, 3), b"data")
            response.read.assert_called_once_with(5)
            self.assertEqual(opener.open.call_args.kwargs["timeout"], 3)
            self.assertIsInstance(factory.call_args.args[0], published._NoRedirect)
            response.status = 404
            with self.assertRaises(published.PublishedCheckError):
                published._fetch(response.geturl(), 5, 3)
            response.status = 200
            response.geturl.return_value = "https://other.invalid/"
            with self.assertRaises(published.PublishedCheckError):
                published._fetch(published.BASE_URL, 5, 3)
        with self.assertRaises(published.PublishedCheckError):
            published._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid/")


if __name__ == "__main__":
    unittest.main()
