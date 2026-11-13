"""Offline inventory grammar, consistency and output failure boundaries."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import check_dependencies as dependencies


HASH_A = "a" * 64
HASH_B = "b" * 64


def requirement(name="example", version="1.2.3", hashes=(HASH_A,)):
    return name + "==" + version + " " + " ".join(
        "--hash=sha256:" + value for value in hashes) + "\n"


class RequirementGrammarTests(unittest.TestCase):
    def test_normalizes_names_sorts_hashes_and_packages(self):
        source = requirement("Zed_pkg", hashes=(HASH_B, HASH_A)) + requirement("Alpha.Pkg")
        self.assertEqual(dependencies.parse_inventory(source), [
            {"name": "alpha-pkg", "version": "1.2.3", "hashes": [HASH_A]},
            {"name": "zed-pkg", "version": "1.2.3", "hashes": [HASH_A, HASH_B]},
        ])

    def test_explicit_continuations_and_crlf_are_supported(self):
        source = "# inventory\r\n\r\nExample==1.2 \\\r\n\t--hash=sha256:" + HASH_A + "\r\n"
        self.assertEqual(dependencies.parse_inventory(source), [
            {"name": "example", "version": "1.2", "hashes": [HASH_A]},
        ])

    def test_comments_and_empty_inventory_are_valid(self):
        self.assertEqual(dependencies.parse_inventory("\n# No runtime dependencies\n"), [])

    def test_unsupported_requirement_forms_are_rejected(self):
        forms = [
            "example", "example>=1", "example~=1.2", "example===1", "example==1.*",
            "example==1.0rc1", "example==1!2", "example==1.0+local", "example==1.0.post1",
            "example[extra]==1", "example @ https://example.invalid/a.whl",
            "git+https://example.invalid/repository", "./local", "/absolute/package.whl",
            "file:///local/package.whl", "-e .", "-r other.txt", "-c other.txt",
            "--index-url=https://example.invalid", "--require-hashes", "--trusted-host=host",
            "_example==1", "example-==1", "example == 1", "example==1;python_version<'4'",
        ]
        for form in forms:
            with self.subTest(form=form), self.assertRaises(dependencies.DependencyError):
                dependencies.parse_inventory(form + " --hash=sha256:" + HASH_A + "\n")

    def test_missing_malformed_hashes_markers_comments_and_options_are_rejected(self):
        suffixes = [
            "", "--hash=md5:" + "a" * 32, "--hash=sha256:" + "a" * 63,
            "--hash=sha256:" + "a" * 65, "--hash=sha256:" + "g" * 64,
            "--hash=sha256:" + "A" * 64, "--hash sha256:" + HASH_A,
            "--hash=sha256:" + HASH_A + " ; python_version < '4'",
            "--hash=sha256:" + HASH_A + " # inline comment",
            "--hash=sha256:" + HASH_A + " --no-deps",
        ]
        for suffix in suffixes:
            with self.subTest(suffix=suffix), self.assertRaises(dependencies.DependencyError):
                dependencies.parse_inventory("example==1 " + suffix + "\n")

    def test_duplicate_normalized_names_and_duplicate_hashes_are_rejected(self):
        for source in (
            requirement("Example_pkg") + requirement("example-pkg"),
            requirement("example.pkg") + requirement("EXAMPLE__pkg", version="2"),
            requirement(hashes=(HASH_A, HASH_A)),
        ):
            with self.subTest(source=source), self.assertRaises(dependencies.DependencyError):
                dependencies.parse_inventory(source)

    def test_dangling_continuations_and_comment_interruptions_are_rejected(self):
        for suffix in ("", "\n", "\n# comment\n", "\n\n--hash=sha256:" + HASH_A):
            with self.subTest(suffix=suffix), self.assertRaises(dependencies.DependencyError):
                dependencies.parse_inventory("example==1 \\" + suffix)

    def test_hash_without_continuation_cannot_form_another_declaration(self):
        with self.assertRaises(dependencies.DependencyError):
            dependencies.parse_inventory("example==1\n--hash=sha256:" + HASH_A + "\n")

    def test_non_ascii_and_hidden_control_characters_are_rejected(self):
        for character in ("\x00", "\x1b", "\v", "\f", "\r", "\u00a0", "\u2028", "é"):
            with self.subTest(character=repr(character)), self.assertRaises(dependencies.DependencyError):
                dependencies.parse_inventory(requirement().replace(" ", character, 1))
        with self.assertRaises(dependencies.DependencyError):
            dependencies.parse_inventory(requirement().rstrip("\n") + "\r")

    def test_byte_line_declaration_package_and_hash_bounds(self):
        cases = [
            ("MAX_BYTES", 4, "# a long comment\n"),
            ("MAX_LINE", 4, "# a long comment\n"),
            ("MAX_DECLARATION", 20, requirement()),
            ("MAX_PACKAGES", 1, requirement("one") + requirement("two")),
            ("MAX_HASHES", 1, requirement(hashes=(HASH_A, HASH_B))),
        ]
        for constant, value, source in cases:
            with self.subTest(constant=constant), mock.patch.object(dependencies, constant, value):
                with self.assertRaisesRegex(dependencies.DependencyError, "exceeds bounds"):
                    dependencies.parse_inventory(source)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "tools").mkdir()
        for name in dependencies.INVENTORIES:
            content = "# empty runtime\n" if name == "requirements.txt" else requirement()
            (self.root / name).write_text(content, encoding="utf-8")

    def write(self, inventory, content):
        (self.root / inventory).write_text(content, encoding="utf-8")

    def test_empty_runtime_and_populated_tool_inventories_are_valid(self):
        result = dependencies.check(self.root)
        self.assertEqual(result["inventories"], [
            {"path": path, "packages": 0 if path == "requirements.txt" else 1}
            for path in dependencies.INVENTORIES])

    def test_each_empty_tool_inventory_fails(self):
        for name in dependencies.INVENTORIES[1:]:
            self.write(name, "# truncated inventory\n")
            with self.subTest(name=name), self.assertRaisesRegex(
                    dependencies.DependencyError, "tool inventory is empty"):
                dependencies.check(self.root)
            self.write(name, requirement())

    def test_shared_names_have_one_sorted_record_with_inventory_membership(self):
        self.write("tools/build-requirements.txt", requirement("Shared.Pkg", hashes=(HASH_B, HASH_A)))
        self.write("tools/security-requirements.txt", requirement("shared_pkg", hashes=(HASH_A, HASH_B)))
        self.write("tools/quality-requirements.txt", requirement("Alpha"))
        manifest = dependencies.check(self.root)
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["packages"], [
            {"name": "alpha", "version": "1.2.3", "hashes": [HASH_A],
             "inventories": ["tools/quality-requirements.txt"]},
            {"name": "shared-pkg", "version": "1.2.3", "hashes": [HASH_A, HASH_B],
             "inventories": ["tools/build-requirements.txt", "tools/security-requirements.txt"]},
        ])

    def test_cross_inventory_conflicting_versions_and_hashes_fail(self):
        self.write("tools/build-requirements.txt", requirement("shared_pkg"))
        for other, category in (
            (requirement("Shared-Pkg", "2"), "conflicting inventory versions"),
            (requirement("Shared-Pkg", "1.2.3.0"), "conflicting inventory versions"),
            (requirement("Shared.Pkg", hashes=(HASH_B,)), "conflicting inventory hashes"),
        ):
            self.write("tools/security-requirements.txt", other)
            with self.subTest(category=category), self.assertRaisesRegex(
                    dependencies.DependencyError, category):
                dependencies.check(self.root)

    def test_each_missing_inventory_fails_instead_of_disappearing(self):
        for name in dependencies.INVENTORIES:
            path = self.root / name
            path.unlink()
            with self.subTest(name=name), self.assertRaises(dependencies.DependencyError):
                dependencies.check(self.root)
            path.write_text(requirement(), encoding="utf-8")

    def test_invalid_encoding_directory_and_oversized_input_fail(self):
        path = self.root / "requirements.txt"
        path.write_bytes(b"\xff")
        with self.assertRaises(dependencies.DependencyError):
            dependencies.check(self.root)
        path.write_bytes(b"#" * (dependencies.MAX_BYTES + 1))
        with self.assertRaises(dependencies.DependencyError):
            dependencies.check(self.root)
        path.unlink()
        path.mkdir()
        with self.assertRaises(dependencies.DependencyError):
            dependencies.check(self.root)

    def test_input_file_and_parent_symlinks_are_rejected(self):
        path = self.root / "requirements.txt"
        path.unlink()
        path.symlink_to(self.root / "tools/build-requirements.txt")
        with self.assertRaisesRegex(dependencies.DependencyError, "symlink"):
            dependencies.check(self.root)
        path.unlink()
        path.write_text("", encoding="utf-8")
        (self.root / "tools").rename(self.root / "actual-tools")
        (self.root / "tools").symlink_to(self.root / "actual-tools", target_is_directory=True)
        with self.assertRaisesRegex(dependencies.DependencyError, "symlink"):
            dependencies.check(self.root)

    def test_manifest_bytes_are_deterministic_and_do_not_expose_local_paths(self):
        self.write("tools/build-requirements.txt", requirement("Example.Pkg"))
        first = self.root / "out/one.json"
        second = self.root / "out/two.json"
        dependencies.write_manifest(first, dependencies.check(self.root))
        dependencies.write_manifest(second, dependencies.check(self.root))
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(json.loads(first.read_text()), dependencies.check(self.root))
        self.assertNotIn(str(self.root), first.read_text())

    def test_output_never_overwrites_existing_files_or_follows_symlinks(self):
        source = self.root / "requirements.txt"
        before = source.read_bytes()
        with self.assertRaises(dependencies.DependencyError):
            dependencies.write_manifest(source, {})
        self.assertEqual(source.read_bytes(), before)
        link = self.root / "linked"
        link.symlink_to(self.root / "tools", target_is_directory=True)
        with self.assertRaisesRegex(dependencies.DependencyError, "symlink"):
            dependencies.write_manifest(link / "new.json", {})
        self.assertFalse((self.root / "tools/new.json").exists())

    def test_cli_failure_uses_fixed_category_and_does_not_write_output(self):
        output = self.root / "result.json"
        self.write("requirements.txt", "https://private.invalid/synthetic-token\n")
        stderr = io.StringIO()
        original_check = dependencies.check
        with mock.patch.object(dependencies, "check", side_effect=lambda: original_check(self.root)), \
                contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            dependencies.main(["--output", str(output)])
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(stderr.getvalue(), "Dependency inventory check failed: invalid requirement pin\n")
        self.assertFalse(output.exists())

    def test_cli_success_can_write_a_fresh_manifest(self):
        output = self.root / "result.json"
        result = dependencies.check(self.root)
        stdout = io.StringIO()
        with mock.patch.object(dependencies, "check", return_value=result), \
                contextlib.redirect_stdout(stdout):
            self.assertEqual(dependencies.main(["--output", str(output)]), 0)
        self.assertEqual(json.loads(output.read_text()), result)
        self.assertEqual(stdout.getvalue(),
                         "Validated 4 Python inventories and 1 normalized packages (offline).\n")

    def test_checked_in_inventory_is_supported_without_modification(self):
        result = dependencies.check()
        self.assertEqual(result["inventories"][0], {"path": "requirements.txt", "packages": 0})
        self.assertTrue(result["packages"])


if __name__ == "__main__":
    unittest.main()
