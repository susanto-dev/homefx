# Development

Start with Python 3.8-compatible syntax, the standard library, and a virtual
environment if desired. The inspected cloud host runs Python 3.12; the TV's exact
embedded interpreter must still be recorded. Build tools require defusedxml 0.7.1
to reject unsafe XML. It is development-only; the Kodi add-on still uses no
third-party Python packages. Optional lint tools are not required or claimed as run.

```sh
python3 -m pip install -r tools/build-requirements.txt
python3 -m unittest discover -s tests -v
python3 tools/package.py
```

The package command parses XML, checks the entry point/API dependency/assets/licence,
checks Python syntax against the 3.8 grammar, and creates an allowlisted ZIP with
fixed timestamps plus a SHA-256 sidecar. It is a focused project validator, not the
full Kodi add-on checker. Add that checker and a pinned linter in a later CI batch.

Pure catalogue/routing logic lives under resources/lib; only default.py imports
Kodi modules. Tests use the standard-library unittest runner and synthetic fixtures.
Tests never log into services. This project does not need Docker, a server, or an
Android application. Trakt foundations use injected request callbacks and mocked responses; an actual
network transport belongs to a later batch.

Future CI should use reviewed immutable Action pins, minimal read permissions,
stable check names, and no service secrets on PRs. Release permissions must be
separate. A scan that skipped files or failed is not a clean scan. The Pages workflow runs tests before building and deploying the preview.
The separate Security scans workflow runs Bandit and pip-audit weekly and on
changes; see security.md for coverage, manual triage and report retention.
Secret scanning and repository security settings remain maintainer-managed.

The Validation workflow runs the complete available unittest suite and builds the
package/site on PRs and main pushes with Python 3.8 and 3.12. It installs only the
pinned build dependency; the optional Action-audit suite runs separately in Security
scans with its audited tool environment. All new Actions use the existing reviewed
commit pins. Validation has read-only permissions and does not deploy or create PRs.
Python 3.8 is a compatibility floor, not a recommendation for a new desktop install;
use a supported interpreter for development. Android/Kodi runtime support still
requires the TV checks.
