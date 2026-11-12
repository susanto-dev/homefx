# Decisions

## 2026-11-12 — Mocked foundation

Approved scope: a Kodi video add-on preview, project guidance, local checks and ZIP
packaging. Retain the existing skin. No account connection, server, native Android
app, publishing, or repository settings changes. All titles/art are invented.

Requested behavior: multiple Trakt list widgets, episode browsing with watched and
air-date information, unfinished items first, manual watched correction, movie
release dates including upcoming movies, title search and related movies.

Provisional preview choices, not final product rulings:
- Widgets: unfinished first (most recently watched), released unwatched newest first,
  upcoming soonest first, watched last. Episodes inside a show remain narrative order.
- Continue watching and next episodes are separate routes. Upcoming means the next
  seven days, excluding today; date-only mock data uses the device's current date.
- Next-episode preview offers replay / next aired unwatched / stop when applicable.
- Related movies retain fictional relevance order. Provider integration is undecided.

MIT already existed in the repository and remains unchanged. The package carries
that same notice. Final owner licence preference is still pending.

Trakt login feasibility, date semantics for real releases, playback ownership,
Umbrella version/compatibility and clickable widget headers remain unverified.

## 2026-11-12 — Publish the synthetic preview

The owner authorized public preview publication after configuring GitHub Pages
for Actions. Publish a ZIP download page with tests and no paid dependencies.
This supersedes the initial publication hold for this preview only. TV acceptance,
real service integration and a Kodi update repository remain separate work.

## 2026-11-12 — Trakt foundations without live account access

The next implementation batch covers authentication, local token persistence,
read API handling, normalized watch views, tests and packaging together. Device
login is caller-driven so a future Kodi UI can cancel and honor polling intervals.
Refresh ownership must be durable across invocations: ambiguous or interrupted
rotation requires reauthentication instead of retrying a potentially consumed token.

Use only original standard-library Python implementation and synthetic responses.
No client secret, real credentials, new paid service or third-party runtime package
is introduced. Existing MIT notices remain unchanged. No live transport or login
menu is enabled until application registration, secret-free refresh and device
validation pass. Aired/released status continues to mean metadata, not playability.

The 0.2.0 package includes inactive foundations and preserves demo routes/state.
PR checks validate Python 3.8 and 3.12 plus the package; the actual TV interpreter
and SQLite capability remain unverified. Independent review covers the combined
commit before the maintainer merges. Merging main publishes the synthetic preview;
it does not activate a real account or an automatic Kodi update channel.

## 2026-11-12 — Connectivity and repository candidates

Use PRs exclusively for protected main. Parallel implementation covers bounded HTTPS
transport, session/library orchestration and local update-repository generation, with
independent review of the integrated head. Public material remains tool-neutral.

Transport uses only the two fixed Trakt hosts and rejects redirects. Network I/O is
inactive in the Kodi preview; tests inject responses rather than use accounts.
Account/session coordination rechecks credential generation before serving cached data
and uses conditional token-store updates so stale login/logout results cannot overwrite
a newer account. Cached list/progress responses live only in bounded invocation memory.

The repository generator targets a reserved HTTPS path and creates a candidate artifact
for review, separate from dist/site. It is not deployed by the Pages workflow. Public
repository activation and retained-version/rollback policy remain future gates. The
existing manual-video preview advances to 0.3.0 on merge. Original MIT notices remain
unchanged, with no third-party source/assets or paid service added.

## 2026-11-12 — Combined workflow and retained-candidate batches

Bundle related sub-batches in one PR so the maintainer reviews one integrated result.
Use parallel implementation with independent review; no PR review/status comments.
Keep evidence and limitations in the PR description, then mark the draft ready.
Protected main remains PR-only and the maintainer merges.

The visible 0.4.0 preview adds local saved movies (including future releases) and
an aired-unwatched episode filter while preserving all-episode browsing and existing
widget routes. These remain synthetic actions, never queued future Trakt writes.

Account list selections use the service's stable user UUID, not a mutable username.
They may persist across token refresh/restart, but never substitute for verification
of the current account. Private list IDs are separate from cached metadata/history.
Explicit library disconnect clears all saved list choices in this local profile
without fetching account identity; normal account switches stay isolated. Hashing an account key is a namespace, not encryption or anonymization.

Explicit action contracts support one mark-watched or owned-list movie addition.
They do not auto-retry: a lost response can hide a successful write, and repeated
history plays are not deduplicated by Trakt. Unknown results require reconciliation.
Remote mark-unwatched/history deletion and scrobbling remain outside this batch.
No live action is enabled by installing the preview, even with a manually copied
profile. Action attempts invalidate invocation read caches.

