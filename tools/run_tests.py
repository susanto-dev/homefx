"""Run repository unittest discovery with an optional aggregate-only JSON report."""

import argparse
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CountingResult(unittest.TextTestResult):
    """Count successful test cases directly, including cases using subtests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = 0

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed += 1


def discover_suite(pattern="test*.py"):
    """Use standard discovery, anchored to this repository's tests directory."""
    # Direct script invocation must also support imports of repository tooling.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    return unittest.TestLoader().discover(str(ROOT / "tests"), pattern=pattern)


def select_suite(patterns):
    """Combine requested discoveries once per test ID; require every selection."""
    groups = [discover_suite(pattern) for pattern in patterns]
    if not groups or any(not group.countTestCases() for group in groups):
        return unittest.TestSuite()
    if len(groups) == 1:
        return groups[0]

    def cases(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from cases(test)
            else:
                yield test

    selected = {}
    for group in groups:
        for test in cases(group):
            selected.setdefault(test.id(), test)
    return unittest.TestSuite(selected.values())


def run_suite(suite, stream=None):
    """Keep ordinary verbose unittest diagnostics on the supplied stream."""
    return unittest.TextTestRunner(
        stream=stream, verbosity=2, resultclass=CountingResult,
    ).run(suite)


def summarize(result):
    """Return only counts and test success, never test details.

    Passed counts addSuccess callbacks. Other counts follow unittest's outcome
    lists; subtests and fixture errors mean these counts are not a partition of
    run. Empty discovery fails even though unittest considers it successful.
    """
    return {
        "run": result.testsRun,
        "passed": result.passed,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses),
        "success": result.testsRun > 0 and result.wasSuccessful(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--documentation", action="store_true",
                           help="run documentation links and guide rendering only")
    selection.add_argument("--pattern", action="append",
                           help="discovery filename pattern; repeat to combine selections (default: test*.py)")
    parser.add_argument("--summary", type=Path,
                        help="write aggregate counts as JSON, creating parent directories")
    args = parser.parse_args(argv)
    patterns = ("test_documentation.py", "test_guide_page.py") if args.documentation else (
        args.pattern or ("test*.py",)
    )
    suite = select_suite(patterns)
    summary = summarize(run_suite(suite))
    print("Tests: run={run}, passed={passed}, failures={failures}, errors={errors}, "
          "skipped={skipped}, expected_failures={expected_failures}, "
          "unexpected_successes={unexpected_successes}, success={success}".format(**summary))
    if not summary["run"]:
        print("No tests were discovered.", file=sys.stderr)
    if args.summary is not None:
        try:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        except OSError:
            print("Could not write test summary.", file=sys.stderr)
            return 2
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
