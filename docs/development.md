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
python3 tools/repository.py
```

The package command parses XML, checks the entry point/API dependency/assets/licence,
checks Python syntax against the 3.8 grammar, and creates an allowlisted ZIP with
fixed timestamps plus a SHA-256 sidecar. It is a focused project validator, not the
full Kodi add-on checker. Add that checker and a pinned linter in a later CI batch.

Pure catalogue/routing logic lives under resources/lib; only default.py imports
Kodi modules. Tests use the standard-library unittest runner and synthetic fixtures.
Tests never log into services. This project does not need Docker, a server, or an
Android application. Trakt transport/session/library tests use injected connections
and fabricated responses. Local socket-pair tests exercise HTTP parsing without
contacting online services. The Kodi adapter does not enable that network stack.

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

The compatibility matrix uses Ubuntu 22.04 for Python 3.8 and Ubuntu 24.04 for
Python 3.12. `ubuntu-latest` resolved to 26.04 during the first run and lacked a
Python 3.8 distribution, so that job failed before tests; explicit runner versions
keep the intended interpreter coverage. Hosted image contents still change over time.

The repository generator writes a local candidate under `dist/repository` (or
`--output PATH`). It accepts a fresh directory or identical prior output, and refuses
to overwrite differing content. Use a new output directory for a changed candidate;
inspect before removing old build output. Validation uploads the Python 3.12 candidate
as a seven-day artifact for manual review. It is separate from `dist/site` and is not
an operational update channel. Never publish arbitrary CI artifacts as releases
without inspecting their source/head and completing the publication gates.

Main is protected and accepts PRs only. Do not bypass branch protection or use direct
main pushes. Keep code/review evidence in ordinary project language; local development
instructions belong here, contribution policy in CONTRIBUTING.md, and release gates
in releases.md.
