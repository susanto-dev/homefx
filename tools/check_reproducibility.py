"""Compare two isolated local builds without publishing or contacting services."""
import argparse
import os
from pathlib import Path
import tempfile

import build_site
import check_published
import development_download
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


def _build(root, development_environment=None):
    site = root / "site"
    candidate = root / "repository"
    inventory = package.ROOT / "releases/inventory.json"
    retained = inventory if inventory.exists() or inventory.is_symlink() else None
    options = {"package_output": root / "package", "retain_manifest": retained}
    if development_environment is not None:
        options["development_environment"] = development_environment
    build_site.build_site(site, **options)
    repository.build(candidate, retain_manifest=retained)
    verified = verify_repository.verify(candidate)
    public_verified = verify_repository.verify(site / "repository", channel="preview")
    if verified != public_verified:
        raise ReproducibilityError("inconsistent repository output")
    site_files, site_dirs = _snapshot(site)
    public_files, public_dirs = _snapshot(site / "repository")
    archive = "plugin.video.homefx-" + verified["current"]["plugin.video.homefx"] + ".zip"
    bootstrap = "repository.homefx-" + verified["current"]["repository.homefx"] + ".zip"
    expected_files = {"repository/" + name for name in public_files}
    expected_files.update({archive, archive + ".sha256", bootstrap, bootstrap + ".sha256",
                           "LICENSE.txt", "index.html", "install.html"})
    for video in (False, True):
        development_archive = development_download.verify(site_files, video=video)
        if (development_environment is None) != (development_archive is None):
            raise ReproducibilityError("invalid Development output")
        if development_archive is not None:
            expected_files.update({development_archive, development_archive + ".sha256"})
    if development_environment is not None:
        check_published._expected(site)
    expected_dirs = {"repository"} | {"repository/" + name for name in public_dirs}
    if set(site_files) != expected_files or site_dirs != expected_dirs:
        raise ReproducibilityError("invalid preview output")
    for ident, name in (("plugin.video.homefx", archive), ("repository.homefx", bootstrap)):
        package_path = candidate / ident / name
        public_path = site / "repository" / ident / name
        for suffix in ("", ".sha256"):
            if (site_files[name + suffix] != Path(str(package_path) + suffix).read_bytes()
                    or site_files[name + suffix] != Path(str(public_path) + suffix).read_bytes()):
                raise ReproducibilityError("inconsistent preview output")
    if (site_files["LICENSE.txt"] != (package.ROOT / "LICENSE").read_bytes()
            or not site_files["index.html"]
            or not 0 < len(site_files["install.html"]) <= build_site.guide_page.MAX_PAGE_BYTES):
        raise ReproducibilityError("inconsistent preview output")
    repository_files, repository_dirs = _snapshot(candidate)
    return {"site": (site_files, site_dirs),
            "repository": (repository_files, repository_dirs)}, verified


def check(development_environment=None):
    """Compare exact output bytes twice for the current source and local toolchain.

    This is repeatability within one environment, not cross-platform reproducibility,
    source authenticity, device acceptance, or permission to publish an update channel.
    Source files must remain unchanged while checking. Temporary builds are removed.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="homefx-repeatability-") as temporary:
            root = Path(temporary)
            if development_environment is None:
                first, first_verified = _build(root / "first")
                second, second_verified = _build(root / "second")
            else:
                first, first_verified = _build(root / "first", development_environment)
                second, second_verified = _build(root / "second", development_environment)
            if first != second or first_verified != second_verified:
                raise ReproducibilityError("build outputs differ")
            return {"site_files": len(first["site"][0]),
                    "repository_files": len(first["repository"][0]),
                    "packages": first_verified["packages"]}
    except ReproducibilityError:
        raise
    except Exception:
        raise ReproducibilityError("build or verification failed") from None


def main(argv=None, environment=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", action="store_true",
                        help="Check the explicitly configured Development download too")
    args = parser.parse_args(argv)
    configured = (os.environ if environment is None else environment) if args.development else None
    try:
        result = check(development_environment=configured)
    except ReproducibilityError as error:
        parser.exit(1, "Reproducibility check failed: " + str(error) + "\n")
    print("Two isolated builds match: {site_files} site files, "
          "{repository_files} repository files, {packages} packages.".format(**result))
    print("Local repeatability only; publication and device acceptance remain separate.")


if __name__ == "__main__":
    main()
