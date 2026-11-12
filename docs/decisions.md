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
