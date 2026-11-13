"""Prepare a verified local release proposal without changing tracked releases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import package
import release_history
import repository

ROOT = package.ROOT


class PreparationError(ValueError):
    """Fixed diagnostics without archive contents or local filesystem details."""


def _require(condition):
    if not condition:
        raise PreparationError("release preparation failed")


def prepare(base_ref, output):
    """Stage the complete prospective inventory and its archives in a new directory.

    Source files, release inputs and destination parents must be quiescent. A
    proposal is not publication or approval: review its diff before copying only
    new archives and inventory into the repository. Existing records never change.
    """
    try:
        root, output = Path(ROOT).absolute(), Path(output).absolute()
        inventory = root / "releases" / "inventory.json"
        repository._no_symlinks(output)
        output = output.resolve()
        root = root.resolve()
        _require(not output.exists() and output.parent.is_dir())
        # Allow ordinary dist staging or an external directory, never write a
        # proposal amongst tracked sources or inside the authoritative inventory.
        _require(root not in output.parents or root / "dist" in output.parents)
        _require(output != root)
        current = release_history._read(inventory)
        prior = release_history._base_records(inventory, base_ref, root)
        _require(all(current.get(identity) == record for identity, record in prior.items()))
        with tempfile.TemporaryDirectory(prefix=".release-proposal-", dir=str(output.parent)) as temporary:
            temporary = Path(temporary)
            # This verifies every retained archive, same-version bytes and bounds.
            candidate = repository.build(temporary / "candidate", retain_manifest=inventory)
            generated = release_history._read(candidate / "release-inventory.json")
            proposal = temporary / "proposal"
            proposal.mkdir()
            records = []
            for identity, item in generated.items():
                record = current.get(identity)
                if record is None:
                    record = dict(item, path="archives/" + Path(item["path"]).name)
                source = candidate / item["path"]
                data = repository._safe_file(source.parent, source.name, repository.MAX_PACKAGE)
                _require(hashlib.sha256(data).hexdigest() == record["sha256"])
                target = proposal / record["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
                records.append(record)
            _require(len(records) == len(generated) and set(current) <= set(generated))
            data = json.dumps({"schema": 1, "packages": records}, indent=2) + "\n"
            _require(len(data.encode("utf-8")) <= repository.MAX_INVENTORY)
            staged_inventory = proposal / "inventory.json"
            staged_inventory.write_text(data, encoding="utf-8")
            release_history.verify_history(staged_inventory, previous_inventory_path=inventory)
            # A concurrent inventory change invalidates this proposal, even when
            # it happens to retain all records seen during the first read.
            _require(release_history._read(inventory) == current)
            _require(not output.exists() and not output.is_symlink())
            os.rename(str(proposal), str(output))
        return output
    except Exception:
        raise PreparationError("release preparation failed") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Absent staging directory; parent must exist")
    parser.add_argument("--base-ref", required=True, help="Reviewed Git base commit or ref")
    args = parser.parse_args()
    try:
        prepare(args.base_ref, args.output)
    except PreparationError:
        parser.exit(1, "Release preparation failed.\n")
    print("Prepared a verified local release proposal. Review before integrating; nothing published.")


if __name__ == "__main__":
    main()
