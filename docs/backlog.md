# Backlog

| Batch | Scope | State / exit condition |
|---|---|---|
| 1 | Mocked widgets, context menus, guidance, tests, local ZIP | Implemented; cloud checks recorded in delivery; TV acceptance pending |
| 2 | Trakt authentication feasibility | Mocked lifecycle, token storage and refresh coordination implemented; registration/live login/refresh still pending ([evidence](trakt-authentication.md)) |
| 3 | Personal lists and watch progress | Read API and normalized view foundations mocked; live transport, actual list selection, caching, manual watched writes and list additions pending |
| 4 | Umbrella playback experiment | Pending: installed version, movie/episode identity, cancellation, subtitles, resume, one scrobbling owner, next-episode choice |
| 5 | Repository installation and updates | Pending: index generation, fresh install/upgrade, approved static hosting/publication |
| 6 | Optional native playback / skin changes | Only if a demonstrated need justifies scope and licensing review |

Real recommendations need a reviewed metadata provider and terms. Upcoming movie
release dates require a defined release type/region; they do not prove playability.
No batch depends on a separate always-on server or standalone Android application.

## Current batch: Trakt foundations (0.2.0)

Includes the device-login state machine, atomic token rotation with one refresh
claimant, bounded read/pagination/error handling, progress/date normalization,
mocked behavioral tests, package integration and PR validation. The Kodi preview
remains synthetic. Independent review and CI are required before merge; TV
acceptance and real service validation are separate gates, not inferred from mocks.

Next bounded candidate: register a development application, verify the public-client
contract with a timeout-bounded TLS transport, and add an explicit account connection
screen. Before that work, supply the public client ID and registered redirect URI
through the agreed configuration path (never a client secret), define disconnect and
account-switch behavior, and verify target SQLite/interpreter support. Select real
lists only after login works. Keep playback as its own experiment.
