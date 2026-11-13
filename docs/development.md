# Development

Use Python 3.11-compatible syntax and standard-library APIs for the Kodi add-on.
The target is the official Kodi 21.2 Android build, whose dependency source pins
Python 3.11.7. CI tests the maintained 3.11 patch line and Python 3.12; developers
can use either. This supersedes the earlier conservative 3.8 policy. It does not
establish device navigation, storage, TLS or performance acceptance.

Build tools require defusedxml 0.7.1
to reject unsafe XML, and pinned markdown-it-py/mdurl to render the installation guide. It is development-only; the Kodi add-on still uses no
third-party Python packages. Ruff 0.17.4 provides a pinned, read-only correctness check; it is also development-only.

```sh
python3 tools/check_dependencies.py
python3 -m pip install --require-hashes -r tools/build-requirements.txt
python3 -m pip install --require-hashes --only-binary=:all: -r tools/quality-requirements.txt
python3 tools/check_quality.py
python3 tools/run_tests.py --summary dist/tests/summary.json
python3 tools/package.py
python3 tools/repository.py
python3 tools/verify_repository.py dist/repository
```

The package command parses XML, checks the entry point/API dependency/assets/licence,
checks Python syntax against the 3.11 grammar, and creates an allowlisted ZIP with
fixed timestamps plus a SHA-256 sidecar. It is a focused project validator, not the
full Kodi add-on checker. The official Kodi add-on checker remains an explicit coverage gap. Ruff checks
Pyflakes F rules in addons and tools with a Python 3.11 target; it does not validate Kodi APIs.

Pure catalogue/routing logic lives under resources/lib; only default.py imports
Kodi modules. Tests use the standard-library unittest runner and synthetic fixtures.
Tests never log into services. This project does not need Docker, a server, or an
Android application. Trakt transport/session/library tests use injected connections
and fabricated responses. Local socket-pair tests exercise HTTP parsing without
contacting online services. The Kodi adapter does not enable either provider network stack. Real-Debrid storage,
transport and session tests use temporary SQLite stores and fabricated HTTP streams.
Never use the cloud development environment or CI for real debrid account traffic.

CI uses reviewed immutable Action pins, minimal read permissions,
stable check names, and no service secrets on PRs. Release permissions are
separate. A scan that skipped files or failed is not a clean scan. The Pages workflow runs tests before building and deploying the preview.
The separate Security scans workflow runs Bandit and pip-audit weekly and on
changes; see security.md for coverage, manual triage and report retention.
Secret scanning and repository security settings remain maintainer-managed.

The Validation workflow runs the complete available unittest suite and builds the
package/site on PRs and main pushes with Python 3.11 and 3.12. Build, quality and security dependencies are installed from pinned, hash-locked
requirement files in their respective jobs. The Action-audit suite runs in Security
scans with its audited tool environment. All new Actions use the existing reviewed
commit pins. Validation has read-only permissions and does not deploy or create PRs.
Python 3.11 is the minimum supported source/runtime target; 3.12 catches newer-runtime
regressions and runs release/security tooling. Both matrix jobs run the full suite
and packaging checks, not two copies of the same interpreter. All CI runners are
explicitly Ubuntu 24.04 for this matrix; hosted image contents still change.

