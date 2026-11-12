# Backlog

| Batch | Scope | State / exit condition |
|---|---|---|
| 1 | Mocked widgets, context menus, guidance, tests, local ZIP | Includes saved movie collection and aired-unwatched episode filter; TV acceptance pending |
| 2 | Trakt authentication feasibility | Mocked lifecycle, protected token rotation, transport and session coordination implemented; registration/live login/refresh still pending ([evidence](trakt-authentication.md)) |
| 3 | Personal lists and watch progress | Read API, normalized views and invocation-memory library cache mocked; account-bound selections and explicit watched/list-add contracts mocked; live UI/write validation and persistent metadata caching pending |
| 4 | Umbrella playback experiment | Pending: installed version, movie/episode identity, cancellation, subtitles, resume, one scrobbling owner, next-episode choice |
| 5 | Repository installation and updates | Local generation plus checksum-pinned version retention implemented; fresh install/upgrade and channel publication pending |
| 6 | Optional native playback / skin changes | Only if a demonstrated need justifies scope and licensing review |

Real recommendations need a reviewed metadata provider and terms. Upcoming movie
release dates require a defined release type/region; they do not prove playability.
No batch depends on a separate always-on server or standalone Android application.

## Combined batch: Workflows and retained candidates (0.4.0)

Four related sub-batches share one PR and independent review:

1. Visible synthetic workflows: My movie list accepts future movies and supports
   duplicate-safe add/cancellable remove; episode context menus switch between all
   episodes and aired unwatched episodes. Existing routes/profile selections remain.
2. Durable selected-list preferences are bound to verified stable account identity,
   survive refresh/restart, and stay separate across accounts. No live Kodi account
   mode is enabled; only fabricated settings/list responses are tested.
3. Explicit single-item mark-watched and owned movie-list-add contracts validate
   outcomes and never retry uncertain writes. Writes are disabled by default and
   not exposed by Kodi routes. Remote mark-unwatched/history deletion is excluded.
4. Candidate repository retention accepts a bounded local inventory of reviewed ZIPs
   and expected checksums. Older versions remain available in the generated tree;
   only current versions enter the index. No publication or automatic downgrade.

Before live account work: register an application, provide its public client ID and
registered redirect URI (never its secret), verify login/refresh and device TLS/SQLite,
then wire account UX and real list views. Confirmed action contracts still need live
validation and UI ownership/reconciliation; duplicate history plays are possible
if a user manually retries an uncertain action. Playback remains a separate gate.

Before repository activation: approve the retention inventory, publish immutable
packages before the index, test fresh install/upgrade and deliberate manual rollback
on the actual TV. The reserved repository path remains outside the deployed site.
