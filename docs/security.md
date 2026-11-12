# Security design

Current preview: no outbound requests or accounts. Only synthetic watched overrides
and demo list selection are saved in the Kodi profile. Reset clears these overrides.
The package includes only an explicit file list. Do not package any user profile.

Inactive authentication/session foundations use injected responses, never a bundled client
secret or a live account configuration. Their dedicated profile token database uses
owner-only directory/file permissions on POSIX systems and fails closed on other
platforms. Android/Kodi SQLite and permission support still need device testing. Tokens and device prompts
have redacted object representations; public failures omit raw transport/response
details. This does not sanitize an arbitrary caller that logs request arguments.
The implemented transport preserves this boundary; future UI wiring must do so too.

A durable refresh claim removes the old token pair from the active row before the
request. Only one invocation wins, and the matching claimant atomically installs
the rotated pair. Ambiguous failure or expired claims require reauthentication;
they never release the old token for retry. Disconnect/new login invalidates stale
completion. Connected request I/O has a budget shorter than the bounded claim lifetime. OS DNS
resolution is not interruptible by socket timeouts; an expired claim rejects any
late response and never permits reuse of the consumed token.

The store is not encrypted and is not a vault against other code running as Kodi.
Local disconnect clears active rows; secure-delete is best effort, not guaranteed
forensic erasure from filesystem snapshots/backups. Service-side revocation, cache
retention and account-switch UX remain gates before connecting real accounts. Do
not export profile files. No token database is created by the current Kodi adapter.

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

## Inactive transport and session boundary

The standard-library transport uses fixed HTTPS hosts, default certificate/hostname
verification, strict route/header/body allowlists and no environment proxies or
redirect following. It bounds JSON bytes/nesting/numeric values, rejects duplicate
keys and nonfinite numbers, and does not expose raw service failures. Socket I/O
shares a deadline; cancellation is checked between blocking operations. DNS duration
remains OS-bound, so actual cancellation/load behavior must be measured on TV.

Session reads check credential generation around remote calls and cache hits. A
401 clears only the generation used by that request, never a newer account. Conditional
login installation prevents stale login completion from restoring a disconnected or
replaced session. No data call is retried automatically. Library cache entries are
copied and bounded to invocation memory; local library disconnect clears them, while
external account changes are noticed on the next access. No background worker or
private persistent metadata cache is introduced. Live Kodi account actions remain
disabled, including with manually installed profile files.

The generated repository candidate is a CI review artifact only. SHA-256 checks
verify index/package bytes but are not signatures or a substitute for trusted HTTPS
publication. Candidate paths are not copied into the deployed preview site. Activation
requires separate retained-version, installation, upgrade and rollback checks.

## Private selections and explicit action contracts

Optional account preferences store only bounded selected-list IDs under a SHA-256
namespace derived from the verified user UUID. They use a separate owner-private
SQLite file, never tokens, titles, watch history or a copy of account settings.
The hash is not encryption or anonymization. The profile remains sensitive and
must not be shared. Library disconnect clears all saved choices in that local
profile, even if account identity was never fetched; it does not contact Trakt.
Credentials are invalidated before preference clearing. A persistent preference
epoch rejects delayed saves from before that clear, so an in-flight selection
cannot restore choices after disconnect.

The stable UUID is rechecked after token-generation changes before restoring choices.
Missing or malformed identity fails closed; mutable usernames are not a fallback.
Cache keys include library identity, credential generation and local action revision.
Compound reads reject changes during the operation. These checks protect invocation
isolation, not arbitrary code already running as the Kodi user.

Explicit action contracts permit one mark-watched history addition or a movie addition
to an owned list. Liked-list status is not permission to write. Validated input precedes
refresh or network work; no mutation callback is configured in the preview. Calls are
never queued or automatically retried. A timeout or malformed response can hide a
successful remote action, so the result stays uncertain and local watched state is
not changed. Reconcile service state before any manual retry; repeated history plays
can create duplicate records. Remote history deletion is not implemented.
Same-session reads are blocked while an action is pending, and cache revisions
change both before the request and at completion, including response loss. This
prevents a concurrent read from keeping pre-write state cached after the result.

## Readiness report and account-flow UI boundary

The on-demand Device readiness screen exposes only allowlisted, bounded local version
and capability fields. It runs before profile loading and does not read secrets,
account configuration or private lists/history. It neither logs nor writes a report,
contacts a service, nor tests playback. Prefer these safe fields over a full backup.

The inactive account-flow controller sends a user code only to its explicit display
callback, never diagnostics. Device codes/tokens are not returned in flow outcomes.
Replacement/disconnect confirmation is tied to observed credential generation; a
changed session cannot be overwritten by a stale confirmation. Local disconnect does
not revoke remote authorization or erase backups, and cleanup failure is not success.

Repository-candidate verification is a read-only integrity check, not a source-trust
or malware guarantee. PR checks run on creation, update, reopening and promotion;
they upload only candidate/report artifacts and have no public-comment operation.

## Provider credentials and resolved links

The inactive Real-Debrid open-source grant receives user-bound client credentials
after consent. These secrets are not bundled public application credentials. No provider
credentials are persisted or enabled in this preview. A separately reviewed private
store, durable refresh ownership and bounded provider transport are activation gates.

Resolved URLs are sensitive. Error messages and representations omit response bodies,
source links, filenames and tokens. URL syntax checks reject credential-bearing and
local-address forms; they do not resolve DNS or constrain subsequent redirects. Live
network/player adapters must enforce destination policy. Explicit resolution is one
attempt with no retry after an uncertain response, and no Remote Traffic option.