Evidence is pinned to Kodi 21.2 source revision
[`d1a1d48c3cb3722d39264ffdd8132f755ffecd27`](https://github.com/xbmc/xbmc/tree/d1a1d48c3cb3722d39264ffdd8132f755ffecd27):
[Python 3.11.7 dependency](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/tools/depends/target/python3/PYTHON3-VERSION),
[depends Python selection](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/cmake/modules/FindPython.cmake),
and [Android build instructions](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/docs/README.Android.md).
The manifest's `xbmc.python` 3.0.1 denotes the Kodi add-on API, not the embedded
CPython version, and remains unchanged. No interpreter is bundled with HomeFX.

The required-check name changes from **Python 3.8 tests and package** to
**Python 3.11 tests and package**. If branch protection names the old check,
the maintainer must replace that requirement; a stale requirement must not be
satisfied with a misleading job label or bypassed. Repository settings are not
modified by the source change.

The repository generator writes a local candidate under `dist/repository` (or
`--output PATH`). It accepts a fresh directory or identical prior output, and refuses
to overwrite differing content. Use a new output directory for a changed candidate;
inspect before removing old build output. Validation uploads the Python 3.12 candidate
as a seven-day artifact for manual review. The candidate is separate from the experimental preview repository staged inside
`dist/site/repository`, which the Pages workflow deploys after a reviewed main merge. Never publish arbitrary CI artifacts as releases
without inspecting their source/head and completing the publication gates.

Main is protected and accepts PRs only. Do not bypass branch protection or use direct
main pushes. Keep code/review evidence in ordinary project language; local development
instructions belong here, contribution policy in CONTRIBUTING.md, and release gates
in releases.md.

For a retained-version candidate, pass `--retain-manifest PATH` to the repository
builder. The inventory names only local, reviewed ZIPs and their expected SHA-256
checksums. See releases.md for its schema and trust boundary. No build step downloads
old releases, and no retained archive code is executed. Use a fresh output directory
when candidate bytes change. Tests include the old-version/current-index distinction.

Validation and Security scans explicitly run for PR opened, synchronize, reopened
and ready_for_review events. Draft creation already runs checks; promotion reruns
them against the same source head. Wait for those fresh runs before treating the
ready PR as mergeable. They use existing full-SHA Action pins, read-only repository
permissions and no comment-posting step. Weekly security/update discovery remains.

The repository verifier is read-only and separate from generation. It validates the
candidate before CI uploads it and can inspect a detached/copied artifact locally.
It does not repair mismatches, publish files or establish source trust. Use a fresh
candidate directory when source changes; the generator's immutable-output guard stays.

The release repeatability check runs `python tools/check_reproducibility.py`. It builds
two temporary site/package/candidate trees and compares their paths and bytes; neither
run writes to the ordinary dist output. This checks one source revision and local
toolchain, not reproducibility between different platforms or toolchain versions.

## Release history and deployed bytes

For video 0.17.2 and repository 0.2.0, record both current ZIPs and every retained
version in `releases/inventory.json`. Run
`python tools/release_history.py releases/inventory.json --base-ref BASE_SHA`
against the reviewed base; existing records cannot be removed or changed. Builders
validate retained hashes, archive contents and exact current build bytes. Bounds
fail closed rather than pruning old releases. See [release policy](releases.md).

The site builder defaults to that inventory when present and embeds a verified preview
repository plus matching root bootstrap/video downloads. Use fresh output directories
for changed builds. No skin is bundled. The existing skin's widget behavior remains
a device acceptance item, as do repository installation and updates.

After Pages deployment, `python tools/check_published.py PATH_TO_EXTRACTED_SITE`
compares the exact deployed build artifact with public HTTPS responses. Do not rebuild
the expected files for this check. HTTP integrity is independent of TV acceptance;
CI must not label live accounts, navigation or playback as passed.

Hash locks restrict accepted dependency artifacts, not all supply-chain risk. Refresh
pins and hashes together after manual review; weekly dependency/Action discovery does
not create update PRs. Install security tooling with
`python -m pip install --require-hashes -r tools/security-requirements.txt`.


For a version change, [prepare a verified release proposal](release-preparation.md)
in a fresh external or dist subdirectory. The helper does not modify releases in
place. Review its inventory and new ZIPs, integrate only the intended new records,
then run the history guard against the reviewed base. Never replace published bytes
to make a changed same-version build pass.

The account assemblies and UI adapter are explicit, inactive development entry points.
See [service runtime](service-runtime.md), [shared interaction](provider-account-flow.md)
and [dialog contract](account-ui.md). Supply the same cancellation probe throughout;
no constructor should contact providers. The optional on-device storage self-check is
separate from account assembly and uses only synthetic data after confirmation.

Use the [test runner](testing.md) for aggregate local/CI results. Focused runs are
useful during development, but do not replace full discovery before review. A
report of passing tests is not a measurement of source-line or branch coverage.

The [dependency inventory guard](dependencies.md) uses only the standard library and
runs before dependency installation in CI. It checks the supported declaration
format and cross-file consistency; pip hash verification and vulnerability scans
remain separate gates. No dependency graph or update settings are changed by it.

The current video source validator requires nonblank add-on name/provider fields,
one mandatory Kodi Python 3.0.1 import, one video plugin extension and one metadata
extension, singleton MIT/all metadata and reviewed asset declarations. These are
HomeFX preview policies; nonblank identity fields are stricter than the inspected
official schema's string-presence requirement. Historical archive validation remains
separate, and changing build policy does not rewrite retained releases.

## Public Trakt configuration preflight

See [environment setup](account-setup.md#github-configuration-environments).
`tools/check_trakt_config.py` checks process environment values offline and emits
fixed diagnostics only. Tests use fabricated identities and redirects; no actual
account belongs in CI. The dedicated main-only workflow selects Development by
default and Production only by explicit manual choice. It does not change release
bytes, add a client-secret requirement or enable provider access.

## Installation guide and Pages

Edit the canonical [installation guide](install.md); the site builder renders it
as `install.html` with local CSS and no copied screenshots or remote assets. The
landing page links to it, and the public README links to both the repository source
and Pages route. Do not maintain a separate HTML copy of the guide text.

Use a fresh site output directory after changes. Check local links/anchors and
phone-width rendering, then run packaging, site topology, artifact-unpacking,
published-byte and reproducibility tests. The site allowlist requires the guide;
missing/corrupt hosted guide bytes fail publication verification. The guide is not
included in any Kodi ZIP. Main merge publishes automatically through the existing
Pages workflow; PR checks do not deploy. Verify the hosted guide after merge rather
than dispatching publication separately. A browser layout test is not a Kodi/TV test.
