"""The quality gate must detect broken code and unavailable tooling."""

import importlib.metadata
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import check_quality


def has_pinned_ruff():
    try:
        return importlib.metadata.version("ruff") == check_quality.RUFF_VERSION
    except importlib.metadata.PackageNotFoundError:
        return False


class QualityFailureTests(unittest.TestCase):
    def test_missing_tool_fails(self):
        with mock.patch.object(check_quality.importlib.metadata, "version",
                               side_effect=importlib.metadata.PackageNotFoundError):
            self.assertEqual(check_quality.check(), 2)

    def test_wrong_version_fails(self):
        with mock.patch.object(check_quality.importlib.metadata, "version", return_value="0.0.0"):
            self.assertEqual(check_quality.check(), 2)

    def test_timeout_fails(self):
        with mock.patch.object(check_quality.importlib.metadata, "version",
                               return_value=check_quality.RUFF_VERSION), \
             mock.patch.object(check_quality.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("ruff", 120)):
            self.assertEqual(check_quality.check(), 2)


@unittest.skipUnless(has_pinned_ruff(), "Install quality-requirements.txt for actual lint checks")
class QualityIntegrationTests(unittest.TestCase):
    def test_undefined_name_is_rejected_and_fix_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "addons").mkdir()
            (root / "tools").mkdir()
            source = root / "addons" / "example.py"
            source.write_text("print(undefined_name)\n", encoding="utf-8")
            self.assertEqual(check_quality.check(root), 1)
            source.write_text("print('defined')\n", encoding="utf-8")
            self.assertEqual(check_quality.check(root), 0)
            self.assertEqual(source.read_text(encoding="utf-8"), "print('defined')\n")


if __name__ == "__main__":
    unittest.main()
