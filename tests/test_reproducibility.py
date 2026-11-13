"""Isolated release builds and deliberately inconsistent outputs; no network."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_reproducibility as checker


class ReproducibilityTests(unittest.TestCase):
    def test_real_builds_match_and_all_package_outputs_are_temporary(self):
        original = checker.package.build
        outputs = []

        def build(source=checker.package.ADDON, output=None):
            self.assertIsNotNone(output)
            output = Path(output)
            self.assertNotEqual(output, checker.package.ROOT / "dist")
            outputs.append(output)
            return original(source, output)

        with patch.object(checker.build_site, "build", side_effect=build), \
                patch.object(checker.repository.package, "build", side_effect=build), \
                patch.object(checker.verify_repository, "verify",
                             wraps=checker.verify_repository.verify) as verify:
            result = checker.check()
        self.assertEqual(verify.call_count, 6)
        self.assertGreater(result["site_files"], result["repository_files"])
        inventory = checker.package.ROOT / "releases" / "inventory.json"
        identities = {(row["id"], row["version"]) for row in
                      json.loads(inventory.read_text())["packages"]} if inventory.exists() else set()
        identities.add(("plugin.video.homefx", checker.package.validate()))
        identities.add(("repository.homefx", checker.repository._repository_manifest(checker.repository.REPOSITORY)[1]))
        self.assertEqual(result["packages"], len(identities))
        self.assertGreater(result["repository_files"], 4)
        self.assertEqual(len(outputs), 6)
        self.assertTrue(all(not path.exists() for path in outputs))

    def test_nondeterministic_site_bytes_are_rejected_and_cleaned(self):
        original = checker.build_site.build_site
        outputs = []

        def build(output, package_output=None, retain_manifest=None):
            site = original(output, package_output=package_output, retain_manifest=retain_manifest)
            outputs.append(site)
            with (site / "index.html").open("ab") as stream:
                stream.write(str(len(outputs)).encode("ascii"))
            return site

        with patch.object(checker.build_site, "build_site", side_effect=build):
            with self.assertRaisesRegex(checker.ReproducibilityError, "^build outputs differ$"):
                checker.check()
        self.assertEqual(len(outputs), 2)
        self.assertTrue(all(not path.exists() for path in outputs))

    def test_consistently_corrupt_candidate_is_verified_not_just_compared(self):
        original = checker.repository.build
        outputs = []

        def build(output, **kwargs):
            candidate = original(output, **kwargs)
            outputs.append(candidate)
            (candidate / "addons.xml.sha256").write_text("bad")
            return candidate

        with patch.object(checker.repository, "build", side_effect=build):
            with self.assertRaisesRegex(checker.ReproducibilityError, "^build or verification failed$"):
                checker.check()
        self.assertTrue(all(not path.exists() for path in outputs))

    def test_extra_preview_files_are_rejected_even_if_repeated(self):
        original = checker.build_site.build_site

        def build(output, package_output=None, retain_manifest=None):
            site = original(output, package_output=package_output, retain_manifest=retain_manifest)
            (site / "unreviewed.txt").write_text("synthetic")
            return site

        with patch.object(checker.build_site, "build_site", side_effect=build):
            with self.assertRaisesRegex(checker.ReproducibilityError, "^invalid preview output$"):
                checker.check()

    def test_missing_required_guide_is_rejected_even_if_repeated(self):
        original = checker.build_site.build_site

        def build(output, **kwargs):
            site = original(output, **kwargs)
            (site / 'install.html').unlink()
            return site

        with patch.object(checker.build_site, 'build_site', side_effect=build):
            with self.assertRaisesRegex(checker.ReproducibilityError, '^invalid preview output$'):
                checker.check()

    def test_bootstrap_mismatch_is_rejected_even_if_repeated(self):
        original = checker.build_site.build_site

        def build(output, **kwargs):
            site = original(output, **kwargs)
            bootstrap = next(site.glob("repository.homefx-*.zip"))
            bootstrap.write_bytes(b"not the indexed package")
            return site

        with patch.object(checker.build_site, "build_site", side_effect=build):
            with self.assertRaisesRegex(checker.ReproducibilityError, "^inconsistent preview output$"):
                checker.check()

    def test_cli_failure_is_nonzero_and_redacted(self):
        output, error = io.StringIO(), io.StringIO()
        with patch.object(checker, "_build", side_effect=OSError("/private/path synthetic token")), \
                patch.object(sys, "argv", ["check_reproducibility.py"]), \
                redirect_stdout(output), redirect_stderr(error):
            with self.assertRaises(SystemExit) as failure:
                checker.main()
        self.assertEqual(failure.exception.code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "Reproducibility check failed: build or verification failed\n")
