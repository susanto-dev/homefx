"""Validate and stage a bounded Pages artifact without tar extraction helpers."""
import argparse
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

import check_published

MAX_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 256
MAX_DEPTH = 5  # repository/plugin.video.homefx/resources/art/icon.png


class UnpackError(ValueError):
    """Fixed diagnostics that do not disclose archive contents or local paths."""


def _require(condition):
    if not condition:
        raise UnpackError("invalid site artifact")


def _name(member):
    name = member.name
    _require(isinstance(name, str) and len(name) <= 512 and "\\" not in name)
    if name == "." and member.isdir():
        return ""
    if name.startswith("./"):
        name = name[2:]
    if member.isdir() and name.endswith("/"):
        name = name[:-1]
    parts = name.split("/")
    _require(bool(name) and len(parts) <= MAX_DEPTH
             and all(part not in ("", ".", "..") for part in parts)
             and not PurePosixPath(name).is_absolute())
    _require(all(all(char.isascii() and (char.isalnum() or char in "_.-")
                     for char in part) for part in parts))
    return name


def unpack(archive, output):
    """Read only regular files/directories, verify staged bytes, then rename once.

    Input and destination parents must be quiescent. No archived permissions,
    ownership, links, metadata, or executable code are applied.
    """
    try:
        archive, output = Path(archive).absolute(), Path(output).absolute()
        _require(not any(path.is_symlink() for path in (archive,) + tuple(archive.parents)))
        _require(not any(path.is_symlink() for path in (output,) + tuple(output.parents)))
        _require(archive.is_file() and archive.stat().st_size <= MAX_BYTES)
        _require(not output.exists() and output.parent.is_dir())
        with tempfile.TemporaryDirectory(prefix=".site-unpack-", dir=str(output.parent)) as temporary:
            staged = Path(temporary) / "site"
            staged.mkdir()
            names, total = set(), 0
            # Only uncompressed tar is produced by the workflow. Streaming avoids
            # loading an unbounded member index or seeking to attacker offsets.
            with archive.open("rb") as source, tarfile.open(fileobj=source, mode="r|") as bundle:
                for count, member in enumerate(bundle, 1):
                    _require(count <= MAX_MEMBERS and member.type in
                             (tarfile.DIRTYPE, tarfile.REGTYPE, tarfile.AREGTYPE))
                    name = _name(member)
                    _require(name not in names)
                    names.add(name)
                    target = staged / name
                    if member.isdir():
                        _require(member.size == 0)
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    _require(0 <= member.size <= MAX_BYTES - total)
                    total += member.size
                    stream = bundle.extractfile(member)
                    _require(stream is not None)
                    with stream:
                        data = stream.read(member.size + 1)
                    _require(len(data) == member.size)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as destination:
                        destination.write(data)
            check_published._expected(staged)
            _require(not output.exists() and not output.is_symlink())
            os.rename(str(staged), str(output))
        return output
    except Exception:
        raise UnpackError("invalid site artifact") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        unpack(args.archive, args.output)
    except UnpackError:
        parser.exit(1, "Site artifact verification failed.\n")
    print("Verified and staged the site artifact.")


if __name__ == "__main__":
    main()
