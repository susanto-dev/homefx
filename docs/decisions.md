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
