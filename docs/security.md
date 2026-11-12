# Security design

Current preview: no outbound requests or accounts. Only synthetic watched overrides
and demo list selection are saved in the Kodi profile. Reset clears these overrides.
The package includes only an explicit file list. Do not package any user profile.

Future service integration must use supported public-client authentication without
shipping a client secret. Keep user tokens out of plugin URLs, logs and diagnostics.
Serialize token refresh and atomically replace rotated tokens. Kodi profile storage
is not a vault against other code running inside Kodi. Specify disconnect, revocation,
cache retention and account-switch behavior before connecting real accounts.

Validate remote responses, bound requests and caches, retain TLS verification, handle
rate limits and cancellations, and avoid duplicate watch-history writes. Read-only
metadata access and Trakt write actions have separate acceptance criteria.

Before release: review dependencies and exact licences, scan source/history for
secrets, inspect packaged bytes, and record scanner coverage and failures. Original
artwork may be shipped; third-party skins/art/code require a separate provenance and
compatibility review. Design for content users are authorized to access.

## Automated checks and manual triage

`Security scans` runs on main pushes, PRs targeting main, manual dispatch, and
Mondays at 01:23 UTC (09:23 Asia/Kuala_Lumpur). GitHub scheduled jobs can be delayed;
public-repository schedules may be disabled after prolonged repository inactivity.
The existing GitHub-managed CodeQL configuration remains separate and unchanged.

Bandit scans add-on and build Python. pip-audit queries published advisories for
`requirements.txt` (currently no third-party runtime Python packages) and the fully
version-pinned audit-tool inventory, including its transitive dependencies. Audit
packages are development-only and excluded from the Kodi ZIP. These checks do not
scan Kodi/Android, undocumented dependencies, or transitive GitHub Action packages.
Action commit pins still require manual provenance/advisory review. Audits are not
licence-compatibility reviews or a guarantee of vulnerability absence.

JSON reports are retained for seven days and counts appear in the run summary.
Any finding or scanner failure fails the check; independent scans still run and
reports are uploaded. A missing or skipped report is not a clean result. Review the
run promptly, assess affected code/version and exposure, then make a manual fix or
record a narrow justified exception. Re-run to verify. Never suppress everything
just to get a green result. Do not paste credentials or private data into issues.

No workflow creates issues, suggestions, remediation PRs, or commits. No Dependabot
version-update configuration is installed. Keep Dependabot alerts enabled if desired,
but disable **Dependabot security updates** in repository security settings to prevent
its separate automatic PRs. The owner confirmed Dependabot security updates were disabled on 2026-11-12.
The integration could not independently read that setting (HTTP 403); no further
setting change is needed based on the owner confirmation.

Initial local scan: three XML-parser findings in tools/package.py (B405 and two B314).
They concern parsing the checked-in manifest and the generated ZIP manifest.
The manually reviewed fix uses defusedxml for both source and ZIP readback,
rejects DTDs/entities, and bounds source manifest reads to 1 MiB. Regression tests
cover malicious source and archive readback. No warning suppression was added.
The initial tool dependency audit reported no known vulnerabilities.
defusedxml is PSF-licensed, development-only, and already included in the audited
tool inventory. It adds no paid service or Kodi runtime dependency.

No paid scanner subscription is introduced. Bandit and pip-audit are Apache-2.0
open-source tools used only in development. Public standard-runner compute is free;
account artifact-storage limits still apply. Tool upgrades and licence reviews are
manual. The tool inventory pins versions; package hashes are not yet locked.


## External Action pins and update discovery

Every external `uses:` in `.github` must use a full 40-character commit SHA.
Local Actions must reside under `.github` and are inspected too. Docker-style
Action references are currently rejected rather than treated as commit-pinned.
The guard reads YAML including reusable workflow references, not comments.
Pages publication runs the local guard before building. Security scans run guard
failure fixtures, then online discovery on main pushes, manual runs and the same
weekly schedule. PR runs use only offline validation, with no API token passed to
PR code. Nested upstream composite Actions and reusable workflow references are
recursively inspected at the pinned commits during online runs.

The pinned Pages wrapper formerly delegated to a floating upload-artifact tag.
It was replaced with a local tar step and a directly SHA-pinned official uploader.
No upstream implementation code was copied into the repository.

`action-audit` reports contain each pin, latest stable release tag/resolved commit,
and whether the release is ahead, behind or divergent. Annotated tags are resolved
to their commit. Missing release metadata is labelled for manual tag review;
network/parse failures or unpinned dependencies fail the job. New releases alone
are informational, never automatic approvals or updates. Review changelogs, source,
provenance and compatibility before manually changing any SHA, then run checks.
Reports are retained seven days. No write token, automatic PRs or fix operation.

Local commands (install tools/security-requirements.txt first):
`python tools/action_audit.py` and `python tools/action_audit.py --online`.
Online mode optionally accepts GH_TOKEN for authenticated GitHub API reads.
Never log that value. The checker covers nested uses, not bundled libraries,
runtime downloads or the runner image. SHA pinning protects against moved tags;
it does not prove an Action is trustworthy or free of vulnerabilities.
