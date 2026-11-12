"""Run the pinned, read-only Python correctness checks used by development CI."""

import importlib.metadata
from pathlib import Path
# Invoke the pinned local checker without a shell.
import subprocess  # nosec B404
import sys


ROOT = Path(__file__).resolve().parents[1]
RUFF_VERSION = "0.17.4"


def check(root=ROOT):
    """Return a failing status for missing tooling or unsuccessful lint checks."""
    try:
        version = importlib.metadata.version("ruff")
    except importlib.metadata.PackageNotFoundError:
        print("Install tools/quality-requirements.txt before running quality checks.")
        return 2
    if version != RUFF_VERSION:
        print("Quality checks require Ruff " + RUFF_VERSION + ".")
        return 2
    command = [
        sys.executable, "-m", "ruff", "check", "--isolated", "--select", "F",
        "--target-version", "py38", "addons", "tools",
    ]
    try:
        # Fixed interpreter/module/options, no shell or user-supplied command.
        result = subprocess.run(command, cwd=root, timeout=120, check=False)  # nosec B603
    except (OSError, subprocess.TimeoutExpired):
        print("Quality checker could not complete.")
        return 2
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(check())
