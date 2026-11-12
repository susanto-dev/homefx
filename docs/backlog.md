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

## Combined batch: Browsing and widget sources (0.6.0)

Four parallel slices extend the preview and its mocked service foundation:

1. List filters, saved upcoming movies, season folders/counts and unknown-date handling in the new model filters.
2. A dedicated Widget sources directory, scope-preserving episode menus, quiet empty
   folders and strict route validation in the Kodi adapter.
3. Inactive Trakt movie/continue/episode views with guarded joins and explicit unknown
   movie watched status. List metadata alone cannot support an unwatched-movie claim.
4. Two isolated package/site/candidate builds compared byte-for-byte, with candidate
   verification before accepting either output. CI runs this on both Python versions.

TV acceptance is still pending. Live account routes require registration and verified
login/refresh; movie history, complete extended metadata, real recommendations and
playback remain separate work. Repository hosting remains inactive pending reviewed
retention plus install/upgrade tests. The next device step is to install this preview,
check widget sources and filtered season navigation, and record Device readiness.
