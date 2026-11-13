# Development tooling and dependency integrity

These tools run on development machines and CI, outside Kodi. They are not
bundled with the add-on ZIPs. Installing these open-source tools requires no
licence purchase. Hosted CI usage is subject to the hosting account's allowance;
this change does not purchase a service or change HomeFX's source licence.

## Python correctness gate

[Ruff 0.17.4](https://pypi.org/project/ruff/0.17.4/) is MIT-licensed; the
[upstream project](https://github.com/astral-sh/ruff) and the
[exact release metadata](https://pypi.org/pypi/ruff/0.17.4/json) identify its
licence and artifacts. Its declared Python requirement is Python 3.7 or later.
HomeFX runs its `F` (Pyflakes) rules over `addons` and `tools`, targeting Python
3.11. This catches errors such as undefined names and unused imports without
introducing automatic formatting. `--isolated` makes the selected rules
independent of incidental local configuration. The gate never modifies source.
This is a focused correctness check, not proof of Kodi compatibility or a
substitute for tests and security review.

Install and run from the repository root:

```sh
python -m pip install --require-hashes --only-binary=:all: -r tools/quality-requirements.txt
python -m unittest discover -s tests -p test_quality.py -v
python tools/check_quality.py
```

The test includes a real undefined-name mutation and a corrected fixture. That
integration test skips in environments without the pinned Ruff version; the
quality job must install its requirements so it actually runs. Missing or
incorrect Ruff versions fail the quality command rather than reporting success.

## Hash-locked development dependencies

All three requirements files pin exact versions and SHA-256 hashes from each
version's PyPI JSON release record, using the `/pypi/NAME/VERSION/json` endpoint.
The locks include every non-yanked release artifact for portability. CI uses
`--only-binary=:all:` to prevent source builds from obtaining additional build
dependencies outside the lock. A missing compatible wheel fails installation.
Updating a pin requires reviewing its upstream release, licence and dependency
changes, regenerating verified artifact hashes and running the relevant checks.
Hashes verify the downloaded bytes against the recorded release; they do not
prove publisher identity, safety, licence compatibility or absence of advisories.

```sh
# Build/XML checks: Python 3.11 and 3.12.
python -m pip install --require-hashes --only-binary=:all: -r tools/build-requirements.txt
# Security tools: Python 3.12, separate from the Kodi runtime requirement.
python -m pip install --require-hashes --only-binary=:all: -r tools/security-requirements.txt
```

The existing XML dependency [defusedxml 0.7.1](https://pypi.org/project/defusedxml/0.7.1/)
is PSFL-licensed. The security dependency versions remain unchanged by hash
locking; their own licences continue to apply. This document does not authorize
copying dependency source or redistributing tooling inside add-on packages.

## Official Kodi checker: evaluated, not a passing release gate

The [official checker](https://github.com/xbmc/addon-check),
[`kodi-addon-checker` 0.0.36](https://pypi.org/project/kodi-addon-checker/0.0.36/),
was examined separately. Its
[exact release metadata](https://pypi.org/pypi/kodi-addon-checker/0.0.36/json)
classifies it as GPLv3 and its source headers specify `GPL-3.0-only`. Running a
standalone development checker does not itself relicense the original files it
inspects. No checker source is copied into HomeFX and the checker is not added
to its dependency locks or distributed packages.

Version 0.0.36 has concrete limitations for this personal add-on repository:

- Its command initializes official repository metadata even with
  `--skip-dependency-checks`. The inspected `check_addon.py` uses mutable HTTP
  mirror URLs (`http://mirrors.kodi.tv/addons/{branch}/addons.xml.gz`).
- Its bundled Omega manifest schema rejects the repository manifest's
  `<dir minversion="21.0.0">` attribute. The Kodi repository compatibility
  requirement is documented in [releases.md](releases.md); removing it just to
  satisfy this checker would change the supported installation contract.
- An isolated invocation of its Omega schema validation reported no problems
  for the video add-on manifest and one problem for the repository manifest.
  This was a schema diagnostic, **not** a full checker pass or Kodi device test.

Adopting the full checker remains pending an upstream-compatible repository
schema and a reviewed offline or secure-input mode. HomeFX's own manifest,
archive and repository-index checks remain the applicable gates. Official
Kodi.org submission requirements must be assessed separately if submission is
later proposed. Any future redistribution or modification of the checker would
need its GPL obligations reviewed first.

The checker evaluation was repeated on 2026-11-13. PyPI still reports 0.0.36;
its wheel SHA-256 is
`bb524725f145bab9cd46ac59b10ca136717ef0c664b00f1d50fc296f431f9e8b`.
The release archive was inspected statically without installing or executing it.
The inspected upstream revision
[`67be5c1eca23e01402a447f995e2216bd83202f3`](https://github.com/xbmc/addon-check/tree/67be5c1eca23e01402a447f995e2216bd83202f3)
still has the HTTP initialization and repository schema limitations above. Its
[CLI](https://github.com/xbmc/addon-check/blob/67be5c1eca23e01402a447f995e2216bd83202f3/kodi_addon_checker/__main__.py)
offers no reviewed local-index mode. Its broad dependency constraints would also
require a separately reviewed hash-locked installation before adoption.

HomeFX instead strengthens its own current source-manifest contract, with mutation
tests for required metadata, duplicate/unknown extensions and unexpected dependency
imports. This adds no checker code or dependencies and changes no published bytes.
It remains a focused project gate, not official checker acceptance.

## Installation guide rendering

The build renders original `docs/install.md` into a static HTML guide using
[markdown-it-py 4.3.0](https://pypi.org/project/markdown-it-py/4.3.0/) and
[mdurl 0.1.2](https://pypi.org/project/mdurl/0.1.2/). Both already appear in the
security tooling lock; their identical pins and SHA-256 hashes are now explicit in
the build lock so ordinary validation can render the guide independently.

Checked the exact wheel artifacts against their
[markdown-it-py release metadata](https://pypi.org/pypi/markdown-it-py/4.3.0/json)
and [mdurl release metadata](https://pypi.org/pypi/mdurl/0.1.2/json) on 2026-11-13.
The wheel licence files contain MIT grants: markdown-it-py's ExecutableBookProject
notice and upstream markdown-it notice, and mdurl's Vitaly Puzrin/Alex Kocharin,
Taneli Hukkinen and Joyent/Node contributor notices. The installed distributions
retain those notices. No dependency source or third-party artwork is copied into
the repository, generated guide or Kodi ZIPs. This is development-only rendering;
no paid licence, runtime dependency or new service is introduced. HomeFX's existing
licence notices remain unchanged.