Repository retention is opt-in through an explicitly reviewed, checksum-pinned local
inventory. The generator never downloads retained packages, promotes older versions
into the current index, or overwrites a different package at an existing version.
This prepares a future update channel without activating one. Existing MIT terms
remain unchanged; no new dependency, paid service or third-party code/assets added.

## 2026-11-12 — Activation readiness and PR event coverage

Keep one reviewed PR for the device-readiness, account-flow and detached-repository
verification sub-batches. Main remains protected and no review/status comments are
posted. Existing PR checks already covered creation/update/reopening; explicitly add
ready_for_review so draft promotion reruns validation/security without new automation
that writes to PR discussions. External review automation is maintainer-managed.

Device readiness is local and deliberately limited to safe version/capability fields.
It does not read account settings, profiles, watch history or network services, create
a token store, or label the device integration as passed. The controller for future
account UI uses injected callbacks and mocked responses; confirmation is tied to the
observed session so a delayed dialog cannot replace or disconnect a newer account.
No live route or client registration is supplied by this batch.

A read-only candidate verifier runs after generation and before CI artifact upload.
It detects damaged/mismatched artifact contents without mutating them. Checksums and
structural checks are not signatures or independent source approval. The reserved
repository endpoint remains inactive. No new dependency, paid service, licence change
or third-party code/assets is introduced.

## Browsing expansion (0.6.0)

Keep the current skin and expose a Widget sources directory plus stable content
URLs. List filters and season navigation extend the synthetic preview while live
activation remains gated. A release date is metadata, not evidence of a playable
source. Movie watched status stays unknown when list/paused responses cannot establish
it; do not infer unwatched from absence. Release checks compare isolated builds
without publishing repository artifacts or adding dependencies.

## Explicit Real-Debrid planning and inactive contracts (0.7.0)

Real-Debrid is a first-class planned component, distinct from metadata and source
discovery. Develop original injected authorization, API and playback contracts with
fabricated responses; do not ship a shared client secret or activate account access.
The service's open-source workflow obtains private user-bound credentials at runtime.

Retain both the Umbrella experiment and a direct-resolution candidate until evidence
supports the first live path. Source-provider selection, secure persistent credentials,
transport, Kodi playback and one resume/scrobbling owner remain explicit gates. No paid
service purchase, new dependency, third-party source reuse or licence change is made.

## Provider coordination and complete watch-state evidence (0.8.0)

Continue a larger parallel batch with independent review: separate provider storage,
bounded API transport, session/refresh coordination and full movie watched snapshots.
No live route or account is enabled. Treat interrupted provider refresh conservatively
as reauthentication, without assuming the service's refresh token is single-use.
A failed or incomplete movie watched snapshot must never imply everything is unwatched.

Reconcile every product, release and quality backlog item in backlog.md. Distinguish
implemented code, fabricated service evidence, unresolved choices and pending TV checks.
Existing source/provider, licence and release choices stay open; no paid service, new
dependency or third-party source is introduced by this batch.

## Experimental repository-first channel and quality checks (0.9.0 / 0.2.0)

The owner authorized continuing the remaining safe batches in one larger PR and
specifically requested repository-first Kodi installation. This supersedes earlier
manual-download-only and repository-publication holds. Publish the experimental
preview repository through the existing Pages workflow after the maintainer merges
protected main. No direct main push, automatic merge or PR discussion comment is needed.

Ship video 0.9.0 and repository 0.2.0. The website offers a root bootstrap ZIP, then
Install from repository → HomeFX Preview Repository → Video add-ons → HomeFX Preview.
Retain the manual video download. Keep the existing skin installed separately; no
skin code/assets are redistributed. Account/provider/title-search contracts remain
inactive and use fabricated tests; no live credentials or playable sources are added.

Use a reviewed inventory to preserve every recorded package version and immutable
path/hash. Require current packages to match fresh builds and compare history against
the reviewed base revision. Current versions alone enter the index. Limits fail
closed; increasing bounds needs review rather than automatic deletion. Retention
supports investigation and explicit downgrade, not a guarantee of profile rollback.

Build a complete verified preview tree, check isolated repeatability, then verify the
exact deployed artifact against public HTTPS bytes. Deployment and HTTP checks do not
replace pending repository install/upgrade or other device acceptance. Preserve live
account, playback, subtitle, resume and scrobbling gates.

Add development-only Ruff correctness checks and hash-locked tooling installs, while
keeping full-SHA external Action pins and weekly manual update triage. The official
Kodi add-on checker is still a documented coverage gap. Existing MIT notices and the
pending final owner licence preference remain unchanged; no paid service or runtime
third-party Python dependency is added.
