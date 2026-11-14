"""The test command must preserve failures and emit only aggregate reports."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import run_tests


def outcome_suite():
    class Outcomes(unittest.TestCase):
        def test_pass(self):
            with self.subTest(value="private passing subtest"):
                self.assertTrue(True)

        def test_failure(self):
            self.fail("private failure detail")

        def test_error(self):
            raise RuntimeError("private exception detail")

        @unittest.skip("private skip reason")
        def test_skip(self):
            pass

        @unittest.expectedFailure
        def test_expected_failure(self):
            self.fail("private expected failure")

        @unittest.expectedFailure
        def test_unexpected_success(self):
            pass

    return unittest.defaultTestLoader.loadTestsFromTestCase(Outcomes)


class TestRunnerTests(unittest.TestCase):
    def invoke(self, suite, arguments=()):
        output = io.StringIO()
        errors = io.StringIO()
        with mock.patch.object(run_tests, "discover_suite", return_value=suite), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = run_tests.main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_default_still_discovers_the_full_suite(self):
        suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
        with mock.patch.object(run_tests, "discover_suite", return_value=suite) as discover, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run_tests.main([]), 0)
        discover.assert_called_once_with("test*.py")

    def test_repeated_patterns_run_overlapping_cases_once_and_keep_failures(self):
        groups = [outcome_suite(), unittest.TestSuite([
            outcome_suite(), unittest.FunctionTestCase(lambda: None),
        ])]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "summary.json"
            with mock.patch.object(run_tests, "discover_suite", side_effect=groups) as discover, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = run_tests.main(["--pattern", "test_one.py", "--pattern", "test_*.py",
                                         "--summary", str(target)])
            report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(discover.call_args_list, [mock.call("test_one.py"), mock.call("test_*.py")])
        self.assertEqual(status, 1)
        self.assertEqual(report["run"], 7)
        self.assertEqual(report["passed"], 2)
        self.assertEqual(report["failures"], 1)
        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["unexpected_successes"], 1)

    def test_one_empty_pattern_cannot_be_hidden_by_other_selected_tests(self):
        for empty_first in (True, False):
            with self.subTest(empty_first=empty_first):
                groups = [unittest.TestSuite(), outcome_suite()]
                if not empty_first:
                    groups.reverse()
                with mock.patch.object(run_tests, "discover_suite", side_effect=groups), \
                        contextlib.redirect_stdout(io.StringIO()) as output, \
                        contextlib.redirect_stderr(io.StringIO()) as errors:
                    status = run_tests.main(["--pattern", "test_one.py", "--pattern", "missing*.py"])
                self.assertEqual(status, 1)
                self.assertIn("run=0", output.getvalue())
                self.assertIn("No tests were discovered.", errors.getvalue())

    def test_documentation_cannot_be_combined_with_patterns(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            run_tests.main(["--documentation", "--pattern", "test_model.py"])
        self.assertEqual(error.exception.code, 2)

    def test_all_outcomes_are_counted_without_private_details_in_json(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "summary.json"
            status, output, errors = self.invoke(outcome_suite(), ["--summary", str(target)])
            report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assertEqual(report, {
            "run": 6, "passed": 1, "failures": 1, "errors": 1, "skipped": 1,
            "expected_failures": 1, "unexpected_successes": 1, "success": False,
        })
        self.assertIn("run=6", output)
        self.assertIn("private exception detail", errors)
        self.assertIn("test_failure", errors)

    def test_subtest_failures_are_not_subtracted_from_run_to_count_passes(self):
        class Subtests(unittest.TestCase):
            def test_multiple_failures(self):
                for value in range(3):
                    with self.subTest(value=value):
                        self.fail("private subtest detail")

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Subtests)
        report = run_tests.summarize(run_tests.run_suite(suite, io.StringIO()))
        self.assertEqual(report["run"], 1)
        self.assertEqual(report["passed"], 0)
        self.assertEqual(report["failures"], 3)
        self.assertFalse(report["success"])

    def test_success_skip_and_expected_failure_exit_successfully(self):
        suite = outcome_suite()
        suite = unittest.TestSuite(test for test in suite if test._testMethodName in {
            "test_pass", "test_skip", "test_expected_failure",
        })
        status, output, _ = self.invoke(suite)
        self.assertEqual(status, 0)
        self.assertIn("passed=1", output)
        self.assertIn("success=True", output)

    def test_unexpected_success_alone_is_a_failure(self):
        suite = unittest.TestSuite(test for test in outcome_suite()
                                   if test._testMethodName == "test_unexpected_success")
        self.assertEqual(self.invoke(suite)[0], 1)

    def test_all_skipped_suite_is_successful_without_passed_tests(self):
        suite = unittest.TestSuite(test for test in outcome_suite()
                                   if test._testMethodName == "test_skip")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "summary.json"
            status, _, _ = self.invoke(suite, ["--summary", str(target)])
            report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(report["passed"], 0)
        self.assertEqual(report["skipped"], 1)
        self.assertTrue(report["success"])

    def test_discovery_import_error_is_reported_as_an_error(self):
        suite = unittest.TestLoader().loadTestsFromName("homefx_missing_test_module")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "summary.json"
            status, _, errors = self.invoke(suite, ["--summary", str(target)])
            report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assertEqual(report["errors"], 1)
        self.assertFalse(report["success"])
        self.assertIn("ImportError", errors)

    def test_empty_discovery_is_unsuccessful_and_writes_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "summary.json"
            status, _, errors = self.invoke(unittest.TestSuite(), ["--summary", str(target)])
            report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assertEqual(report["run"], 0)
        self.assertFalse(report["success"])
        self.assertIn("No tests were discovered.", errors)

    def test_summary_write_error_is_unsuccessful(self):
        with tempfile.TemporaryDirectory() as directory:
            suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
            status, output, errors = self.invoke(suite, ["--summary", directory])
        self.assertEqual(status, 2)
        self.assertIn("success=True", output)
        self.assertIn("Could not write test summary.", errors)

    def test_cli_pattern_uses_repository_tests_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            # This name would be discovered if the runner used its caller's cwd.
            (Path(directory) / "test_model.py").write_text(
                "raise RuntimeError('caller test must not be imported')\n", encoding="utf-8")
            target = Path(directory) / "summary.json"
            process = subprocess.run(
                [sys.executable, str(run_tests.ROOT / "tools" / "run_tests.py"),
                 "--pattern", "test_model.py", "--pattern", "test_mode*.py", "--summary", str(target)],
                cwd=directory, capture_output=True, text=True, check=False, timeout=30,
            )
            report = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report["run"], run_tests.discover_suite("test_model.py").countTestCases())
        self.assertTrue(report["success"])
        self.assertIn("test_", process.stderr)

    def test_documentation_missing_group_fails_with_empty_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'summary.json'
            groups = [unittest.TestSuite([unittest.FunctionTestCase(lambda: None)]), unittest.TestSuite()]
            with mock.patch.object(run_tests, 'discover_suite', side_effect=groups), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                status = run_tests.main(['--documentation', '--summary', str(target)])
            report = json.loads(target.read_text())
        self.assertEqual(status, 1)
        self.assertEqual(report['run'], 0)
        self.assertFalse(report['success'])

    def test_documentation_cli_runs_links_and_rendering_without_runtime_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'summary.json'
            process = subprocess.run(
                [sys.executable, str(run_tests.ROOT / 'tools/run_tests.py'),
                 '--documentation', '--summary', str(target)],
                cwd=directory, capture_output=True, text=True, check=False, timeout=30)
            report = json.loads(target.read_text())
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(report['success'])
        self.assertEqual(report['skipped'], 0)
        self.assertIn('test_documentation.', process.stderr)
        self.assertIn('test_guide_page.', process.stderr)
        self.assertNotIn('test_model.', process.stderr)
        self.assertNotIn('test_trakt_', process.stderr)


if __name__ == "__main__":
    unittest.main()
