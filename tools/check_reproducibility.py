"""Compare two isolated local builds without publishing or contacting services."""
import argparse
from pathlib import Path
import tempfile

import build_site
import package
import repository
import verify_repository

MAX_FILES = 256
MAX_BYTES = 128 * 1024 * 1024


class ReproducibilityError(ValueError):
    """Fixed categories only; build paths and source contents are never reported."""


def _snapshot(root):
    files, directories = {}, set()
    total = 0
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ReproducibilityError("invalid build output")
        if path.is_dir():
            directories.add(name)
        elif path.is_file():
            if len(files) >= MAX_FILES or path.stat().st_size > MAX_BYTES - total:
                raise ReproducibilityError("build output exceeds bounds")
            data = path.read_bytes()
            total += len(data)
            if total > MAX_BYTES:
                raise ReproducibilityError("build output exceeds bounds")
            files[name] = data
        else:
            raise ReproducibilityError("invalid build output")
    return files, directories


def _build(root):
    site = root / "site"
    candidate = root / "repository"
    build_site.build_site(site, package_output=root / "package")
    repository.build(candidate)
    verified = verify_repository.verify(candidate)
    site_files, site_dirs = _snapshot(site)
    archive = "plugin.video.homefx-" + package.validate() + ".zip"
    if site_dirs or set(site_files) != {archive, archive + ".sha256", "LICENSE.txt", "index.html"}:
        raise ReproducibilityError("invalid preview output")
    package_path = candidate / "plugin.video.homefx" / archive
    if (site_files[archive] != package_path.read_bytes()
            or site_files[archive + ".sha256"] != package_path.with_suffix(".zip.sha256").read_bytes()
            or site_files["LICENSE.txt"] != (package.ROOT / "LICENSE").read_bytes()
            or not site_files["index.html"]):
        raise ReproducibilityError("inconsistent preview output")
    repository_files, repository_dirs = _snapshot(candidate)
    return {"site": (site_files, site_dirs),
            "repository": (repository_files, repository_dirs)}, verified


def check():
    """Compare exact output bytes twice for the current source and local toolchain.

    This is repeatability within one environment, not cross-platform reproducibility,
    source authenticity, device acceptance, or permission to publish an update channel.
    Source files must remain unchanged while checking. Temporary builds are removed.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="homefx-repeatability-") as temporary:
            root = Path(temporary)
            first, first_verified = _build(root / "first")
            second, second_verified = _build(root / "second")
            if first != second or first_verified != second_verified:
                raise ReproducibilityError("build outputs differ")
            return {"site_files": len(first["site"][0]),
                    "repository_files": len(first["repository"][0]),
                    "packages": first_verified["packages"]}
    except ReproducibilityError:
        raise
    except Exception:
        raise ReproducibilityError("build or verification failed") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = check()
    except ReproducibilityError as error:
        parser.exit(1, "Reproducibility check failed: " + str(error) + "\n")
    print("Two isolated builds match: {site_files} site files, "
          "{repository_files} repository files, {packages} packages.".format(**result))
    print("Local repeatability only; publication and device acceptance remain separate.")


if __name__ == "__main__":
    main()
