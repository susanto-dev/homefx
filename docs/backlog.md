# Backlog

| Batch | Scope | State / exit condition |
|---|---|---|
| 1 | Mocked widgets, context menus, guidance, tests, local ZIP | Implemented; cloud checks recorded in delivery; TV acceptance pending |
| 2 | Trakt authentication feasibility | Mocked lifecycle, protected token rotation, transport and session coordination implemented; registration/live login/refresh still pending ([evidence](trakt-authentication.md)) |
| 3 | Personal lists and watch progress | Read API, normalized views and invocation-memory library cache mocked; live transport, actual list selection, caching, manual watched writes and list additions pending |
| 4 | Umbrella playback experiment | Pending: installed version, movie/episode identity, cancellation, subtitles, resume, one scrobbling owner, next-episode choice |
| 5 | Repository installation and updates | Local candidate package/index generation implemented; fresh install/upgrade and update-channel publication pending |
| 6 | Optional native playback / skin changes | Only if a demonstrated need justifies scope and licensing review |

Real recommendations need a reviewed metadata provider and terms. Upcoming movie
release dates require a defined release type/region; they do not prove playability.
No batch depends on a separate always-on server or standalone Android application.

## Current batch: Connectivity and repository candidates (0.3.0)

Includes a fixed-host HTTPS transport, account/session coordination, generation-bound
read-library caching, mocked integration tests, local repository ZIP/index generation,
PR candidate artifacts and account setup guidance. The Kodi connection-setup menu is
information only; existing demo routes stay synthetic. Changes enter protected main
through a reviewed PR. No live login or update repository is activated by this batch.

Before connecting real accounts: register a development application, provide the public
client ID and registered redirect URI (never a client secret), verify secret-free
refresh and target SQLite/TLS support, and complete account-switch/revocation UX.
Then connect selected lists/read-only progress. Watch writes and playback remain
separate acceptance gates. No real account identity was supplied to automated tests.

Before activating repository updates: inspect the candidate artifact, choose version
retention/rollback policy, publish immutable package paths before the index, and verify
fresh install/upgrade on Kodi. The generated endpoint is reserved and currently absent
from the public preview. The candidate is build evidence, not an operational channel.
