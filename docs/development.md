# Development

Start with Python 3.8-compatible syntax, the standard library, and a virtual
environment if desired. The inspected cloud host runs Python 3.12; the TV's exact
embedded interpreter must still be recorded. No external Python packages are
needed for this batch. Optional lint tools are not required or claimed as run.

```sh
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
Android application. Runtime network support belongs to later batches.

Future CI should use reviewed immutable Action pins, minimal read permissions,
stable check names, and no service secrets on PRs. Release permissions must be
separate. A scan that skipped files or failed is not a clean scan. The Pages workflow runs tests before building and deploying the preview.
Secret and vulnerability scanners are not configured by this project yet;
repository-level security settings are managed separately by the maintainer.
