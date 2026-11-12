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
its separate automatic PRs. The current integration received HTTP 403 when inspecting
and disabling that setting, so its actual state is unverified. No security settings
were changed. Repository administrators must verify this once.

Initial local scan: three XML-parser findings in tools/package.py (B405 and two B314).
They concern parsing the checked-in manifest and the generated ZIP manifest. They
remain visible for manual trust-boundary assessment; no automatic fix or suppression
was applied. The initial tool dependency audit reported no known vulnerabilities.

No paid scanner subscription is introduced. Bandit and pip-audit are Apache-2.0
open-source tools used only in development. Public standard-runner compute is free;
account artifact-storage limits still apply. Tool upgrades and licence reviews are
manual. The tool inventory pins versions; package hashes are not yet locked.
