"""Safety checks for the synthetic local demo state file."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons/plugin.video.homefx"
import sys
sys.path.insert(0, str(ADDON))
from resources.lib import state


class DemoStateSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "demo.json"

    def assert_default(self, value):
        self.assertEqual(value, {"watched": {}, "selected": list(state.LISTS),
                                 "saved_movies": []})

    def test_valid_atomic_round_trip_and_oversize_recovery(self):
        data = {"watched": {}, "selected": [], "saved_movies": []}
        state.save(self.path, data)
        self.assertEqual(state.load(self.path), data)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(list(self.root.glob("demo-*")), [])

        self.path.write_bytes(b" " * (state.MAX_STATE_BYTES + 1))
        self.assert_default(state.load(self.path))
        state.save(self.path, data)
        self.assertEqual(state.load(self.path), data)

    def test_missing_and_malformed_state_return_default(self):
        self.assert_default(state.load(self.path))
        self.path.write_text("{")
        self.assert_default(state.load(self.path))

    def test_load_rejects_symlink_and_hardlink(self):
        source = self.root / "source.json"
        source.write_text(json.dumps({"watched": {}, "selected": [], "saved_movies": []}))
        link = self.root / "link.json"
        link.symlink_to(source)
        self.assert_default(state.load(link))

        hardlink = self.root / "hardlink.json"
        os.link(source, hardlink)
        self.assert_default(state.load(hardlink))

    def test_load_rejects_fifo_without_blocking(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is unavailable")
        os.mkfifo(self.path)
        self.assert_default(state.load(self.path))

    def test_load_rejects_symlinked_parent(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "demo.json").write_text("{}")
        alias = self.root / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        self.assert_default(state.load(alias / "demo.json"))

    def test_save_refuses_unsafe_targets_without_touching_them(self):
        outside = self.root / "outside.json"
        outside.write_text("sentinel")
        symlink = self.root / "symlink.json"
        symlink.symlink_to(outside)
        hardlink = self.root / "hardlink.json"
        os.link(outside, hardlink)
        directory = self.root / "directory"
        directory.mkdir()

        for path in (symlink, hardlink, directory):
            with self.subTest(path=path.name):
                with self.assertRaises(OSError) as caught:
                    state.save(path, {"watched": {}, "selected": [], "saved_movies": []})
                self.assertEqual(str(caught.exception), "Unable to save demo state")

        self.assertEqual(outside.read_text(), "sentinel")
        self.assertEqual(list(self.root.glob("demo-*")), [])

    def test_save_refuses_symlinked_parent_without_chmod_or_outside_write(self):
        outside = self.root / "outside"
        outside.mkdir(mode=0o711)
        before_mode = stat.S_IMODE(outside.stat().st_mode)
        alias = self.root / "alias"
        alias.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            state.save(alias / "demo.json", {"watched": {}, "selected": [], "saved_movies": []})
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), before_mode)
        self.assertFalse((outside / "demo.json").exists())
        self.assertEqual(list(outside.iterdir()), [])

    def test_save_refuses_fifo_target(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO creation is unavailable")
        os.mkfifo(self.path)
        with self.assertRaises(OSError):
            state.save(self.path, {"watched": {}, "selected": [], "saved_movies": []})

    def test_failed_replace_preserves_old_file_and_cleans_temp(self):
        old = b'{"old": true}'
        self.path.write_bytes(old)
        with patch.object(state.os, "replace", side_effect=OSError("secret/path")):
            with self.assertRaises(OSError) as caught:
                state.save(self.path, {"watched": {}, "selected": [], "saved_movies": []})
        self.assertEqual(str(caught.exception), "Unable to save demo state")
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(list(self.root.glob("demo-*")), [])


if __name__ == "__main__":
    unittest.main()
